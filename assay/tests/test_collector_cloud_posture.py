"""Test the cloud-posture collector — the Phase 2 acceptance case: a connected-mode,
out-of-list dimension implemented as a thin caller of the shared `aws` MCP server.

The collector takes an injected tool caller, so these tests fake the MCP surface with plain
dicts shaped like the server's tool results. No boto3, no network, no credentials.
"""

from qbiz_assay.collectors import cloud_posture
from qbiz_assay.findings import EvidenceType, Severity

PUBLIC_POLICY = {
    "Statement": [
        {"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "*"}
    ]
}
PRIVATE_POLICY = {
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "arn:aws:iam::111122223333:role/app"},
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::good-bucket/*",
        }
    ]
}
ENCRYPTED = {"rules": [{"sse_algorithm": "aws:kms"}]}
ADMIN_DOCUMENT = {
    "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]
}
SCOPED_DOCUMENT = {
    "Statement": [{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::x/*"}]
}


def _fake_aws(responses: dict[tuple[str, str], object], default: object = None):
    """A tool caller keyed on (tool, bucket-or-arn); unkeyed tools use `default`."""

    def call(tool: str, args: dict) -> object:
        key = (tool, str(args.get("bucket") or args.get("arn") or ""))
        if key in responses:
            value = responses[key]
        elif (tool, "") in responses:
            value = responses[(tool, "")]
        else:
            value = default
        if isinstance(value, Exception):
            raise value
        return value

    return call


class TestS3Checks:
    def test_public_bucket_yields_critical_finding(self):
        aws = _fake_aws(
            {
                ("s3_list_buckets", ""): ["open-bucket"],
                ("s3_get_bucket_policy", "open-bucket"): PUBLIC_POLICY,
                ("s3_get_bucket_encryption", "open-bucket"): ENCRYPTED,
                ("iam_list_policies", ""): [],
            }
        )
        result = cloud_posture.collect(aws)
        [finding] = [f for f in result.findings if f.severity is Severity.CRITICAL]
        assert "open-bucket" in finding.title
        assert "publicly accessible" in finding.title
        assert finding.dimension == "cloud_posture"
        assert finding.evidence is EvidenceType.SYSTEM_OF_RECORD

    def test_private_encrypted_bucket_yields_no_findings(self):
        aws = _fake_aws(
            {
                ("s3_list_buckets", ""): [{"name": "good-bucket"}],
                ("s3_get_bucket_policy", "good-bucket"): PRIVATE_POLICY,
                ("s3_get_bucket_encryption", "good-bucket"): ENCRYPTED,
                ("iam_list_policies", ""): [],
            }
        )
        result = cloud_posture.collect(aws)
        assert result.findings == []
        assert result.stats["buckets_checked"] == 1

    def test_missing_encryption_yields_high_finding(self):
        aws = _fake_aws(
            {
                ("s3_list_buckets", ""): ["plain-bucket"],
                ("s3_get_bucket_policy", "plain-bucket"): PRIVATE_POLICY,
                ("s3_get_bucket_encryption", "plain-bucket"): None,
                ("iam_list_policies", ""): [],
            }
        )
        result = cloud_posture.collect(aws)
        [finding] = result.findings
        assert finding.severity is Severity.HIGH
        assert "encryption" in finding.title


class TestIamChecks:
    def test_star_on_star_policy_yields_high_finding(self):
        aws = _fake_aws(
            {
                ("s3_list_buckets", ""): [],
                ("iam_list_policies", ""): [
                    {"name": "AdminEverything", "arn": "arn:aws:iam::1:policy/AdminEverything"},
                    {"name": "ScopedRead", "arn": "arn:aws:iam::1:policy/ScopedRead"},
                ],
                ("iam_get_policy_document", "arn:aws:iam::1:policy/AdminEverything"): ADMIN_DOCUMENT,
                ("iam_get_policy_document", "arn:aws:iam::1:policy/ScopedRead"): SCOPED_DOCUMENT,
            }
        )
        result = cloud_posture.collect(aws)
        [finding] = result.findings
        assert "AdminEverything" in finding.title
        assert result.stats["over_broad_policies"] == 1


class TestFailureHonesty:
    def test_failed_calls_become_an_unchecked_finding_not_a_pass(self):
        aws = _fake_aws(
            {
                ("s3_list_buckets", ""): ["locked-bucket"],
                ("s3_get_bucket_policy", "locked-bucket"): RuntimeError("AccessDenied"),
                ("s3_get_bucket_encryption", "locked-bucket"): RuntimeError("AccessDenied"),
                ("iam_list_policies", ""): [],
            }
        )
        result = cloud_posture.collect(aws)
        # No posture findings fabricated from failed calls...
        assert all(f.severity is Severity.INFO for f in result.findings)
        # ...but the gap is disclosed, not silently passed.
        [unchecked] = result.findings
        assert "could not be completed" in unchecked.title
        assert result.stats["unchecked_calls"] == 2

    def test_dead_connection_never_raises(self):
        def dead(_tool: str, _args: dict) -> object:
            raise ConnectionError("mcp server unreachable")

        result = cloud_posture.collect(dead)
        assert result.stats["buckets_checked"] == 0
        [unchecked] = result.findings
        assert unchecked.severity is Severity.INFO
