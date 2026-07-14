"""Assessment config — the dimension/rubric/offering registries, loaded from YAML.

The framework's core design rule is that core pieces iterate registries, never enums: every
domain-specific fact — which dimensions exist, what they weigh, what the score bands are,
which offerings a remediation can point at — lives here as data, discovered at runtime. Qbiz
ships a baseline (``config/qbiz_baseline.yaml``); an engagement profile can override any part
of it, honoring the standing principle that a client's own standards beat the Qbiz default.

If adding an assessment domain requires editing ``engine.py``, ``rubric.py``, or
``report.py``, that is a framework bug. It should only ever require entries here (Tier 0)
and possibly one new collector (Tier 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

import yaml

from qbiz_assay.findings import DimensionId, OfferingId, Severity

#: Fallback weight for a dimension that appears in findings but not in the rubric config —
#: evidence trumps registration, so it still gets scored.
DEFAULT_DIMENSION_WEIGHT = 1.0


@dataclass(slots=True, frozen=True)
class DimensionSpec:
    """One registered readiness dimension."""

    id: DimensionId
    title: str
    weight: float = DEFAULT_DIMENSION_WEIGHT
    description: str = ""


@dataclass(slots=True, frozen=True)
class OfferingSpec:
    """One entry in the remediation → engagement catalog."""

    id: OfferingId
    title: str
    description: str = ""


@dataclass(slots=True, frozen=True)
class RubricConfig:
    """The scoring registry: dimensions, severity weights, score bands."""

    dimensions: tuple[DimensionSpec, ...]
    severity_weights: Mapping[Severity, int]
    bands: tuple[tuple[int, str], ...]

    def dimension_ids(self) -> tuple[DimensionId, ...]:
        return tuple(d.id for d in self.dimensions)

    def spec_for(self, dimension_id: DimensionId) -> DimensionSpec:
        """The registered spec, or an unregistered-but-scored placeholder (see YAML note)."""
        for spec in self.dimensions:
            if spec.id == dimension_id:
                return spec
        return DimensionSpec(id=dimension_id, title=dimension_id)

    def title_for(self, dimension_id: DimensionId) -> str:
        return self.spec_for(dimension_id).title

    def weight_for(self, dimension_id: DimensionId) -> float:
        return self.spec_for(dimension_id).weight

    def band_for(self, score: int) -> str:
        for minimum, name in self.bands:
            if score >= minimum:
                return name
        return self.bands[-1][1]

    def deduction_for(self, severity: Severity) -> int:
        return self.severity_weights.get(severity, 0)


@dataclass(slots=True, frozen=True)
class AssessmentConfig:
    """Everything the generic machinery iterates: the rubric plus the offering catalog."""

    rubric: RubricConfig
    offerings: Mapping[OfferingId, OfferingSpec] = field(default_factory=dict)

    def offering_title(self, offering_id: OfferingId) -> str:
        """Resolve an offering id to its display title; an uncataloged id displays as-is
        (a collector emitting one is worth noticing in review, not worth crashing a run)."""
        spec = self.offerings.get(offering_id)
        return spec.title if spec is not None else offering_id


# --- parsing ------------------------------------------------------------------------------------


class ConfigError(ValueError):
    """A config file is malformed — raised with the offending key, never silently defaulted."""


def _parse_dimension(entry: Mapping[str, Any]) -> DimensionSpec:
    if not isinstance(entry, Mapping) or "id" not in entry:
        raise ConfigError(f"rubric.dimensions entries need an 'id': got {entry!r}")
    return DimensionSpec(
        id=str(entry["id"]),
        title=str(entry.get("title", entry["id"])),
        weight=float(entry.get("weight", DEFAULT_DIMENSION_WEIGHT)),
        description=str(entry.get("description", "")),
    )


def _parse_severity_weights(raw: Mapping[str, Any]) -> dict[Severity, int]:
    weights: dict[Severity, int] = {}
    for key, value in raw.items():
        try:
            severity = Severity(key)
        except ValueError as exc:
            raise ConfigError(f"unknown severity {key!r} in rubric.severity_weights") from exc
        weights[severity] = int(value)
    return weights


def _parse_bands(raw: list[Any]) -> tuple[tuple[int, str], ...]:
    bands: list[tuple[int, str]] = []
    for entry in raw:
        if not isinstance(entry, Mapping) or "min" not in entry or "name" not in entry:
            raise ConfigError(f"rubric.bands entries need 'min' and 'name': got {entry!r}")
        bands.append((int(entry["min"]), str(entry["name"])))
    bands.sort(key=lambda b: -b[0])
    if not bands or bands[-1][0] > 0:
        raise ConfigError("rubric.bands must include a band with min: 0")
    return tuple(bands)


def _parse_offerings(raw: Mapping[str, Any]) -> dict[OfferingId, OfferingSpec]:
    offerings: dict[OfferingId, OfferingSpec] = {}
    for offering_id, entry in raw.items():
        entry = entry or {}
        if not isinstance(entry, Mapping):
            raise ConfigError(f"offerings.{offering_id} must be a mapping: got {entry!r}")
        offerings[str(offering_id)] = OfferingSpec(
            id=str(offering_id),
            title=str(entry.get("title", offering_id)),
            description=str(entry.get("description", "")),
        )
    return offerings


def parse_config(raw: Mapping[str, Any]) -> AssessmentConfig:
    """Parse a full config mapping (the shape of ``qbiz_baseline.yaml``)."""
    rubric_raw = raw.get("rubric")
    if not isinstance(rubric_raw, Mapping):
        raise ConfigError("config needs a 'rubric' mapping")
    for required in ("dimensions", "severity_weights", "bands"):
        if required not in rubric_raw:
            raise ConfigError(f"rubric.{required} is required")
    rubric = RubricConfig(
        dimensions=tuple(_parse_dimension(d) for d in rubric_raw["dimensions"]),
        severity_weights=_parse_severity_weights(rubric_raw["severity_weights"]),
        bands=_parse_bands(rubric_raw["bands"]),
    )
    return AssessmentConfig(
        rubric=rubric,
        offerings=_parse_offerings(raw.get("offerings") or {}),
    )


def load_config(path: Path | str) -> AssessmentConfig:
    """Load a complete config file (baseline-shaped, all sections required as in parse)."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{path}: top level must be a mapping")
    return parse_config(raw)


def baseline_config() -> AssessmentConfig:
    """The shipped Qbiz baseline — the default when a profile overrides nothing."""
    text = (
        resources.files("qbiz_assay").joinpath("config/qbiz_baseline.yaml").read_text("utf-8")
    )
    return parse_config(yaml.safe_load(text))


# --- overrides (engagement profiles) --------------------------------------------------------


def apply_overrides(base: AssessmentConfig, overrides: Mapping[str, Any]) -> AssessmentConfig:
    """Overlay a profile's partial ``rubric:`` / ``offerings:`` sections onto ``base``.

    Merge semantics, chosen so a profile states only what differs from the baseline:
    - ``severity_weights``: per-severity update.
    - ``bands``: replaced wholesale when given (a partial band ladder is meaningless).
    - ``dimensions``: merged by id — listed fields override, unlisted fields keep the
      baseline value, ids new to the rubric are appended (that is the Tier-0 "add a
      dimension" move).
    - ``offerings``: merged by id, same way.
    """
    rubric = base.rubric
    rubric_raw = overrides.get("rubric") or {}
    if not isinstance(rubric_raw, Mapping):
        raise ConfigError("profile 'rubric' override must be a mapping")

    severity_weights = dict(rubric.severity_weights)
    if "severity_weights" in rubric_raw:
        severity_weights.update(_parse_severity_weights(rubric_raw["severity_weights"]))

    bands = rubric.bands
    if "bands" in rubric_raw:
        bands = _parse_bands(rubric_raw["bands"])

    dimensions = list(rubric.dimensions)
    for entry in rubric_raw.get("dimensions") or []:
        if not isinstance(entry, Mapping) or "id" not in entry:
            raise ConfigError(f"rubric.dimensions entries need an 'id': got {entry!r}")
        dim_id = str(entry["id"])
        existing = next((i for i, d in enumerate(dimensions) if d.id == dim_id), None)
        if existing is None:
            dimensions.append(_parse_dimension(entry))
        else:
            current = dimensions[existing]
            fields = {k: entry[k] for k in ("title", "weight", "description") if k in entry}
            if "weight" in fields:
                fields["weight"] = float(fields["weight"])
            dimensions[existing] = replace(current, **fields)

    offerings = dict(base.offerings)
    offerings_raw = overrides.get("offerings") or {}
    if not isinstance(offerings_raw, Mapping):
        raise ConfigError("profile 'offerings' override must be a mapping")
    for offering_id, entry in offerings_raw.items():
        entry = entry or {}
        current = offerings.get(str(offering_id))
        if current is None:
            offerings.update(_parse_offerings({offering_id: entry}))
        else:
            fields = {k: str(entry[k]) for k in ("title", "description") if k in entry}
            offerings[str(offering_id)] = replace(current, **fields)

    return AssessmentConfig(
        rubric=RubricConfig(
            dimensions=tuple(dimensions),
            severity_weights=severity_weights,
            bands=bands,
        ),
        offerings=offerings,
    )
