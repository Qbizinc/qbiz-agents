"""Cloud-posture collector — read-only AWS security posture via the shared ``aws`` MCP server.

This is the plan's worked example landed for real: a connected-mode, out-of-list dimension
(``cloud_posture``) implemented at Tier-1 effort on top of a shared tool that already existed
(``mcp/mcp_aws``, read-only IAM/S3/Redshift through an assumed least-privilege role — see also
``skills/aws-readonly-explorer/``). Per the reuse-over-duplication rule there is **no boto3 in
here**: every fact comes from an MCP tool call, so any agent in the repo gets the same
capability for free.

Checks (a first pass, extended per engagement):
- **Public S3 buckets** — a bucket policy allowing Principal ``*``.
- **Unencrypted S3 buckets** — no server-side encryption configuration.
- **Over-broad IAM policies** — customer-managed policies allowing ``Action: *`` on
  ``Resource: *``.

The ``aws_call`` input is a tool caller: ``aws_call(tool_name, arguments) -> parsed result``.
The engagement runner supplies one bound to the live MCP connection (Phase 3); tests supply a
fake. A call that raises is recorded as *unchecked* — never silently scored, and never
reported as a clean pass: absence of an answer is not absence of a problem.

The ``cloud_posture`` dimension and the ``cloud_security_review`` offering are not in the Qbiz
baseline config; an engagement profile that enables this collector adds them (Tier 0) — see
``docs/EXTENDING.md``.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from qbiz_assay.collectors import AcquisitionMode, CollectorResult, collector
from qbiz_assay.findings import EvidenceType, Finding, Severity

_DIMENSIONS = {"cloud_posture"}

NAME = "aws-cloud-posture"

_OFFERING_CLOUD_SECURITY = "cloud_security_review"

#: ``aws_call("s3_list_buckets", {}) -> result`` — bound to the ``aws`` MCP server.
AwsToolCaller = Callable[[str, dict[str, Any]], Any]

#: Don't turn a huge estate into a huge bill of MCP round-trips on a first pass.
_MAX_BUCKETS = 50
_MAX_POLICIES = 50


def _statements(policy: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(policy, dict):
        return ()
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    return (s for s in statements if isinstance(s, dict))


def _is_public_principal(principal: Any) -> bool:
    if principal == "*":
        return True
    if isinstance(principal, dict):
        aws = principal.get("AWS")
        values = aws if isinstance(aws, list) else [aws]
        return "*" in values
    return False


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _allows_star_on_star(statement: dict[str, Any]) -> bool:
    return (
        statement.get("Effect") == "Allow"
        and "*" in _as_list(statement.get("Action"))
        and "*" in _as_list(statement.get("Resource"))
    )


def _is_listing_shape(value: Any, *, wrapper_key: str) -> bool:
    """A valid ``list_*`` response: a bare list, or ``{wrapper_key: [...]}``.

    Anything else (an error payload, a bare string, ``None``, ...) is a malformed
    response, not "zero items" — the caller must not silently treat it as empty.
    """
    if isinstance(value, list):
        return True
    return isinstance(value, dict) and isinstance(value.get(wrapper_key), list)


def _bucket_names(listing: Any) -> list[str]:
    """Accept either a plain name list or a list of ``{"name": ...}`` records.

    Caller must have already confirmed ``_is_listing_shape(listing, wrapper_key="buckets")``.
    """
    if isinstance(listing, dict):
        listing = listing.get("buckets", [])
    names: list[str] = []
    for entry in listing if isinstance(listing, list) else []:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict) and entry.get("name"):
            names.append(str(entry["name"]))
    return names


def _policy_records(listing: Any) -> list[dict[str, Any]]:
    """Caller must have already confirmed ``_is_listing_shape(listing, wrapper_key="policies")``."""
    if isinstance(listing, dict):
        listing = listing.get("policies", [])
    return [p for p in (listing if isinstance(listing, list) else []) if isinstance(p, dict)]


@collector(
    name=NAME,
    dimensions=_DIMENSIONS,
    mode=AcquisitionMode.CONNECTED,
    inputs={"aws_call": "tool caller bound to the read-only `aws` MCP server"},
    requires_mcp=("aws",),
    description="AWS security posture, read-only via the shared aws MCP server: public "
    "buckets, unencrypted storage, over-broad IAM policies.",
)
def collect(aws_call: AwsToolCaller) -> CollectorResult:
    result = CollectorResult(name=NAME, dimensions=set(_DIMENSIONS))
    unchecked: list[str] = []

    def call(tool: str, args: dict[str, Any]) -> tuple[Any, bool]:
        try:
            return aws_call(tool, args), True
        except Exception as exc:  # a dead connection must not kill the assessment
            unchecked.append(f"{tool}({args}): {exc}")
            return None, False

    # --- S3: public access and encryption ------------------------------------------------
    listing, ok = call("s3_list_buckets", {})
    if ok and not _is_listing_shape(listing, wrapper_key="buckets"):
        unchecked.append(f"s3_list_buckets({{}}): unexpected response shape: {listing!r}")
        ok = False
    buckets = _bucket_names(listing) if ok else []
    for bucket in buckets[:_MAX_BUCKETS]:
        policy, ok = call("s3_get_bucket_policy", {"bucket": bucket})
        if ok and any(
            s.get("Effect") == "Allow" and _is_public_principal(s.get("Principal"))
            for s in _statements(policy if isinstance(policy, dict) else None)
        ):
            result.findings.append(
                Finding(
                    dimension="cloud_posture",
                    severity=Severity.CRITICAL,
                    title=f"S3 bucket `{bucket}` is publicly accessible",
                    detail=(
                        "Its bucket policy allows Principal `*` — anyone on the internet can "
                        "exercise the allowed actions. If this holds client data, it is an "
                        "active exposure, not a hardening gap."
                    ),
                    remediation=(
                        "Remove the public statement (or scope it to specific principals) and "
                        "enable account-level S3 Block Public Access."
                    ),
                    offering=_OFFERING_CLOUD_SECURITY,
                    subject=bucket,
                    evidence=EvidenceType.SYSTEM_OF_RECORD,
                )
            )

        encryption, ok = call("s3_get_bucket_encryption", {"bucket": bucket})
        if ok and not encryption:
            result.findings.append(
                Finding(
                    dimension="cloud_posture",
                    severity=Severity.HIGH,
                    title=f"S3 bucket `{bucket}` has no server-side encryption configured",
                    detail=(
                        "No default encryption configuration is set, so objects land "
                        "unencrypted unless every writer opts in per request."
                    ),
                    remediation="Set default bucket encryption (SSE-KMS preferred) and verify existing objects.",
                    offering=_OFFERING_CLOUD_SECURITY,
                    subject=bucket,
                    evidence=EvidenceType.SYSTEM_OF_RECORD,
                )
            )

    # --- IAM: over-broad customer-managed policies ----------------------------------------
    listing, ok = call("iam_list_policies", {"scope": "Local"})
    if ok and not _is_listing_shape(listing, wrapper_key="policies"):
        unchecked.append(f"iam_list_policies({{'scope': 'Local'}}): unexpected response shape: {listing!r}")
        ok = False
    policies = _policy_records(listing) if ok else []
    star_policies = 0
    for record in policies[:_MAX_POLICIES]:
        name = str(record.get("name") or record.get("arn") or "unnamed-policy")
        document, ok = call("iam_get_policy_document", {"arn": record.get("arn", name)})
        if ok and any(_allows_star_on_star(s) for s in _statements(document)):
            star_policies += 1
            result.findings.append(
                Finding(
                    dimension="cloud_posture",
                    severity=Severity.HIGH,
                    title=f"IAM policy `{name}` allows `*` on `*`",
                    detail=(
                        "A customer-managed policy grants every action on every resource — "
                        "any principal it attaches to is a full account administrator."
                    ),
                    remediation="Replace with least-privilege statements scoped to the services actually used.",
                    offering=_OFFERING_CLOUD_SECURITY,
                    subject=name,
                    evidence=EvidenceType.SYSTEM_OF_RECORD,
                )
            )

    if unchecked:
        result.findings.append(
            Finding(
                dimension="cloud_posture",
                severity=Severity.INFO,
                title=f"{len(unchecked)} posture check(s) could not be completed",
                detail=(
                    "Some MCP calls failed, so those checks are unverified — not passed: "
                    + "; ".join(unchecked[:3])
                    + ("…" if len(unchecked) > 3 else "")
                ),
                remediation="Re-run once the aws MCP connection/role covers these calls.",
                evidence=EvidenceType.SYSTEM_OF_RECORD,
            )
        )

    result.stats = {
        "buckets_checked": min(len(buckets), _MAX_BUCKETS),
        "policies_checked": min(len(policies), _MAX_POLICIES),
        "over_broad_policies": star_policies,
        "unchecked_calls": len(unchecked),
    }
    return result
