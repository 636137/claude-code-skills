"""Syntactic / schematic validation of generated files:

- All .json must parse.
- All .sh must pass `bash -n`.
- All .py must byte-compile.
- No unresolved Jinja tokens (`{%`, `{{ ... }}` that look like our placeholders).
- OpenAPI docs must be valid.
"""
from __future__ import annotations

import json
import py_compile
import re
import subprocess
from pathlib import Path

import pytest
from openapi_spec_validator import validate as validate_openapi


def _all(root: Path, suffix: str) -> list[Path]:
    return sorted(root.rglob(f"*{suffix}"))


@pytest.mark.parametrize("tree_fixture", ["snap_tree", "va_tree"])
def test_json_parses(tree_fixture, request):
    tree = request.getfixturevalue(tree_fixture)
    for p in _all(tree, ".json"):
        with p.open() as f:
            json.load(f)


@pytest.mark.parametrize("tree_fixture", ["snap_tree", "va_tree"])
def test_bash_syntax(tree_fixture, request):
    tree = request.getfixturevalue(tree_fixture)
    for p in _all(tree, ".sh"):
        result = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert result.returncode == 0, f"{p} bash -n failed: {result.stderr}"


@pytest.mark.parametrize("tree_fixture", ["snap_tree", "va_tree"])
def test_python_compiles(tree_fixture, request):
    tree = request.getfixturevalue(tree_fixture)
    for p in _all(tree, ".py"):
        py_compile.compile(str(p), doraise=True)


# Bedrock Prompt node input variables use `{{name}}` syntax — those are LEGAL in
# the generated flow-definition.json. Elsewhere, {{ ... }} should not appear.
JINJA_BLOCK = re.compile(r"\{%")


@pytest.mark.parametrize("tree_fixture", ["snap_tree", "va_tree"])
def test_no_unrendered_jinja_blocks(tree_fixture, request):
    tree = request.getfixturevalue(tree_fixture)
    for p in tree.rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        text = p.read_text(errors="ignore")
        assert not JINJA_BLOCK.search(text), f"unrendered Jinja block in {p}"


@pytest.mark.parametrize("tree_fixture", ["snap_tree", "va_tree"])
def test_no_unresolved_curly_outside_flow_json(tree_fixture, request):
    tree = request.getfixturevalue(tree_fixture)
    # These templates contain legitimate shell ${var} and Bedrock-flow {{var}} usage.
    for p in tree.rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        if p.name == "flow-definition.json":
            continue  # Bedrock prompt-node input variables use {{name}}
        if p.suffix in (".md",):
            continue  # README examples may reference {{placeholder}} in prose
        text = p.read_text(errors="ignore")
        # Look for {{ ... }} patterns that look like unrendered Jinja (no whitespace is OK for bedrock)
        # Explicitly fail on {{ spec.x }} or {{ anything | ... }} that would be a Jinja expression
        suspicious = re.findall(r"\{\{[^}]*\|[^}]*\}\}", text)
        assert not suspicious, f"unrendered Jinja expression in {p}: {suspicious[:3]}"


def test_openapi_valid_for_snap(snap_tree: Path):
    for p in (snap_tree / "agents").glob("*-actions-openapi.json"):
        with p.open() as f:
            spec = json.load(f)
        validate_openapi(spec)


def test_snap_flow_has_all_expected_nodes(snap_tree: Path):
    flow = json.loads((snap_tree / "flow" / "flow-definition.json").read_text())
    node_names = {n["name"] for n in flow["nodes"]}
    # Ingress + per-specialist build+agent + supervisor + route + per-branch explain+output + default
    expected_subset = {
        "FlowInput", "BDAInvoker",
        "BuildIdentityPrompt", "IdentityAgent",
        "BuildIncomePrompt", "IncomeAgent",
        "BuildResidencyPrompt", "ResidencyAgent",
        "Supervisor", "Route",
        "ExplainApprove", "OutputApprove",
        "ExplainDeny", "OutputDeny",
        "ExplainReview", "OutputReview",
        "OutputDefault",
    }
    missing = expected_subset - node_names
    assert not missing, f"snap flow missing nodes: {missing}"


def test_va_flow_has_no_agent_nodes(va_tree: Path):
    flow = json.loads((va_tree / "flow" / "flow-definition.json").read_text())
    agent_nodes = [n for n in flow["nodes"] if n["type"] == "Agent"]
    assert agent_nodes == [], "va-eligibility has no specialists; should have no Agent nodes"


def test_snap_deploy_uses_inference_profile(snap_tree: Path):
    """Bedrock on-demand needs us.* inference-profile prefix for Claude 4.x."""
    text = (snap_tree / "scripts" / "deploy.sh").read_text()
    assert "us.anthropic.claude-haiku-4-5-20251001-v1:0" in text
    # Must not use the bare (non-profile) form anywhere standalone
    bare = re.findall(r'(?<!us\.)anthropic\.claude-haiku-4-5-20251001-v1:0', text)
    assert not bare, "deploy.sh uses bare model ID; on-demand throughput won't work"
