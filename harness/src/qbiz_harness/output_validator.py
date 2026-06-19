"""Component 2 — Output Validator.

Intercepts the LLM's response *before* any downstream action is taken. Where the input wrapper
(Component 1) guards what reaches the model, this guards what leaves it: the model can reason its
way to a bad answer, but it cannot reason its way past a code check on that answer.

Mechanical (Layer 1) checks, all dependency-free:

- **Format validation** — the response parses and matches the expected shape. A downstream step
  that expects JSON with certain fields gets a hard guarantee, not a hope.
- **Hallucinated tool-call detection** — every tool the model asks to call must be in the agent's
  registered allowlist. The allowlist is the same per-agent set Component 3 (access controls) keys
  off; this component is the *output-side* check ("did the model invent a tool?") and Component 3
  is the *call-side* check ("is this agent allowed to invoke it?").
- **Out-of-scope flagging** — the response must not reference systems the agent is not permitted to
  touch.

Two things deliberately live elsewhere. *Factual consistency* ("is the cited data real and does it
support the claim?") and deeper semantic correctness are Layer 2 — the evaluator (Component 7) —
because they need reasoning, not a rule. *Downstream-compatibility* beyond shape is enforced by the
caller's own `expected_schema`.

**Pure enforcement, no I/O.** Like the other components, this raises `OutputRejectedError`; the
call site records the rejection through the audit log (as a `harness_intervention`).

**Partial-output policy is the call site's to choose**, per the plan:
- *reject-and-re-prompt* (simple calls) — run :func:`validate_output`, which raises on any
  violation; the caller catches it and asks the model again.
- *strip-and-log* (expensive pipelines where a full retry is costly) — run :func:`inspect_output`,
  which never raises; the caller reads `result.violations`, strips/repairs the offending parts, and
  logs each one.

Robustness note: ``requested_tools`` / ``referenced_systems`` should come from the model's
*structured* output (e.g. tool-use blocks), not a regex over prose. A check on structured fields is
non-bypassable; scraping free text is not, and a determined prompt can dodge it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from qbiz_harness.exceptions import OutputRejectedError

# A lightweight schema: field name → the type (or tuple of types) it must hold. Every named field
# is required. This is intentionally not full JSON-Schema — that's a later dependency choice if a
# richer contract is ever needed; the common case (required keys of known types) needs no library.
Schema = Mapping[str, "type | tuple[type, ...]"]


@dataclass(slots=True)
class Violation:
    """One thing wrong with an output. `kind` groups it; `detail` is human-readable."""

    kind: str  # "format" | "hallucinated_tool" | "out_of_scope"
    detail: str


@dataclass(slots=True)
class ValidationResult:
    """The outcome of inspecting an output — empty `violations` means it passed.

    Returned by :func:`inspect_output` so a pipeline call site can strip-and-log. A strict call
    site instead uses :func:`validate_output`, or calls :meth:`raise_if_violations` on this.
    """

    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def raise_if_violations(self) -> None:
        """Raise `OutputRejectedError` summarising every violation, if there are any."""
        if self.violations:
            summary = "; ".join(f"{v.kind}: {v.detail}" for v in self.violations)
            raise OutputRejectedError(f"Output failed validation — {summary}")


def check_format(response: Any, expected_schema: Schema) -> list[Violation]:
    """Verify `response` parses to an object matching `expected_schema`.

    A `str` is parsed as JSON first (a parse failure is itself a format violation). The result
    must be a mapping carrying every schema key with a value of the declared type(s). Returns one
    `Violation` per problem; an empty list means the shape is sound.
    """
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except (json.JSONDecodeError, ValueError) as exc:
            return [Violation("format", f"response is not valid JSON ({exc})")]

    if not isinstance(response, Mapping):
        return [Violation("format", f"expected an object, got {type(response).__name__}")]

    violations: list[Violation] = []
    for key, expected_type in expected_schema.items():
        if key not in response:
            violations.append(Violation("format", f"missing required field {key!r}"))
            continue
        value = response[key]
        # bool is a subtype of int — guard against an accidental True passing an `int` field.
        if expected_type is int and isinstance(value, bool):
            violations.append(Violation("format", f"field {key!r} is bool, expected int"))
        elif not isinstance(value, expected_type):
            type_name = getattr(expected_type, "__name__", str(expected_type))
            violations.append(
                Violation("format", f"field {key!r} is {type(value).__name__}, expected {type_name}")
            )
    return violations


def check_tool_calls(requested_tools: Iterable[str], allowed_tools: Iterable[str]) -> list[Violation]:
    """Flag any requested tool not in the agent's allowlist — i.e. a hallucinated/forbidden tool.

    `allowed_tools` is the per-agent set shared with Component 3. A name the model asked for that
    isn't in it is either invented or out of this agent's scope; either way it must not run.
    """
    allowed = set(allowed_tools)
    return [
        Violation("hallucinated_tool", f"tool {tool!r} is not in the agent's allowlist")
        for tool in requested_tools
        if tool not in allowed
    ]


def check_scope(
    referenced_systems: Iterable[str], permitted_systems: Iterable[str]
) -> list[Violation]:
    """Flag any system the output references that the agent is not permitted to touch."""
    permitted = set(permitted_systems)
    return [
        Violation("out_of_scope", f"output references out-of-scope system {system!r}")
        for system in referenced_systems
        if system not in permitted
    ]


def inspect_output(
    response: Any,
    *,
    expected_schema: Schema | None = None,
    requested_tools: Iterable[str] | None = None,
    allowed_tools: Iterable[str] | None = None,
    referenced_systems: Iterable[str] | None = None,
    permitted_systems: Iterable[str] | None = None,
) -> ValidationResult:
    """Run every opted-in check and return the collected violations *without raising*.

    Each check runs only when the caller supplies the data it needs, so validation is opt-in at the
    call site (a low-stakes read may check nothing; a write-capable agent checks all three). Use
    this for the *strip-and-log* policy; use :func:`validate_output` for *reject-and-re-prompt*.
    """
    violations: list[Violation] = []
    if expected_schema is not None:
        violations += check_format(response, expected_schema)
    if allowed_tools is not None and requested_tools is not None:
        violations += check_tool_calls(requested_tools, allowed_tools)
    if permitted_systems is not None and referenced_systems is not None:
        violations += check_scope(referenced_systems, permitted_systems)
    return ValidationResult(violations)


def validate_output(
    response: Any,
    *,
    expected_schema: Schema | None = None,
    requested_tools: Iterable[str] | None = None,
    allowed_tools: Iterable[str] | None = None,
    referenced_systems: Iterable[str] | None = None,
    permitted_systems: Iterable[str] | None = None,
) -> Any:
    """Strict validation — raise `OutputRejectedError` on any violation, else return `response`.

    The *reject-and-re-prompt* path: a caller wraps this around the model's output and, on
    rejection, re-prompts. Returns the original `response` unchanged so it can be used inline.
    """
    inspect_output(
        response,
        expected_schema=expected_schema,
        requested_tools=requested_tools,
        allowed_tools=allowed_tools,
        referenced_systems=referenced_systems,
        permitted_systems=permitted_systems,
    ).raise_if_violations()
    return response
