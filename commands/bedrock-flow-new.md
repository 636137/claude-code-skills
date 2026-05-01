---
name: bedrock-flow-new
description: Scaffold a new Amazon Bedrock Prompt Flow project from a YAML spec. Emits deploy scripts, IAM policies, Lambdas, agents, BDA blueprints, and the flow graph.
---

# /bedrock-flow-new

Orchestrates the `bedrock-flow-scaffolder` skill to produce a complete, deployable Bedrock Prompt Flow project.

## Arguments

- `spec=<path>` — path to a YAML spec file. If omitted, walk the user through an interactive prompt and write the spec first.
- `out=<path>` — output directory. Defaults to `./<project_name>` from the spec.
- `--dry-run` — generate into a temp directory and run the test suite; do not touch the user's cwd.

## Execution plan

### Step 0 — Preflight

- If `spec` is missing, interactively ask the user for these fields (in one batch, don't ping-pong):
  1. **Project name** (kebab-case, e.g., `claims-intake`)
  2. **AWS region** (default `us-east-1`)
  3. **Model ID** (default `us.anthropic.claude-haiku-4-5-20251001-v1:0`)
  4. **Ingress type**: `bda` (document extraction), `lambda` (custom lookup), or `none` (skip — supervisor takes raw input)
  5. **Specialists** (0 or more): for each, ask name + 1-3 tool operation IDs + a 1-sentence description. Zero specialists is valid — the supervisor can fuse just the ingress output.
  6. **Branches**: usually `APPROVE / DENY / REVIEW`. Let them override.
  7. **Fusion rules**: 3-6 lines of plain English describing how the supervisor combines specialist verdicts into a branch.

  Write the resulting spec to `./<project_name>/spec.yaml` and echo it back for confirmation before generating.

- If `spec` is provided, read it and validate the schema before touching the filesystem. Schema lives in `skills/bedrock-flow-scaffolder/schema.json`.

### Step 1 — Scaffold

Invoke the scaffolder script:

```bash
python3 <plugin-root>/skills/bedrock-flow-scaffolder/scaffolder.py \
  --spec <spec-path> \
  --out <out-dir>
```

Do **not** re-implement generation in-line — the scaffolder is the single source of truth. If it fails, surface the exact error and stop.

### Step 2 — Validate generated output

Run the validation harness:

```bash
python3 -m pytest <plugin-root>/tests/ --generated=<out-dir>
```

This runs the same four checks the test suite runs against fixtures:
- `bash -n` on `scripts/deploy.sh` and `scripts/teardown.sh`
- JSON validity + `${...}` placeholder accounting on `flow/flow-definition.json`
- OpenAPI 3.0 compliance on every file in `agents/*-actions-openapi.json`
- No stray Jinja `{{ }}` tokens in any generated file

If any check fails, the scaffold is broken — report to the user, do not pretend it's done.

### Step 3 — Next steps

Print a block the user can copy-paste:

```
Scaffolded:  <out-dir>

Next steps (from inside <out-dir>):
  AWS_PROFILE=<your-profile> AWS_REGION=<region> bash scripts/deploy.sh

Teardown:
  AWS_PROFILE=<your-profile> bash scripts/teardown.sh

Invoke after deploy:
  FLOW_ID=... ALIAS_ID=... python3 scripts/invoke_flow.py <case-id>
```

## Hard rules

- **Never** emit files outside `<out-dir>`.
- **Never** overwrite an existing non-empty `<out-dir>` without confirmation. Ask first.
- **Never** run `deploy.sh` automatically — that's the user's decision after they've read it.
- **Never** widen the spec schema silently. If the user asks for something the scaffolder doesn't support (e.g., a 5-branch router, nested specialists, knowledge-base integration), say so and propose either (a) manual edits after scaffold, or (b) a follow-up PR to the scaffolder.

## When to abort

- User-provided spec fails schema validation (the scaffolder reports what's wrong).
- The user's `out` directory exists and isn't empty and they decline to overwrite.
- Generated output fails validation and you can't identify a fix in one pass — that's a scaffolder bug; file an issue rather than hand-editing generated files.
