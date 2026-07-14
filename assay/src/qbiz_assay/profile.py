"""Engagement profiles — the per-client entry point.

One YAML file names the client, picks the delivery mode, enables collectors and their inputs,
overrides any part of the rubric or offering catalog (a client's own standards beat the Qbiz
default), and tightens harness limits. Writing one is the whole "plug into a client's tech
stack" step for any stack the collector library already covers — Tier 0 on the extension
ladder.

Shape::

    client: Acme Analytics
    mode: pulse                    # pulse | full
    collectors:
      - name: dbt-manifest
        inputs:
          manifest_path: artifacts/dbt/manifest.json   # artifact inputs are paths,
      - name: airflow-dags                             # resolved relative to this file
        inputs:
          dags_dir: artifacts/dags
    rubric:                        # optional, partial — merged over the Qbiz baseline
      dimensions:
        - id: data_quality
          weight: 2.0
    offerings: {}                  # optional, same merge-by-id semantics
    limits:                        # optional, any AssessmentLimits field
      spend_limit_usd: 1.0

The **pulse tier's zero-credential property is a hard constraint enforced here**: a ``pulse``
profile that enables a connected or interview collector fails to load. That property is what
makes the pulse check a lead magnet a prospect will actually agree to.

Connected collectors need live MCP connections, which YAML cannot carry: an input value of
``"mcp:<server>"`` is resolved at run time from the ``tool_callers`` mapping the caller passes
to :func:`run_profile` (Phase 3 wires real MCP transports; tests pass fakes).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Mapping

import yaml

from qbiz_assay.collectors import AcquisitionMode, RegisteredCollector, get_collector
from qbiz_assay.config import AssessmentConfig, apply_overrides, baseline_config
from qbiz_assay.engine import Assessment, AssessmentLimits, CollectorSpec, run_assessment

_MCP_INPUT_PREFIX = "mcp:"


class ProfileError(ValueError):
    """An engagement profile is invalid — raised at load, before anything runs."""


class DeliveryMode(str, Enum):
    PULSE = "pulse"
    FULL = "full"


@dataclass(slots=True)
class EnabledCollector:
    """One ``collectors:`` entry, resolved against the registry."""

    registered: RegisteredCollector
    inputs: dict[str, Any]

    @property
    def name(self) -> str:
        return self.registered.name


@dataclass(slots=True)
class EngagementProfile:
    client: str
    mode: DeliveryMode
    collectors: list[EnabledCollector]
    config: AssessmentConfig
    limits: AssessmentLimits = field(default_factory=AssessmentLimits)


def _parse_limits(raw: Mapping[str, Any]) -> AssessmentLimits:
    known = {f.name for f in fields(AssessmentLimits)}
    unknown = set(raw) - known
    if unknown:
        raise ProfileError(f"unknown limits field(s): {', '.join(sorted(unknown))}")
    return AssessmentLimits(**{k: v for k, v in raw.items()})


def _resolve_artifact_paths(inputs: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Artifact collectors take file/directory paths; relative ones are relative to the
    profile file, so a profile and its shared artifacts travel as one folder."""
    resolved: dict[str, Any] = {}
    for key, value in inputs.items():
        if isinstance(value, str) and not Path(value).is_absolute():
            resolved[key] = str((base_dir / value).resolve())
        else:
            resolved[key] = value
    return resolved


def load_profile(path: Path | str) -> EngagementProfile:
    """Load and validate an engagement profile. Every constraint that can fail is checked
    here, so a consultant finds out before the client meeting, not during it."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ProfileError(f"{path}: top level must be a mapping")

    client = raw.get("client")
    if not client or not isinstance(client, str):
        raise ProfileError(f"{path}: 'client' (a name) is required")

    try:
        mode = DeliveryMode(raw.get("mode", DeliveryMode.PULSE.value))
    except ValueError:
        raise ProfileError(
            f"{path}: mode must be one of {[m.value for m in DeliveryMode]}"
        ) from None

    entries = raw.get("collectors")
    if not isinstance(entries, list) or not entries:
        raise ProfileError(f"{path}: 'collectors' must be a non-empty list")

    enabled: list[EnabledCollector] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or "name" not in entry:
            raise ProfileError(f"{path}: collectors entries need a 'name': got {entry!r}")
        name = str(entry["name"])
        try:
            registered = get_collector(name)
        except KeyError as exc:
            raise ProfileError(f"{path}: {exc.args[0]}") from None

        if mode is DeliveryMode.PULSE and registered.info.mode is not AcquisitionMode.ARTIFACT:
            raise ProfileError(
                f"{path}: collector {name!r} is {registered.info.mode.value}-mode — the pulse "
                "tier allows artifact collectors only (zero credentials is a hard constraint; "
                "use mode: full for connected/interview collectors)"
            )

        inputs = dict(entry.get("inputs") or {})
        missing = set(registered.info.inputs) - set(inputs)
        if missing:
            raise ProfileError(
                f"{path}: collector {name!r} is missing input(s): {', '.join(sorted(missing))} "
                f"(each is described in `qba assay list-collectors`)"
            )
        if registered.info.mode is AcquisitionMode.ARTIFACT:
            inputs = _resolve_artifact_paths(inputs, path.parent)
        enabled.append(EnabledCollector(registered=registered, inputs=inputs))

    config = apply_overrides(baseline_config(), raw)

    limits_raw = raw.get("limits") or {}
    if not isinstance(limits_raw, Mapping):
        raise ProfileError(f"{path}: 'limits' must be a mapping")
    limits = _parse_limits(limits_raw)

    return EngagementProfile(
        client=client, mode=mode, collectors=enabled, config=config, limits=limits
    )


def build_collector_specs(
    profile: EngagementProfile,
    tool_callers: Mapping[str, Any] | None = None,
) -> list[CollectorSpec]:
    """Bind each enabled collector's inputs into the engine's ``(name, callable)`` shape.

    ``tool_callers`` maps MCP server name → live tool caller; a profile input valued
    ``"mcp:<server>"`` resolves through it. Missing callers fail here, before any collector
    runs — never mid-assessment.
    """
    tool_callers = tool_callers or {}
    specs: list[CollectorSpec] = []
    for enabled in profile.collectors:
        bound = dict(enabled.inputs)
        for key, value in bound.items():
            if isinstance(value, str) and value.startswith(_MCP_INPUT_PREFIX):
                server = value[len(_MCP_INPUT_PREFIX):]
                if server not in tool_callers:
                    raise ProfileError(
                        f"collector {enabled.name!r} needs a tool caller for MCP server "
                        f"{server!r}; pass tool_callers={{{server!r}: ...}} to run_profile"
                    )
                bound[key] = tool_callers[server]
        specs.append((enabled.name, partial(enabled.registered.fn, **bound)))
    return specs


def run_profile(
    profile: EngagementProfile | Path | str,
    *,
    tool_callers: Mapping[str, Any] | None = None,
    narrator: Any = None,
    audit: Any = None,
) -> Assessment:
    """Run one assessment exactly as an engagement profile describes it."""
    if not isinstance(profile, EngagementProfile):
        profile = load_profile(profile)
    return run_assessment(
        client_name=profile.client,
        collectors=build_collector_specs(profile, tool_callers),
        narrator=narrator,
        audit=audit,
        limits=profile.limits,
        config=profile.config,
    )
