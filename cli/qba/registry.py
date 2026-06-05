import os
import json
import httpx
import click
from pathlib import Path

# Set QBA_REGISTRY to a local repo path to bypass GitHub during development.
# e.g.: export QBA_REGISTRY=/path/to/qbiz-agents
LOCAL_REGISTRY = os.environ.get("QBA_REGISTRY")

_REF = os.environ.get("QBA_REF", "master")
_BASE = f"https://raw.githubusercontent.com/Qbizinc/qbiz-agents/{_REF}"
REGISTRY_URL = f"{_BASE}/skills-manifest.json"
SKILLS_BASE_URL = f"{_BASE}/skills"
MCP_BASE_URL = f"{_BASE}/mcp"

def fetch_manifest() -> dict:
    if LOCAL_REGISTRY:
        manifest_path = Path(LOCAL_REGISTRY) / "skills-manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text())
        raise click.ClickException(f"skills-manifest.json not found at {manifest_path}")

    try:
        r = httpx.get(REGISTRY_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise click.ClickException(f"Could not reach qbiz-agents registry: {e}")


def _fetch_checksums() -> dict:
    """Fetch checksums.sha256 from the repo. Returns {} if not available."""
    if LOCAL_REGISTRY:
        f = Path(LOCAL_REGISTRY) / "checksums.sha256"
        if not f.exists():
            return {}
        checksums = {}
        for line in f.read_text().splitlines():
            if line.strip():
                hash_, path = line.split(None, 1)
                checksums[path.strip()] = hash_
        return checksums
    try:
        r = httpx.get(f"{_BASE}/checksums.sha256", timeout=10)
        if r.status_code != 200:
            return {}
        checksums = {}
        for line in r.text.splitlines():
            if line.strip():
                hash_, path = line.split(None, 1)
                checksums[path.strip()] = hash_
        return checksums
    except Exception:
        return {}


def _verify(content: str, path: str, checksums: dict) -> bool:
    """Verify content matches expected checksum. Passes if no checksum found."""
    if not checksums or path not in checksums:
        return True
    import hashlib
    actual = hashlib.sha256(content.encode()).hexdigest()
    return actual == checksums[path]


def fetch_skill_files(skill_name: str, models: list) -> dict:
    """Fetch SKILL.md, SETUP.md, OWNERS.yaml and requested model sidecars."""
    files = {}
    checksums = _fetch_checksums()

    if LOCAL_REGISTRY:
        skill_dir = Path(LOCAL_REGISTRY) / "skills" / skill_name
        for filename in ["SKILL.md", "SETUP.md", "OWNERS.yaml"]:
            f = skill_dir / filename
            if f.exists():
                files[filename] = f.read_text()
        for model in models:
            sidecar = "CLAUDE.md" if model == "claude" else "GEMINI.md"
            f = skill_dir / sidecar
            if f.exists():
                files[sidecar] = f.read_text()
        return files

    for filename in ["SKILL.md", "SETUP.md", "OWNERS.yaml"]:
        path = f"skills/{skill_name}/{filename}"
        r = httpx.get(f"{SKILLS_BASE_URL}/{skill_name}/{filename}", timeout=10)
        if r.status_code == 200:
            if not _verify(r.text, path, checksums):
                raise click.ClickException(f"Checksum mismatch for {path} — file may have been tampered with.")
            files[filename] = r.text
    for model in models:
        sidecar = "CLAUDE.md" if model == "claude" else "GEMINI.md"
        path = f"skills/{skill_name}/{sidecar}"
        r = httpx.get(f"{SKILLS_BASE_URL}/{skill_name}/{sidecar}", timeout=10)
        if r.status_code == 200:
            if not _verify(r.text, path, checksums):
                raise click.ClickException(f"Checksum mismatch for {path} — file may have been tampered with.")
            files[sidecar] = r.text

    return files


def fetch_mcp_definition(mcp_name: str):
    folder = f"mcp_{mcp_name.replace('-', '_')}"

    if LOCAL_REGISTRY:
        mcp_path = Path(LOCAL_REGISTRY) / "mcp" / folder / "mcp.yaml"
        return mcp_path.read_text() if mcp_path.exists() else None

    url = f"{MCP_BASE_URL}/{folder}/mcp.yaml"
    r = httpx.get(url, timeout=10)
    return r.text if r.status_code == 200 else None
