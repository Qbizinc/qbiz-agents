"""AWS session management via STS AssumeRole.

The server authenticates by assuming a (read-only) IAM role. Base credentials
come from the standard boto3 credential chain (env vars, shared config, an
attached instance/SSO role, etc.); those credentials are only used to call
``sts:AssumeRole`` into the target role configured below.

Configuration (environment variables):

  AWS_READONLY_ROLE_ARN   (required) ARN of the role to assume.
  AWS_READONLY_EXTERNAL_ID (optional) External ID, if the role's trust policy
                            requires one.
  AWS_READONLY_SESSION_NAME (optional) Role session name. Default: "aws-readonly-mcp".
  AWS_READONLY_REGION      (optional) Default region for service clients.
                            Falls back to AWS_REGION / AWS_DEFAULT_REGION.
  AWS_READONLY_DURATION    (optional) Requested session duration in seconds.
                            Default: 3600.
  AWS_PROFILE              (optional) Base profile used to source the
                            credentials that call AssumeRole.
"""

from __future__ import annotations

import datetime as _dt
import os
import threading

import boto3
from botocore.credentials import (
    DeferredRefreshableCredentials,
    create_assume_role_refresher,
)
from botocore.session import get_session as _get_botocore_session


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


class SessionManager:
    """Builds and caches a boto3 Session backed by auto-refreshing
    AssumeRole credentials, plus per-(service, region) client caching."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session: boto3.Session | None = None
        self._clients: dict[tuple[str, str | None], object] = {}
        self._default_region: str | None = None

    # -- configuration -----------------------------------------------------
    @staticmethod
    def _load_config() -> dict:
        role_arn = _env("AWS_READONLY_ROLE_ARN")
        if not role_arn:
            raise ConfigError(
                "AWS_READONLY_ROLE_ARN is not set. Set it to the ARN of the "
                "read-only IAM role this server should assume."
            )
        region = (
            _env("AWS_READONLY_REGION")
            or _env("AWS_REGION")
            or _env("AWS_DEFAULT_REGION")
        )
        try:
            duration = int(_env("AWS_READONLY_DURATION", "3600"))
        except ValueError as exc:
            raise ConfigError("AWS_READONLY_DURATION must be an integer.") from exc

        return {
            "role_arn": role_arn,
            "external_id": _env("AWS_READONLY_EXTERNAL_ID"),
            "session_name": _env("AWS_READONLY_SESSION_NAME", "aws-readonly-mcp"),
            "region": region,
            "duration": duration,
            "profile": _env("AWS_PROFILE"),
        }

    # -- session -----------------------------------------------------------
    def _build_session(self) -> boto3.Session:
        cfg = self._load_config()
        self._default_region = cfg["region"]

        # Single botocore session: sources the base credentials used to
        # AssumeRole, then has its credentials swapped for the assumed-role
        # ones. Reusing one session (rather than building a second one for
        # the returned boto3.Session) ensures profile-derived config (region,
        # S3 addressing style, retries, etc.) isn't silently dropped.
        base = _get_botocore_session()
        if cfg["profile"]:
            base.set_config_variable("profile", cfg["profile"])

        sts = base.create_client("sts", region_name=cfg["region"])

        assume_kwargs = {
            "RoleArn": cfg["role_arn"],
            "RoleSessionName": cfg["session_name"],
            "DurationSeconds": cfg["duration"],
        }
        if cfg["external_id"]:
            assume_kwargs["ExternalId"] = cfg["external_id"]

        refresher = create_assume_role_refresher(sts, assume_kwargs)
        creds = DeferredRefreshableCredentials(
            refresh_using=refresher, method="sts-assume-role"
        )

        base._credentials = creds
        if cfg["region"]:
            base.set_config_variable("region", cfg["region"])

        return boto3.Session(botocore_session=base)

    def session(self) -> boto3.Session:
        with self._lock:
            if self._session is None:
                self._session = self._build_session()
            return self._session

    # -- clients -----------------------------------------------------------
    def client(self, service: str, region: str | None = None):
        with self._lock:
            self.session()  # ensures _default_region is populated before use
            region = region or self._default_region
            key = (service, region)
            if key not in self._clients:
                self._clients[key] = self.session().client(
                    service, region_name=region
                )
            return self._clients[key]

    def whoami(self) -> dict:
        """Return the assumed identity (sts:GetCallerIdentity)."""
        ident = self.client("sts").get_caller_identity()
        return {
            "account": ident.get("Account"),
            "arn": ident.get("Arn"),
            "user_id": ident.get("UserId"),
            "default_region": self._default_region,
        }


# Module-level singleton used by the server.
manager = SessionManager()


def json_default(obj):
    """JSON serializer for boto3 return types (datetimes, etc.)."""
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.hex()
    return str(obj)
