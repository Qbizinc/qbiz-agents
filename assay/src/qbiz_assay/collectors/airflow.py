"""Airflow collector — AST-scans DAG files for operational readiness.

Static analysis only: files are parsed, never imported or executed, so this runs on a client's
repo without their Airflow environment — and without triggering side effects (some clients'
DAG files do real work at import time, which is its own finding for a later pass).

Measures the incident-readiness basics: retries, failure callbacks (does a failure *go*
anywhere?), ownership, and unbounded catchup backfills (a cost problem, not an ops one).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from qbiz_assay.collectors import CollectorResult
from qbiz_assay.findings import (
    OFFERING_INCIDENT_AGENT,
    OFFERING_STARTUP_KIT,
    Dimension,
    Finding,
    Severity,
)

_DIMENSIONS = {Dimension.OPERATIONS, Dimension.COST}
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}

NAME = "airflow-dags"


def _const(node: ast.expr | None) -> object:
    """Best-effort literal value of an AST node; None when not a simple constant."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _dict_keys(node: ast.Dict) -> dict[str, ast.expr]:
    out: dict[str, ast.expr] = {}
    for key, value in zip(node.keys, node.values):
        name = _const(key)
        if isinstance(name, str):
            out[name] = value
    return out


@dataclass(slots=True)
class _DagInfo:
    dag_id: str
    path: Path
    default_args: dict[str, ast.expr] = field(default_factory=dict)
    kwargs: dict[str, ast.expr] = field(default_factory=dict)


def _resolve_default_args(
    node: ast.expr | None, module_dicts: dict[str, ast.Dict]
) -> dict[str, ast.expr]:
    """``default_args=`` is usually a dict literal or a module-level variable holding one."""
    if isinstance(node, ast.Name):
        node = module_dicts.get(node.id)
    if isinstance(node, ast.Dict):
        return _dict_keys(node)
    return {}


def _scan_file(path: Path) -> list[_DagInfo]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    module_dicts: dict[str, ast.Dict] = {}
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and isinstance(stmt.value, ast.Dict)
        ):
            module_dicts[stmt.targets[0].id] = stmt.value

    dags: list[_DagInfo] = []
    for node in ast.walk(tree):
        # Classic style: DAG(...) constructor (bare name or airflow.DAG attribute).
        if isinstance(node, ast.Call):
            func = node.func
            is_dag_call = (isinstance(func, ast.Name) and func.id == "DAG") or (
                isinstance(func, ast.Attribute) and func.attr == "DAG"
            )
            if not is_dag_call:
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            dag_id = None
            if node.args:
                dag_id = _const(node.args[0])
            if dag_id is None:
                dag_id = _const(kwargs.get("dag_id"))
            dags.append(
                _DagInfo(
                    dag_id=str(dag_id) if dag_id else path.stem,
                    path=path,
                    default_args=_resolve_default_args(kwargs.get("default_args"), module_dicts),
                    kwargs=kwargs,
                )
            )
        # TaskFlow style: @dag(...) decorated function.
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                call = dec if isinstance(dec, ast.Call) else None
                target = call.func if call is not None else dec
                is_dag_dec = (isinstance(target, ast.Name) and target.id == "dag") or (
                    isinstance(target, ast.Attribute) and target.attr == "dag"
                )
                if not is_dag_dec:
                    continue
                kwargs = (
                    {kw.arg: kw.value for kw in call.keywords if kw.arg} if call is not None else {}
                )
                dags.append(
                    _DagInfo(
                        dag_id=node.name,
                        path=path,
                        default_args=_resolve_default_args(
                            kwargs.get("default_args"), module_dicts
                        ),
                        kwargs=kwargs,
                    )
                )
    return dags


def collect(dags_dir: Path | str) -> CollectorResult:
    result = CollectorResult(name=NAME, dimensions=set(_DIMENSIONS))
    dags_dir = Path(dags_dir)

    files = [
        p
        for p in sorted(dags_dir.rglob("*.py"))
        if not any(part in _SKIP_DIRS for part in p.parts)
    ]

    dags: list[_DagInfo] = []
    for path in files:
        try:
            dags.extend(_scan_file(path))
        except (OSError, SyntaxError) as exc:
            result.findings.append(
                Finding(
                    dimension=Dimension.OPERATIONS,
                    severity=Severity.LOW,
                    title=f"Unparseable DAG file: {path.name}",
                    detail=f"{exc}",
                    remediation="Fix the syntax error; a file Airflow cannot import is a dead pipeline.",
                    subject=str(path),
                )
            )

    no_callback = 0
    for dag in dags:
        rel = dag.path.name

        retries = _const(dag.default_args.get("retries"))
        if "retries" not in dag.default_args or (isinstance(retries, int) and retries <= 0):
            result.findings.append(
                Finding(
                    dimension=Dimension.OPERATIONS,
                    severity=Severity.MEDIUM,
                    title=f"DAG `{dag.dag_id}` has no retries configured",
                    detail=f"({rel}) A transient blip becomes a hard failure and a human page.",
                    remediation="Set `retries` (with backoff) in default_args.",
                    offering=OFFERING_STARTUP_KIT,
                    subject=dag.dag_id,
                )
            )

        if "on_failure_callback" not in dag.kwargs and "on_failure_callback" not in dag.default_args:
            no_callback += 1
            result.findings.append(
                Finding(
                    dimension=Dimension.OPERATIONS,
                    severity=Severity.HIGH,
                    title=f"DAG `{dag.dag_id}` has no failure callback — failures go nowhere",
                    detail=(
                        f"({rel}) No on_failure_callback at the DAG or default_args level: a "
                        "failure produces no notification, no ticket, no incident record."
                    ),
                    remediation=(
                        "Wire on_failure_callback to an incident path — Qbiz's agentic incident "
                        "response investigates the failure, files the ticket, and notifies "
                        "on-call automatically."
                    ),
                    offering=OFFERING_INCIDENT_AGENT,
                    subject=dag.dag_id,
                )
            )

        owner = _const(dag.default_args.get("owner"))
        if not isinstance(owner, str) or owner.strip().lower() in ("", "airflow"):
            result.findings.append(
                Finding(
                    dimension=Dimension.OPERATIONS,
                    severity=Severity.LOW,
                    title=f"DAG `{dag.dag_id}` has no meaningful owner",
                    detail=f"({rel}) owner is missing or the default 'airflow' — nobody is on the hook.",
                    remediation="Set owner to a real team or rotation.",
                    subject=dag.dag_id,
                )
            )

        if _const(dag.kwargs.get("catchup")) is True:
            result.findings.append(
                Finding(
                    dimension=Dimension.COST,
                    severity=Severity.MEDIUM,
                    title=f"DAG `{dag.dag_id}` has catchup=True",
                    detail=(
                        f"({rel}) A deploy or unpause can trigger an unbounded historical "
                        "backfill — surprise compute spend."
                    ),
                    remediation="Set catchup=False unless backfill is genuinely intended; bound it if so.",
                    subject=dag.dag_id,
                )
            )

    result.stats = {
        "files_scanned": len(files),
        "dags": len(dags),
        "dags_without_failure_callback": no_callback,
    }
    return result
