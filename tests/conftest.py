"""Shared fixtures: run the scaffolder against each example spec once per session."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLDER = REPO_ROOT / "skills" / "bedrock-flow-scaffolder" / "scaffolder.py"
EXAMPLES = REPO_ROOT / "examples"


def _scaffold(spec_name: str, tmp_path: Path) -> Path:
    out = tmp_path / spec_name.replace(".yaml", "")
    if out.exists():
        shutil.rmtree(out)
    result = subprocess.run(
        [sys.executable, str(SCAFFOLDER),
         "--spec", str(EXAMPLES / spec_name),
         "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"scaffolder failed: {result.stderr}"
    return out


@pytest.fixture(scope="session")
def snap_tree(tmp_path_factory) -> Path:
    return _scaffold("snap-intake.yaml", tmp_path_factory.mktemp("snap"))


@pytest.fixture(scope="session")
def va_tree(tmp_path_factory) -> Path:
    return _scaffold("va-eligibility.yaml", tmp_path_factory.mktemp("va"))


@pytest.fixture(scope="session")
def telco_tree(tmp_path_factory) -> Path:
    return _scaffold("telco-care.yaml", tmp_path_factory.mktemp("telco"))


@pytest.fixture(scope="session")
def cpg_tree(tmp_path_factory) -> Path:
    return _scaffold("cpg-it-helpdesk.yaml", tmp_path_factory.mktemp("cpg"))


@pytest.fixture(scope="session")
def retail_tree(tmp_path_factory) -> Path:
    return _scaffold("retail-store-ops.yaml", tmp_path_factory.mktemp("retail"))
