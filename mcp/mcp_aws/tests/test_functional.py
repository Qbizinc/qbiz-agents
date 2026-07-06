"""Functional tests — hit real AWS (requires valid credentials and role).

Run with:
    AWS_READONLY_ROLE_ARN=arn:... uv run pytest tests/test_functional.py -v
Or, if you have the env vars already set:
    uv run pytest tests/test_functional.py -v

These tests are skipped automatically when AWS_READONLY_ROLE_ARN is not set,
so they won't break CI environments that lack credentials.
"""

from __future__ import annotations

import json
import os

import pytest

# Skip every test in this module if the required env var is absent.
pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_READONLY_ROLE_ARN"),
    reason="AWS_READONLY_ROLE_ARN not set — skipping functional tests",
)


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------
class TestS3Functional:
    def test_list_buckets_contains_qbiz_users(self):
        from aws_readonly_mcp.server import s3_list_buckets

        result = json.loads(s3_list_buckets())

        assert "buckets" in result, f"Unexpected response shape: {result}"
        names = [b["name"] for b in result["buckets"]]
        assert "qbiz-users" in names, (
            f"Expected bucket 'qbiz-users' not found. Buckets returned: {names}"
        )
