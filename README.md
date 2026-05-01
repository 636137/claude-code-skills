# Claude Code Skills — Bedrock Prompt Flow pack

A set of [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) and a top-level slash command that scaffold a production-grade **Amazon Bedrock Prompt Flow** project from a single YAML spec. Distilled from two reference implementations (SNAP intake, VA eligibility) so you don't have to rediscover the boilerplate each time.

## What it builds

Given a `spec.yaml` describing the flow you want, the scaffolder emits a complete repo with:

- `flow/flow-definition.json` — the Bedrock Prompt Flow graph, wired for ingress → (optional specialists) → supervisor → condition router → per-branch explainers
- `agents/*-instructions.md` + `agents/*-actions-openapi.json` — one Bedrock Agent per specialist
- `bda/blueprint-*.json` — custom Bedrock Data Automation blueprints if ingress is BDA
- `lambda/*/lambda_function.py` — action-group Lambdas with the canonical agent-response envelope
- `iam/*.json` — least-privilege trust + permissions policies (Lambda, Agent, Flow roles)
- `scripts/deploy.sh` + `scripts/teardown.sh` — idempotent, state-cached, order-safe
- `scripts/invoke_flow.py` — CLI invoker

Then you run `AWS_PROFILE=... ./scripts/deploy.sh` and the flow is live.

## Install

```bash
# Clone next to your other Claude Code settings
git clone https://github.com/ChadDHendren/claude-code-skills ~/.claude/plugins/claude-code-skills
```

Or install as a plugin (when Claude Code plugin install is wired up in your setup).

## Use

In any Claude Code session, type:

```
/bedrock-flow-new
```

Claude will walk you through the spec fields interactively, then invoke the scaffolder. You can also hand it a spec file directly:

```
/bedrock-flow-new spec=./my-flow.yaml out=./my-flow-project
```

See `examples/` for two working specs:

- `examples/snap-intake.yaml` — full-featured: BDA ingress + 3 specialists + supervisor + 3 explainers
- `examples/va-eligibility.yaml` — minimal: single lookup Lambda + classifier Prompt + router + explainers

## Components

| Component | Path | Purpose |
|---|---|---|
| `/bedrock-flow-new` | `commands/bedrock-flow-new.md` | Top-level slash command — orchestrates the other skills |
| `bedrock-flow-scaffolder` | `skills/bedrock-flow-scaffolder/` | Turns `spec.yaml` into a full project tree |
| `bedrock-agent-authoring` | `skills/bedrock-agent-authoring/` | Guidance: writing good agent instructions + OpenAPI schemas |
| `bda-blueprint-authoring` | `skills/bda-blueprint-authoring/` | Guidance: designing Bedrock Data Automation blueprints |
| `bedrock-flow-deploy` | `skills/bedrock-flow-deploy/` | Troubleshooting: IAM propagation, flow validation errors |
| `bedrock-flow-eval` | `skills/bedrock-flow-eval/` | Golden-case test harness for flow verdicts |

## Tests

```bash
cd claude-code-skills
python3 -m pip install -r tests/requirements.txt
python3 -m pytest tests/
```

Tests verify:
- scaffolder emits expected file tree from a sample spec
- generated `deploy.sh` parses under `bash -n`
- generated `flow-definition.json` is valid JSON with all `${...}` placeholders accounted for
- generated OpenAPI action-group schemas parse cleanly
- no unresolved Jinja tokens in any emitted file

No AWS calls are made by the tests — scaffolding is a pure file-generation step.

## License

MIT. See `LICENSE`.

## Not affiliated with

Anthropic, Amazon Web Services, or any other organization. This is a personal toolkit distilled from public reference architectures.
