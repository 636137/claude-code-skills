---
name: bedrock-flow-eval
description: Lightweight eval harness for Bedrock Prompt Flows — golden inputs + expected verdicts, pass/fail scoring. Use after a flow is deployed to lock in behavior before prompts evolve.
---

# bedrock-flow-eval

A minimal eval harness for Bedrock Prompt Flows. Not a model-eval framework — just enough to regression-test a deployed flow against known-good cases.

## Layout

Create `evals/<flow>/` with:

```
evals/<flow>/
├── goldens.yaml        # list of cases + expected verdicts
└── (report generated per run)
```

Example `goldens.yaml`:

```yaml
flow_id: XISOE9J6CY
alias_id: 0CI06P9EGZ
region: us-east-1

cases:
  - name: clean
    input:
      case_id: SNAP-2001
      household_size: "1"
      s3_bucket: snap-intake-123456789012-us-east-1
      s3_prefix: cases/SNAP-2001/
    expected_verdict: APPROVE
    expected_output_node: OutputApprove

  - name: review
    input:
      case_id: SNAP-2002
      household_size: "2"
      s3_bucket: snap-intake-123456789012-us-east-1
      s3_prefix: cases/SNAP-2002/
    expected_verdict: REVIEW
    expected_output_node: OutputReview
```

## Run

```bash
python3 harness.py --goldens evals/snap-intake/goldens.yaml
```

The harness invokes the flow for each case, captures which Output node fires, and reports:

```
case              expected    actual      status
---------------   ---------   ---------   ------
clean             APPROVE     APPROVE     PASS
review            REVIEW      REVIEW      PASS
deny              DENY        DENY        PASS
---------------------------------------------
3/3 passing   FPR=0.00   FNR=0.00
```

Exit code 0 if all pass, 1 otherwise — wire into CI to prevent prompt regressions.

## What this does NOT do

- Call any LLM judge (deterministic routing-token check only).
- Measure latency or cost — add those if you need them, but the core value is verdict consistency.
- Test the *content* of explainer prompts — just which branch was selected. For content quality evals, use a separate LLM-judge harness.
