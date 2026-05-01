"""File-tree assertions — ensure the scaffolder produces the expected layout."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLDER = REPO_ROOT / "skills" / "bedrock-flow-scaffolder" / "scaffolder.py"
EXAMPLES = REPO_ROOT / "examples"


SNAP_EXPECTED = {
    "README.md", ".gitignore",
    "flow/flow-definition.json",
    "iam/lambda-trust-policy.json",
    "iam/agent-trust-policy.json",
    "iam/agent-permissions-policy.json",
    "iam/flow-trust-policy.json",
    "iam/flow-permissions-policy.json",
    "iam/bda-invoker-lambda-policy.json",
    "bda/blueprint-id_document.json",
    "bda/blueprint-income_document.json",
    "bda/blueprint-residency_document.json",
    "lambda/bda_invoker/lambda_function.py",
    "agents/identity-instructions.md",
    "agents/identity-actions-openapi.json",
    "lambda/identity_actions/lambda_function.py",
    "agents/income-instructions.md",
    "agents/income-actions-openapi.json",
    "lambda/income_actions/lambda_function.py",
    "agents/residency-instructions.md",
    "agents/residency-actions-openapi.json",
    "lambda/residency_actions/lambda_function.py",
    "scripts/deploy.sh",
    "scripts/teardown.sh",
    "scripts/invoke_flow.py",
}

VA_EXPECTED = {
    "README.md", ".gitignore",
    "flow/flow-definition.json",
    "iam/lambda-trust-policy.json",
    "iam/agent-trust-policy.json",
    "iam/agent-permissions-policy.json",
    "iam/flow-trust-policy.json",
    "iam/flow-permissions-policy.json",
    "lambda/ingress/lambda_function.py",
    "scripts/deploy.sh",
    "scripts/teardown.sh",
    "scripts/invoke_flow.py",
}


def _relfiles(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_snap_tree_layout(snap_tree: Path):
    assert _relfiles(snap_tree) == SNAP_EXPECTED


def test_va_tree_layout(va_tree: Path):
    assert _relfiles(va_tree) == VA_EXPECTED


def test_scripts_executable(snap_tree: Path):
    import os, stat
    for name in ("deploy.sh", "teardown.sh", "invoke_flow.py"):
        p = snap_tree / "scripts" / name
        mode = p.stat().st_mode
        assert mode & stat.S_IXUSR, f"{name} should be executable"


def test_rejects_missing_required_keys(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("project_name: foo\n")
    result = subprocess.run(
        [sys.executable, str(SCAFFOLDER), "--spec", str(bad), "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "missing required keys" in result.stderr


def test_rejects_non_kebab_project_name(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "project_name: FooBar\n"
        "region: us-east-1\n"
        "model_id: us.anthropic.claude-haiku-4-5-20251001-v1:0\n"
        "ingress: {type: none}\n"
        "supervisor: {temperature: 0, max_tokens: 40, fusion_rules: x}\n"
        "router: {branches: [A, B]}\n"
        "explainers: {A: {temperature: 0, max_tokens: 10, instructions: x}, B: {temperature: 0, max_tokens: 10, instructions: x}}\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCAFFOLDER), "--spec", str(bad), "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "kebab-case" in result.stderr


def test_rejects_branches_not_matching_explainers(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "project_name: foo\n"
        "region: us-east-1\n"
        "model_id: us.anthropic.claude-haiku-4-5-20251001-v1:0\n"
        "ingress: {type: none}\n"
        "supervisor: {temperature: 0, max_tokens: 40, fusion_rules: x}\n"
        "router: {branches: [APPROVE, DENY]}\n"
        "explainers: {APPROVE: {temperature: 0, max_tokens: 10, instructions: x}}\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCAFFOLDER), "--spec", str(bad), "--out", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "router.branches" in result.stderr
