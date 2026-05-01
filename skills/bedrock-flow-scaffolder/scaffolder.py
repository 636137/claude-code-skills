#!/usr/bin/env python3
"""Turn a YAML spec into a complete Bedrock Prompt Flow project tree.

Invocation:
    python3 scaffolder.py --spec spec.yaml --out ./my-project [--force]

No AWS calls. Pure file generation. See SKILL.md for spec schema.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"


# ----------------------------------------------------------------------------
# Spec loading + validation
# ----------------------------------------------------------------------------

REQUIRED_TOP_LEVEL = ["project_name", "region", "model_id", "ingress",
                      "supervisor", "router", "explainers"]
KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class SpecError(Exception):
    """Raised when the user's YAML spec is malformed."""


def load_spec(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    if not isinstance(spec, dict):
        raise SpecError("spec must be a YAML mapping at the top level")
    _validate(spec)
    _normalize(spec)
    return spec


def _validate(spec: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_TOP_LEVEL if k not in spec]
    if missing:
        raise SpecError(f"spec missing required keys: {', '.join(missing)}")

    name = spec["project_name"]
    if not isinstance(name, str) or not KEBAB_RE.match(name):
        raise SpecError(f"project_name must be kebab-case, got {name!r}")

    ingress = spec["ingress"]
    if not isinstance(ingress, dict) or "type" not in ingress:
        raise SpecError("ingress must be a mapping with a 'type' key")
    itype = ingress["type"]
    if itype not in ("bda", "lambda", "none"):
        raise SpecError(f"ingress.type must be bda|lambda|none, got {itype!r}")
    if itype == "bda" and not ingress.get("blueprints"):
        raise SpecError("ingress.type=bda requires non-empty 'blueprints'")
    if itype == "lambda":
        lam = ingress.get("lambda") or {}
        if not lam.get("name"):
            raise SpecError("ingress.type=lambda requires ingress.lambda.name")

    specialists = spec.get("specialists") or []
    if not isinstance(specialists, list):
        raise SpecError("specialists must be a list")
    for i, s in enumerate(specialists):
        if not isinstance(s, dict):
            raise SpecError(f"specialists[{i}] must be a mapping")
        for k in ("name", "instructions", "tools"):
            if not s.get(k):
                raise SpecError(f"specialists[{i}] missing '{k}'")
        if not isinstance(s["tools"], list) or not s["tools"]:
            raise SpecError(f"specialists[{i}].tools must be a non-empty list")
        for j, t in enumerate(s["tools"]):
            if not t.get("operation_id") or not t.get("description"):
                raise SpecError(f"specialists[{i}].tools[{j}] needs operation_id + description")

    router = spec["router"]
    branches = router.get("branches") or []
    if not isinstance(branches, list) or len(branches) < 2:
        raise SpecError("router.branches must be a list with at least 2 entries")
    for b in branches:
        if not isinstance(b, str) or not b.isupper():
            raise SpecError(f"router branches must be UPPERCASE strings; got {b!r}")

    explainers = spec["explainers"]
    if set(explainers.keys()) != set(branches):
        raise SpecError(
            f"explainers keys {sorted(explainers)} must exactly match router.branches {sorted(branches)}"
        )


def _normalize(spec: dict[str, Any]) -> None:
    """Fill in defaults and add derived fields templates expect."""
    spec.setdefault("specialists", [])

    # Snake case for resource names (lambda dir names, etc.)
    spec["project_snake"] = spec["project_name"].replace("-", "_")

    # Each specialist gets derived names
    for s in spec["specialists"]:
        s["snake"] = s["name"].replace("-", "_")
        s["agent_name"] = f"{spec['project_name']}-{s['name']}-agent"
        s["lambda_name"] = f"{spec['project_name']}-{s['name']}-actions"
        s["agent_token"] = s["name"].upper().replace("-", "_")  # for ${AGENT_X_ALIAS_ARN}

    # Ingress derived names
    ing = spec["ingress"]
    if ing["type"] == "bda":
        ing["lambda_name"] = f"{spec['project_name']}-bda-invoker"
        ing["lambda_dir"] = "bda_invoker"
        ing["bda_project_name"] = f"{spec['project_snake']}_project"
        for bp in ing["blueprints"]:
            bp["snake"] = bp["name"].replace("-", "_")
    elif ing["type"] == "lambda":
        lam = ing["lambda"]
        lam.setdefault("input_fields", [])
        lam.setdefault("description", "")
        ing["lambda_dir"] = lam["name"].replace("-", "_")

    # Supervisor defaults
    sup = spec["supervisor"]
    sup.setdefault("temperature", 0.0)
    sup.setdefault("max_tokens", 40)

    # Explainer defaults
    for _, ex in spec["explainers"].items():
        ex.setdefault("temperature", 0.3)
        ex.setdefault("max_tokens", 400)


# ----------------------------------------------------------------------------
# Template rendering
# ----------------------------------------------------------------------------

def _render_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=select_autoescape(enabled_extensions=(), default_for_string=False),
    )
    env.filters["tojson_indent"] = lambda v: json.dumps(v, indent=2)
    env.filters["tojson"] = json.dumps
    return env


def _write(out: Path, relpath: str, content: str, executable: bool = False) -> Path:
    dest = out / relpath
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    if executable:
        st = os.stat(dest)
        os.chmod(dest, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def scaffold(spec: dict[str, Any], out: Path) -> list[Path]:
    env = _render_env()
    written: list[Path] = []

    def render(template_name: str, **ctx: Any) -> str:
        tpl = env.get_template(template_name)
        return tpl.render(spec=spec, **ctx)

    # Top-level
    written.append(_write(out, "README.md", render("README.md.j2")))
    written.append(_write(out, ".gitignore", render("gitignore.j2")))

    # Flow definition
    written.append(_write(out, "flow/flow-definition.json",
                          render("flow-definition.json.j2")))

    # IAM
    for fname in ("lambda-trust-policy.json", "agent-trust-policy.json",
                  "agent-permissions-policy.json", "flow-trust-policy.json",
                  "flow-permissions-policy.json"):
        written.append(_write(out, f"iam/{fname}", render(f"iam/{fname}.j2")))

    # Ingress
    ing = spec["ingress"]
    if ing["type"] == "bda":
        for bp in ing["blueprints"]:
            written.append(_write(out, f"bda/blueprint-{bp['name']}.json",
                                  render("bda-blueprint.json.j2", blueprint=bp)))
        written.append(_write(out, f"lambda/{ing['lambda_dir']}/lambda_function.py",
                              render("bda-invoker-lambda.py.j2")))
        written.append(_write(out, "iam/bda-invoker-lambda-policy.json",
                              render("iam/bda-invoker-lambda-policy.json.j2")))
    elif ing["type"] == "lambda":
        written.append(_write(out, f"lambda/{ing['lambda_dir']}/lambda_function.py",
                              render("custom-ingress-lambda.py.j2")))

    # Specialists — agent instructions + OpenAPI + action-group Lambda
    for s in spec["specialists"]:
        written.append(_write(out, f"agents/{s['name']}-instructions.md",
                              render("agent-instructions.md.j2", specialist=s)))
        written.append(_write(out, f"agents/{s['name']}-actions-openapi.json",
                              render("agent-openapi.json.j2", specialist=s)))
        written.append(_write(out, f"lambda/{s['snake']}_actions/lambda_function.py",
                              render("action-lambda.py.j2", specialist=s)))

    # Scripts
    written.append(_write(out, "scripts/deploy.sh",
                          render("deploy.sh.j2"), executable=True))
    written.append(_write(out, "scripts/teardown.sh",
                          render("teardown.sh.j2"), executable=True))
    written.append(_write(out, "scripts/invoke_flow.py",
                          render("invoke_flow.py.j2"), executable=True))

    return written


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a Bedrock Prompt Flow project")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--force", action="store_true",
                        help="allow writing into a non-empty directory")
    args = parser.parse_args(argv)

    if not args.spec.is_file():
        print(f"spec file not found: {args.spec}", file=sys.stderr)
        return 1

    try:
        spec = load_spec(args.spec)
    except SpecError as e:
        print(f"spec validation failed: {e}", file=sys.stderr)
        return 1
    except yaml.YAMLError as e:
        print(f"spec YAML parse error: {e}", file=sys.stderr)
        return 1

    if args.out.exists() and any(args.out.iterdir()) and not args.force:
        print(f"output dir exists and is non-empty: {args.out} (pass --force)",
              file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    written = scaffold(spec, args.out)
    print(f"wrote {len(written)} files into {args.out}")
    for p in written:
        print(f"  {p.relative_to(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
