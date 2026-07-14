"""Collectors — deterministic scanners that turn client evidence into findings.

Collectors are the free tier of the assessment: no LLM, ever. Each declares its metadata
(name, the dimensions it can assess, its acquisition mode, the inputs it needs, and — for
connected mode — the MCP servers it calls) and registers itself via the ``@collector``
decorator; the engine, CLI, and profile loader discover collectors from the registry, never
from a hardcoded list. ``qba assay list-collectors`` renders this registry for a consultant.

A collector never raises on messy input — a broken artifact is itself a finding. The engine
runs collectors under the harness's redundancy guard and records each run in the audit log.

Acquisition modes (a collector declares exactly one):
- **artifact** — offline parsing of files the client shared. Zero credentials, zero network.
  The only mode the pulse tier allows — that zero-credential property is a hard constraint.
- **connected** — read-only queries against live client systems, always through a shared MCP
  server (declared in ``requires_mcp``, enforced here — the reuse-over-duplication rule).
- **interview** — structured questionnaires whose answers flow through the same Finding
  pipeline as attestations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping

from qbiz_assay.findings import DimensionId, EvidenceType, Finding


class AcquisitionMode(str, Enum):
    ARTIFACT = "artifact"
    CONNECTED = "connected"
    INTERVIEW = "interview"


#: The evidence type findings from each mode naturally carry.
DEFAULT_EVIDENCE: dict[AcquisitionMode, EvidenceType] = {
    AcquisitionMode.ARTIFACT: EvidenceType.ARTIFACT,
    AcquisitionMode.CONNECTED: EvidenceType.SYSTEM_OF_RECORD,
    AcquisitionMode.INTERVIEW: EvidenceType.ATTESTATION,
}


@dataclass(slots=True)
class CollectorResult:
    """What one collector saw: raw stats for the report, findings for the rubric.

    ``dimensions`` is the set of dimensions this run *assessed* — a claimed dimension with no
    findings scores clean, an unclaimed one stays "Not assessed" (see rubric).
    """

    name: str
    dimensions: set[DimensionId] = field(default_factory=set)
    stats: dict[str, object] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


#: A collector's entry point: keyword arguments matching its declared ``inputs``, one
#: ``CollectorResult`` out. (A Protocol with **kwargs adds nothing over this alias.)
CollectorFn = Callable[..., CollectorResult]


@dataclass(slots=True, frozen=True)
class CollectorInfo:
    """A collector's declared metadata — what discovery (`list-collectors`) shows.

    ``inputs`` maps each keyword argument of the collect function to a human description of
    what to pass (a file path, a directory, a questionnaire id, an MCP tool caller), so a
    consultant can see at a glance what a client must share or grant for this check to run.
    """

    name: str
    dimensions: frozenset[DimensionId]
    mode: AcquisitionMode
    inputs: Mapping[str, str]
    requires_mcp: tuple[str, ...] = ()
    description: str = ""


@dataclass(slots=True, frozen=True)
class RegisteredCollector:
    info: CollectorInfo
    fn: CollectorFn

    @property
    def name(self) -> str:
        return self.info.name


_REGISTRY: dict[str, RegisteredCollector] = {}


def collector(
    *,
    name: str,
    dimensions: set[DimensionId] | frozenset[DimensionId],
    mode: AcquisitionMode,
    inputs: Mapping[str, str],
    requires_mcp: tuple[str, ...] = (),
    description: str = "",
) -> Callable[[CollectorFn], CollectorFn]:
    """Register a collect function. The function itself is returned unchanged, so it stays
    directly callable in tests and ad-hoc scripts.

    Enforced at registration (it is cheaper to fail here than in an engagement):
    - names are unique;
    - an **artifact** collector declares no MCP servers (zero-credential is the pulse tier's
      hard constraint, and artifact mode is the only mode that tier allows);
    - a **connected** collector declares at least one — live-system access goes through a
      shared MCP server, per the repo's reuse-over-duplication rule, never through client
      code private to Assay.
    """
    mode = AcquisitionMode(mode)
    if mode is AcquisitionMode.ARTIFACT and requires_mcp:
        raise ValueError(f"collector {name!r}: artifact mode must not declare requires_mcp")
    if mode is AcquisitionMode.CONNECTED and not requires_mcp:
        raise ValueError(
            f"collector {name!r}: connected mode must declare the MCP server(s) it calls "
            "(requires_mcp) — see the repo's reuse-over-duplication rule"
        )

    info = CollectorInfo(
        name=name,
        dimensions=frozenset(dimensions),
        mode=mode,
        inputs=dict(inputs),
        requires_mcp=tuple(requires_mcp),
        description=description,
    )

    def register(fn: CollectorFn) -> CollectorFn:
        existing = _REGISTRY.get(name)
        if existing is not None and existing.fn is not fn:
            raise ValueError(f"collector name {name!r} is already registered")
        _REGISTRY[name] = RegisteredCollector(info=info, fn=fn)
        return fn

    return register


def load_builtin_collectors() -> None:
    """Import the collectors that ship with Assay so they self-register."""
    from qbiz_assay.collectors import ai_usage, airflow, cloud_posture, dbt  # noqa: F401


def all_collectors() -> tuple[RegisteredCollector, ...]:
    """Every registered collector, name-sorted. Loads the built-ins on first use."""
    load_builtin_collectors()
    return tuple(_REGISTRY[name] for name in sorted(_REGISTRY))


def get_collector(name: str) -> RegisteredCollector:
    load_builtin_collectors()
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise KeyError(f"no collector named {name!r} (registered: {known})") from None


__all__ = [
    "AcquisitionMode",
    "CollectorFn",
    "CollectorInfo",
    "CollectorResult",
    "DEFAULT_EVIDENCE",
    "RegisteredCollector",
    "all_collectors",
    "collector",
    "get_collector",
    "load_builtin_collectors",
]
