---
name: bedrock-flow-deploy
description: Troubleshooting guide for deploying Bedrock Prompt Flows — IAM propagation, flow validation errors, agent preparation failures, common AWS CLI pitfalls.
---

# bedrock-flow-deploy

Troubleshooting the generated `deploy.sh`. Read this when a deploy fails; the errors are usually one of the following.

## "AccessDenied" on agent invoke

**Symptom**: Flow runs, reaches an Agent node, fails with `AccessDenied` or `User is not authorized to perform: bedrock:InvokeAgent`.

**Cause**: The flow's IAM role lacks `bedrock:InvokeAgent` on `agent-alias/*`. Policy template `flow-permissions-policy.json.j2` includes this when `specialists` is non-empty — double-check the rendered policy.

**Also check**: agent trust policy allows `bedrock.amazonaws.com` and its `SourceArn` condition matches the agent ARN pattern.

## "Resource is not in a valid state" on update

**Symptom**: `update-agent` returns `ResourceConflictException: agent is in a non-terminal state`.

**Cause**: Previous prepare is still running, or the agent is in `PREPARING`. `deploy.sh`'s prepare polling loop handles the post-update case, but concurrent invocations can race.

**Fix**: wait 30 seconds and re-run `deploy.sh`. The idempotency will pick up where it left off.

## "Flow definition is invalid"

**Symptom**: `prepare-flow` fails; `get-flow` `validations` list explains.

Common entries:
- **Node output type mismatch** — a connection's `sourceOutput` is typed Object but the target expects String. Prompt node outputs are always String; LambdaFunction node outputs default to Object unless you explicitly declare String.
- **Dangling condition** — the Condition node must have a `default` branch AND every condition name must have at least one outgoing Conditional connection.
- **Unresolved input variable** — Prompt node template has `{{foo}}` but no `inputVariables` entry named `foo`, or the `inputs` array doesn't include a connection feeding `foo`.
- **Self-loop** — a node connected to itself. Usually a rename bug.

## "BadRequestException: on-demand throughput isn't supported"

**Symptom**: Agent invoke or prompt invoke fails with the above error.

**Cause**: Used a bare model ID (`anthropic.claude-haiku-4-5-20251001-v1:0`) instead of the inference-profile ID (`us.anthropic.claude-haiku-4-5-20251001-v1:0`). Cross-region inference profiles are required for Claude 4.x on-demand.

**Fix**: the scaffolder defaults to the `us.` prefix. Check `spec.yaml` didn't override it.

## IAM propagation delays

**Symptom**: `create-function` fails with `The role defined for the function cannot be assumed`, or `create-agent` fails with similar.

**Cause**: IAM role was just created and hasn't propagated globally yet.

**Fix**: the generated `deploy.sh` sleeps 10s after role creation. If you're doing it by hand, give it 15s and retry.

## `jq` errors in the deploy script

**Symptom**: `jq: error: Could not open file` or `parse error: Invalid numeric literal` during state-file ops.

**Cause**: `.deploy-state.json` is malformed (hand-edited, or a previous run crashed mid-write).

**Fix**: delete the state file. `deploy.sh` will recreate it. Idempotent resource detection is by AWS API, not by state cache — state is just a handy local reference.

## Lambda "Unzipped size must be smaller than..."

**Symptom**: `create-function` fails with size limit at either 70MB (direct upload) or 250MB (unzipped).

**Fix**:
- Over 70MB zip: stage to S3 and use `--code S3Bucket=...,S3Key=...` instead of `--zip-file`.
- Over 250MB unzipped: strip `__pycache__`, `tests/`, `*.dist-info/`, `*.so.debug` from site-packages before zipping.

## Flow invoke returns empty / incomplete output

**Symptom**: `invoke_flow.py` shows a Completion event but no Output events.

**Cause**: flow routed through the Condition node's `default` branch (supervisor returned a token outside the declared branches).

**Fix**: check the supervisor's actual output via CloudWatch Logs for the Prompt node. If the model is returning something like `APPROVE.` with a period, tighten the prompt: "Return ONE word from {APPROVE, DENY, REVIEW}. No punctuation, no explanation."

## Model access not granted

**Symptom**: First invoke fails with `AccessDeniedException` on `InvokeModel`.

**Fix**: in the Bedrock console, go to "Model access" and enable the specific model ID for your region. This is a one-time manual step AWS requires per account.
