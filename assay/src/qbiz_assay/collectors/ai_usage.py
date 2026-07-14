"""AI-usage collector — finds where the client already calls LLMs, and what (if anything)
governs those calls.

This is the headline scan for AI-forward prospects: most companies have more ungoverned LLM
usage than they think — a data scientist's notebook here, a support script there — with no
cost caps, no audit trail, and occasionally a hardcoded API key. Detection is import-based
(which provider SDKs appear) plus a light credential regex; it deliberately errs toward
"worth a human look" rather than exhaustive.

Also owns the repo-wide hardcoded-credential scan (governance) — it walks every Python file
anyway, and keeping the scan in one collector avoids duplicate findings.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from qbiz_assay.collectors import AcquisitionMode, CollectorResult, collector
from qbiz_assay.findings import Finding, Severity

_DIMENSIONS = {"ai_governance", "governance"}

_OFFERING_HARNESS = "agent_harness"
_OFFERING_ADVISORY = "ai_advisory"

NAME = "ai-usage"

#: Import prefixes that indicate a direct LLM call site.
_PROVIDER_MODULES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
    "litellm",
    "langchain",
    "langchain_openai",
    "langchain_anthropic",
    "pydantic_ai",
    "cohere",
    "mistralai",
    "ollama",
)

#: Imports that indicate the call site runs under governance.
_GOVERNANCE_MODULES = ("qbiz_harness",)

_SKIP_DIRS = {".git", ".venv", "venv", ".varve", "node_modules", "__pycache__", "site-packages", ".pytest_cache"}

# No leading \b: names like `ftp_password` have no word boundary before "password".
_CREDENTIAL_RE = re.compile(
    r"""(?ix)(?:api_key|apikey|auth_token|password|secret)\s*=\s*['"][^'"]{8,}['"]"""
)
_KEY_LITERAL_RE = re.compile(r"sk-[A-Za-z0-9_\-]{12,}")


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _matches(modules: set[str], prefixes: tuple[str, ...]) -> set[str]:
    hits: set[str] = set()
    for module in modules:
        for prefix in prefixes:
            if module == prefix or module.startswith(prefix + "."):
                hits.add(prefix)
    return hits


@collector(
    name=NAME,
    dimensions=_DIMENSIONS,
    mode=AcquisitionMode.ARTIFACT,
    inputs={"repo_dir": "path to a repo checkout to scan (read access only)"},
    description="Where the client already calls LLMs and what governs those calls: provider "
    "SDK imports, governance-layer presence, hardcoded-credential scan.",
)
def collect(repo_dir: Path | str) -> CollectorResult:
    result = CollectorResult(name=NAME, dimensions=set(_DIMENSIONS))
    repo_dir = Path(repo_dir)

    files = [
        p
        for p in sorted(repo_dir.rglob("*.py"))
        if not any(part in _SKIP_DIRS for part in p.parts)
    ]

    llm_files: list[str] = []
    governed_files: list[str] = []
    credential_files: list[str] = []
    providers_seen: set[str] = set()

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(repo_dir))

        if _CREDENTIAL_RE.search(text) or _KEY_LITERAL_RE.search(text):
            credential_files.append(rel)

        try:
            modules = _imported_modules(ast.parse(text, filename=str(path)))
        except SyntaxError:
            continue

        providers = _matches(modules, _PROVIDER_MODULES)
        if providers:
            providers_seen.update(providers)
            llm_files.append(rel)
            if _matches(modules, _GOVERNANCE_MODULES):
                governed_files.append(rel)

    ungoverned = [f for f in llm_files if f not in governed_files]

    result.stats = {
        "python_files": len(files),
        "llm_call_sites": len(llm_files),
        "governed_call_sites": len(governed_files),
        "providers": sorted(providers_seen),
        "files_with_hardcoded_credentials": len(credential_files),
    }

    for rel in credential_files[:5]:
        result.findings.append(
            Finding(
                dimension="governance",
                severity=Severity.CRITICAL,
                title=f"Hardcoded credential in {rel}",
                detail="A secret is committed in source. Anyone with repo access has it; so does the git history.",
                remediation="Rotate the credential now; move secrets to a manager and inject via environment.",
                subject=rel,
            )
        )

    if ungoverned:
        shown = ", ".join(ungoverned[:5])
        extra = len(ungoverned) - 5
        result.findings.append(
            Finding(
                dimension="ai_governance",
                severity=Severity.HIGH,
                title=f"{len(ungoverned)} ungoverned LLM call site(s)",
                detail=(
                    f"Files calling provider SDKs directly with no governance layer: {shown}"
                    f"{f' (+{extra} more)' if extra > 0 else ''}. No cost caps, no loop bounds, "
                    "no audit trail — each one is an unbounded spend and data-exposure surface."
                ),
                remediation=(
                    "Route LLM calls through an enforcement harness: token/spend caps, loop "
                    "guards, output validation, and an append-only audit log."
                ),
                offering=_OFFERING_HARNESS,
            )
        )
        if not governed_files:
            result.findings.append(
                Finding(
                    dimension="ai_governance",
                    severity=Severity.MEDIUM,
                    title="No AI audit trail exists anywhere in the estate",
                    detail=(
                        "None of the detected LLM usage records what was asked, what was "
                        "returned, or what it cost. 'What did the AI do last month?' is "
                        "currently unanswerable."
                    ),
                    remediation="Adopt a shared audit log for all agent activity before usage grows.",
                    offering=_OFFERING_HARNESS,
                )
            )
    elif not llm_files:
        result.findings.append(
            Finding(
                dimension="ai_governance",
                severity=Severity.INFO,
                title="No direct LLM usage detected — greenfield",
                detail=(
                    "No provider SDK imports found. Adoption hasn't started (or lives outside "
                    "this repo) — the cheapest moment to adopt governed-by-default patterns."
                ),
                remediation="Start with a governed reference agent rather than retrofitting controls later.",
                offering=_OFFERING_ADVISORY,
            )
        )

    return result
