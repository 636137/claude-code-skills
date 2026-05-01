#!/usr/bin/env python3
"""Lightweight eval harness — invoke a deployed Bedrock Prompt Flow against
a YAML list of golden cases and assert the expected Output node fired.

Usage:
    python3 harness.py --goldens evals/snap-intake/goldens.yaml
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import boto3
import yaml


def run_case(client, flow_id: str, alias_id: str, case: dict) -> dict:
    resp = client.invoke_flow(
        flowIdentifier=flow_id,
        flowAliasIdentifier=alias_id,
        inputs=[{
            "nodeName": "FlowInput",
            "nodeOutputName": "document",
            "content": {"document": case["input"]},
        }],
        executionId=str(uuid.uuid4()),
    )
    fired_node = None
    for event in resp["responseStream"]:
        if "flowOutputEvent" in event:
            fired_node = event["flowOutputEvent"].get("nodeName")
            break
    return {
        "name": case["name"],
        "expected": case.get("expected_output_node") or case.get("expected_verdict"),
        "actual": fired_node,
        "pass": fired_node == case.get("expected_output_node"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldens", required=True, type=Path)
    args = parser.parse_args(argv)

    with args.goldens.open() as f:
        cfg = yaml.safe_load(f)

    client = boto3.client("bedrock-agent-runtime", region_name=cfg.get("region", "us-east-1"))

    results = []
    for case in cfg["cases"]:
        results.append(run_case(client, cfg["flow_id"], cfg["alias_id"], case))

    width_name = max(len(r["name"]) for r in results) + 2
    width_exp = max(len(str(r["expected"])) for r in results) + 2
    width_act = max(len(str(r["actual"] or "(none)")) for r in results) + 2

    print(f"{'case':<{width_name}}{'expected':<{width_exp}}{'actual':<{width_act}}status")
    print("-" * (width_name + width_exp + width_act + 6))
    passed = 0
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        if r["pass"]:
            passed += 1
        print(f"{r['name']:<{width_name}}{str(r['expected']):<{width_exp}}{str(r['actual'] or '(none)'):<{width_act}}{status}")
    print("-" * (width_name + width_exp + width_act + 6))
    print(f"{passed}/{len(results)} passing")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
