"""Read-only MCP server for AWS S3, Redshift, and IAM.

Exposes list/describe/get tools only. No tool in this server performs a
mutating AWS API call. Authentication is handled in ``aws_session`` via STS
AssumeRole into a read-only role.
"""

from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from mcp.server.fastmcp import FastMCP

from .aws_session import ConfigError, json_default, manager

mcp = FastMCP("aws-readonly")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _ok(data: Any) -> str:
    return json.dumps(data, default=json_default, indent=2)


def _err(action: str, exc: Exception) -> str:
    if isinstance(exc, ClientError):
        err = exc.response.get("Error", {})
        payload = {
            "error": err.get("Code", "ClientError"),
            "message": err.get("Message", str(exc)),
            "action": action,
        }
    elif isinstance(exc, (ConfigError, BotoCoreError)):
        payload = {"error": type(exc).__name__, "message": str(exc), "action": action}
    else:
        payload = {"error": "UnexpectedError", "message": str(exc), "action": action}
    return json.dumps(payload, indent=2)


def _paginate(client, op: str, result_key: str, max_items: int, **kwargs) -> list:
    """Collect up to ``max_items`` results from a paginated operation."""
    items: list = []
    paginator = client.get_paginator(op)
    page_cfg = {"MaxItems": max_items} if max_items else {}
    for page in paginator.paginate(PaginationConfig=page_cfg, **kwargs):
        items.extend(page.get(result_key, []))
        if max_items and len(items) >= max_items:
            return items[:max_items]
    return items


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
@mcp.tool()
def whoami() -> str:
    """Return the AWS identity the server is operating as (the assumed role),
    via sts:GetCallerIdentity. Useful for confirming auth is configured."""
    try:
        return _ok(manager.whoami())
    except Exception as exc:  # noqa: BLE001
        return _err("sts:GetCallerIdentity", exc)


# --------------------------------------------------------------------------
# S3
# --------------------------------------------------------------------------
@mcp.tool()
def s3_list_buckets() -> str:
    """List all S3 buckets in the account."""
    try:
        resp = manager.client("s3").list_buckets()
        buckets = [
            {"name": b["Name"], "creation_date": b.get("CreationDate")}
            for b in resp.get("Buckets", [])
        ]
        return _ok({"buckets": buckets, "count": len(buckets)})
    except Exception as exc:  # noqa: BLE001
        return _err("s3:ListAllMyBuckets", exc)


@mcp.tool()
def s3_get_bucket_location(bucket: str) -> str:
    """Get the AWS region a bucket resides in."""
    try:
        resp = manager.client("s3").get_bucket_location(Bucket=bucket)
        region = resp.get("LocationConstraint") or "us-east-1"
        return _ok({"bucket": bucket, "region": region})
    except Exception as exc:  # noqa: BLE001
        return _err("s3:GetBucketLocation", exc)


@mcp.tool()
def s3_list_objects(
    bucket: str, prefix: str = "", max_keys: int = 100, continuation_token: str = ""
) -> str:
    """List objects in a bucket (optionally under a key prefix).

    Args:
        bucket: Bucket name.
        prefix: Only return keys beginning with this prefix.
        max_keys: Max objects to return (1-1000).
        continuation_token: Token from a previous call to fetch the next page.
    """
    try:
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "MaxKeys": max(1, min(int(max_keys), 1000)),
        }
        if prefix:
            kwargs["Prefix"] = prefix
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        resp = manager.client("s3").list_objects_v2(**kwargs)
        objects = [
            {
                "key": o["Key"],
                "size": o.get("Size"),
                "last_modified": o.get("LastModified"),
                "storage_class": o.get("StorageClass"),
                "etag": o.get("ETag"),
            }
            for o in resp.get("Contents", [])
        ]
        return _ok(
            {
                "bucket": bucket,
                "prefix": prefix,
                "objects": objects,
                "count": len(objects),
                "is_truncated": resp.get("IsTruncated", False),
                "next_continuation_token": resp.get("NextContinuationToken"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err("s3:ListBucket", exc)


@mcp.tool()
def s3_get_object_metadata(bucket: str, key: str) -> str:
    """Get an object's metadata (size, content-type, last modified, etc.)
    via a HEAD request. Does not download object contents."""
    try:
        resp = manager.client("s3").head_object(Bucket=bucket, Key=key)
        return _ok(
            {
                "bucket": bucket,
                "key": key,
                "content_length": resp.get("ContentLength"),
                "content_type": resp.get("ContentType"),
                "last_modified": resp.get("LastModified"),
                "etag": resp.get("ETag"),
                "storage_class": resp.get("StorageClass"),
                "server_side_encryption": resp.get("ServerSideEncryption"),
                "metadata": resp.get("Metadata", {}),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err("s3:GetObject (HEAD)", exc)


@mcp.tool()
def s3_get_bucket_policy(bucket: str) -> str:
    """Get the bucket policy (JSON) attached to a bucket, if any."""
    try:
        resp = manager.client("s3").get_bucket_policy(Bucket=bucket)
        policy = resp.get("Policy")
        try:
            policy = json.loads(policy) if policy else None
        except (TypeError, ValueError):
            pass
        return _ok({"bucket": bucket, "policy": policy})
    except Exception as exc:  # noqa: BLE001
        return _err("s3:GetBucketPolicy", exc)


@mcp.tool()
def s3_get_bucket_encryption(bucket: str) -> str:
    """Get the default server-side encryption configuration for a bucket."""
    try:
        resp = manager.client("s3").get_bucket_encryption(Bucket=bucket)
        return _ok(
            {
                "bucket": bucket,
                "rules": resp.get("ServerSideEncryptionConfiguration", {}).get(
                    "Rules", []
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err("s3:GetEncryptionConfiguration", exc)


# --------------------------------------------------------------------------
# Redshift
# --------------------------------------------------------------------------
@mcp.tool()
def redshift_describe_clusters(region: str = "", max_records: int = 100) -> str:
    """List/describe Redshift provisioned clusters in a region.

    Args:
        region: AWS region (defaults to the server's configured region).
        max_records: Max clusters to return.
    """
    try:
        client = manager.client("redshift", region=region or None)
        clusters = _paginate(client, "describe_clusters", "Clusters", max_records)
        summary = [
            {
                "cluster_identifier": c.get("ClusterIdentifier"),
                "node_type": c.get("NodeType"),
                "number_of_nodes": c.get("NumberOfNodes"),
                "cluster_status": c.get("ClusterStatus"),
                "db_name": c.get("DBName"),
                "endpoint": c.get("Endpoint"),
                "vpc_id": c.get("VpcId"),
                "encrypted": c.get("Encrypted"),
                "publicly_accessible": c.get("PubliclyAccessible"),
                "create_time": c.get("ClusterCreateTime"),
            }
            for c in clusters
        ]
        return _ok({"clusters": summary, "count": len(summary)})
    except Exception as exc:  # noqa: BLE001
        return _err("redshift:DescribeClusters", exc)


@mcp.tool()
def redshift_describe_cluster(cluster_identifier: str, region: str = "") -> str:
    """Get the full description of a single Redshift cluster."""
    try:
        client = manager.client("redshift", region=region or None)
        resp = client.describe_clusters(ClusterIdentifier=cluster_identifier)
        clusters = resp.get("Clusters", [])
        return _ok(clusters[0] if clusters else {})
    except Exception as exc:  # noqa: BLE001
        return _err("redshift:DescribeClusters", exc)


@mcp.tool()
def redshift_describe_cluster_snapshots(
    cluster_identifier: str = "", region: str = "", max_records: int = 100
) -> str:
    """List Redshift cluster snapshots, optionally filtered to one cluster."""
    try:
        client = manager.client("redshift", region=region or None)
        kwargs = {}
        if cluster_identifier:
            kwargs["ClusterIdentifier"] = cluster_identifier
        snaps = _paginate(
            client, "describe_cluster_snapshots", "Snapshots", max_records, **kwargs
        )
        summary = [
            {
                "snapshot_identifier": s.get("SnapshotIdentifier"),
                "cluster_identifier": s.get("ClusterIdentifier"),
                "status": s.get("Status"),
                "snapshot_type": s.get("SnapshotType"),
                "create_time": s.get("SnapshotCreateTime"),
                "encrypted": s.get("Encrypted"),
            }
            for s in snaps
        ]
        return _ok({"snapshots": summary, "count": len(summary)})
    except Exception as exc:  # noqa: BLE001
        return _err("redshift:DescribeClusterSnapshots", exc)


@mcp.tool()
def redshift_serverless_list_namespaces(region: str = "") -> str:
    """List Redshift Serverless namespaces in a region."""
    try:
        client = manager.client("redshift-serverless", region=region or None)
        items: list = []
        paginator = client.get_paginator("list_namespaces")
        for page in paginator.paginate():
            items.extend(page.get("namespaces", []))
        summary = [
            {
                "namespace_name": n.get("namespaceName"),
                "namespace_id": n.get("namespaceId"),
                "status": n.get("status"),
                "db_name": n.get("dbName"),
                "creation_date": n.get("creationDate"),
            }
            for n in items
        ]
        return _ok({"namespaces": summary, "count": len(summary)})
    except Exception as exc:  # noqa: BLE001
        return _err("redshift-serverless:ListNamespaces", exc)


@mcp.tool()
def redshift_serverless_list_workgroups(region: str = "") -> str:
    """List Redshift Serverless workgroups in a region."""
    try:
        client = manager.client("redshift-serverless", region=region or None)
        items: list = []
        paginator = client.get_paginator("list_workgroups")
        for page in paginator.paginate():
            items.extend(page.get("workgroups", []))
        summary = [
            {
                "workgroup_name": w.get("workgroupName"),
                "workgroup_id": w.get("workgroupId"),
                "status": w.get("status"),
                "namespace_name": w.get("namespaceName"),
                "endpoint": w.get("endpoint"),
            }
            for w in items
        ]
        return _ok({"workgroups": summary, "count": len(summary)})
    except Exception as exc:  # noqa: BLE001
        return _err("redshift-serverless:ListWorkgroups", exc)


# --------------------------------------------------------------------------
# IAM
# --------------------------------------------------------------------------
@mcp.tool()
def iam_list_roles(path_prefix: str = "/", max_items: int = 200) -> str:
    """List IAM roles, optionally filtered by path prefix."""
    try:
        client = manager.client("iam")
        roles = _paginate(
            client, "list_roles", "Roles", max_items, PathPrefix=path_prefix
        )
        summary = [
            {
                "role_name": r.get("RoleName"),
                "arn": r.get("Arn"),
                "path": r.get("Path"),
                "create_date": r.get("CreateDate"),
                "description": r.get("Description"),
                "max_session_duration": r.get("MaxSessionDuration"),
            }
            for r in roles
        ]
        return _ok({"roles": summary, "count": len(summary)})
    except Exception as exc:  # noqa: BLE001
        return _err("iam:ListRoles", exc)


@mcp.tool()
def iam_get_role(role_name: str) -> str:
    """Get a role's details, including its trust (assume-role) policy."""
    try:
        resp = manager.client("iam").get_role(RoleName=role_name)
        return _ok(resp.get("Role", {}))
    except Exception as exc:  # noqa: BLE001
        return _err("iam:GetRole", exc)


@mcp.tool()
def iam_list_role_policies(role_name: str) -> str:
    """List inline policy names embedded in a role, plus attached managed
    policy ARNs."""
    try:
        client = manager.client("iam")
        inline = _paginate(
            client, "list_role_policies", "PolicyNames", 0, RoleName=role_name
        )
        attached = _paginate(
            client,
            "list_attached_role_policies",
            "AttachedPolicies",
            0,
            RoleName=role_name,
        )
        return _ok(
            {
                "role_name": role_name,
                "inline_policies": inline,
                "attached_managed_policies": attached,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err("iam:ListRolePolicies", exc)


@mcp.tool()
def iam_get_role_inline_policy(role_name: str, policy_name: str) -> str:
    """Get the JSON document of an inline policy embedded in a role."""
    try:
        resp = manager.client("iam").get_role_policy(
            RoleName=role_name, PolicyName=policy_name
        )
        return _ok(
            {
                "role_name": role_name,
                "policy_name": resp.get("PolicyName"),
                "policy_document": resp.get("PolicyDocument"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err("iam:GetRolePolicy", exc)


@mcp.tool()
def iam_list_policies(
    scope: str = "Local", only_attached: bool = False, max_items: int = 200
) -> str:
    """List managed IAM policies.

    Args:
        scope: "Local" (customer-managed), "AWS" (AWS-managed), or "All".
        only_attached: If true, only return policies attached to an entity.
        max_items: Max policies to return.
    """
    try:
        client = manager.client("iam")
        policies = _paginate(
            client,
            "list_policies",
            "Policies",
            max_items,
            Scope=scope,
            OnlyAttached=only_attached,
        )
        summary = [
            {
                "policy_name": p.get("PolicyName"),
                "arn": p.get("Arn"),
                "path": p.get("Path"),
                "attachment_count": p.get("AttachmentCount"),
                "default_version_id": p.get("DefaultVersionId"),
                "create_date": p.get("CreateDate"),
                "update_date": p.get("UpdateDate"),
            }
            for p in policies
        ]
        return _ok({"policies": summary, "count": len(summary), "scope": scope})
    except Exception as exc:  # noqa: BLE001
        return _err("iam:ListPolicies", exc)


@mcp.tool()
def iam_get_policy(policy_arn: str) -> str:
    """Get a managed policy's metadata (name, default version, attachment count)."""
    try:
        resp = manager.client("iam").get_policy(PolicyArn=policy_arn)
        return _ok(resp.get("Policy", {}))
    except Exception as exc:  # noqa: BLE001
        return _err("iam:GetPolicy", exc)


@mcp.tool()
def iam_get_policy_document(policy_arn: str, version_id: str = "") -> str:
    """Get the JSON policy document for a managed policy. If version_id is
    omitted, the default version is used."""
    try:
        client = manager.client("iam")
        if not version_id:
            meta = client.get_policy(PolicyArn=policy_arn)
            version_id = meta["Policy"]["DefaultVersionId"]
        resp = client.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
        version = resp.get("PolicyVersion", {})
        return _ok(
            {
                "policy_arn": policy_arn,
                "version_id": version.get("VersionId"),
                "is_default": version.get("IsDefaultVersion"),
                "document": version.get("Document"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err("iam:GetPolicyVersion", exc)


def main() -> None:
    """Entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
