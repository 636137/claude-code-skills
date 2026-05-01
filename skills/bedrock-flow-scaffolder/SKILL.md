---
name: bedrock-flow-scaffolder
description: Turn a YAML spec into a complete Bedrock Prompt Flow project tree (flow graph, IAM, Lambdas, agents, deploy/teardown scripts). Invoked by /bedrock-flow-new. Not for conversational use.
---

# bedrock-flow-scaffolder

This skill is a **code generator**, not a conversational helper. It takes a validated spec and emits files. Claude's role here is only to invoke `scaffolder.py` with the right args and surface errors.

## Inputs

- `spec.yaml` — user's flow description. Schema: `schema.json` in this directory.
- `out/` — target directory (must be empty, or user confirmed overwrite).

## Outputs

A complete project tree:

```
<out>/
├── README.md
├── .gitignore
├── flow/flow-definition.json
├── agents/
│   ├── <specialist>-instructions.md
│   └── <specialist>-actions-openapi.json
├── bda/
│   └── blueprint-<name>.json       # only if ingress.type == bda
├── lambda/
│   ├── <ingress>/lambda_function.py
│   └── <specialist>_actions/lambda_function.py
├── iam/
│   ├── lambda-trust-policy.json
│   ├── agent-trust-policy.json
│   ├── agent-permissions-policy.json
│   ├── flow-trust-policy.json
│   └── flow-permissions-policy.json
└── scripts/
    ├── deploy.sh
    ├── teardown.sh
    └── invoke_flow.py
```

## Invocation

```bash
python3 scaffolder.py --spec <path-to-spec.yaml> --out <out-dir>
```

Exit codes:
- `0` — success
- `1` — spec validation failed (stderr has details)
- `2` — output directory exists and is non-empty (pass `--force` to overwrite)
- `3` — template rendering error (bug — file an issue)

## Spec schema (human-readable)

```yaml
# Required
project_name: snap-intake           # kebab-case, becomes bucket prefix + resource names
region: us-east-1
model_id: us.anthropic.claude-haiku-4-5-20251001-v1:0

# Ingress — exactly one shape
ingress:
  type: bda                         # bda | lambda | none
  # if type == bda:
  blueprints:
    - name: id_document
      class: US-Drivers-License-Or-State-ID
      description: "..."
      fields:
        full_name:
          type: string
          inferenceType: explicit
          instruction: "..."
        # ... more fields
  # if type == lambda:
  lambda:
    name: va-eligibility-lookup
    description: "..."
    input_fields: [claim_number]    # fields the flow passes in

# Specialists — zero or more parallel Bedrock Agents
specialists:
  - name: identity                  # becomes <project>-identity-agent
    description: "..."
    instructions: |                 # freeform, used as agent 'instruction' field
      You are an Identity Verification specialist...
    tools:                          # becomes action-group OpenAPI paths
      - operation_id: check_id_validity
        description: "..."
        request:
          required: [id_number, issuing_state]
          properties:
            id_number: { type: string, description: "..." }
            issuing_state: { type: string, description: "..." }
        response:
          properties:
            verdict: { type: string, enum: [VALID, INVALID, UNVERIFIED] }
            reasons: { type: array, items: { type: string } }

# Supervisor — single Prompt node
supervisor:
  temperature: 0.0
  max_tokens: 40
  fusion_rules: |
    Strict, top-to-bottom:
    1. Any specialist FAIL -> DENY
    2. All PASS -> APPROVE
    3. Otherwise -> REVIEW

# Router branches
router:
  branches: [APPROVE, DENY, REVIEW]

# Explainers — one Prompt node per branch
explainers:
  APPROVE:
    temperature: 0.3
    max_tokens: 400
    instructions: |
      You are writing a plain-English approval notice...
  DENY:
    temperature: 0.3
    max_tokens: 400
    instructions: |
      ...
  REVIEW:
    temperature: 0.3
    max_tokens: 400
    instructions: |
      ...

# OPTIONAL: Knowledge Bases
# Each KB is attached to one or more specialists by name. The scaffolder emits
# a KB config JSON per entry and an IAM role policy; deploy.sh prints the manual
# steps required (OpenSearch Serverless collection is NOT auto-created).
knowledge_bases:
  - name: telco-faq
    description: "Customer-facing FAQ for balance/connectivity issues"
    s3_source_uri: s3://my-kb-docs-bucket/telco-faq/
    # Optional overrides:
    # embedding_model_id: amazon.titan-embed-text-v2:0
    # chunking_strategy: FIXED_SIZE

specialists:
  - name: balance-and-connectivity
    instructions: "..."
    tools: [...]
    knowledge_bases: [telco-faq]       # must match a name in knowledge_bases above

# OPTIONAL: Channels — non-flow-input delivery surfaces
# Values: "connect" (Amazon Connect + Lex), "sms" (AWS End User Messaging).
# Independent of ingress.type; e.g. ingress.type=lambda + channels=[connect]
# means the Lambda is the flow entry and Connect feeds into it.
channels: [connect, sms]

# OPTIONAL: emit a CloudFormation template alongside deploy.sh
emit_cfn: true
```

The scaffolder rejects specs that:
- Reference a branch in `explainers` that isn't in `router.branches`
- Use `ingress.type=bda` without `blueprints`
- Use `ingress.type=lambda` without `ingress.lambda.name`
- Have a specialist with no tools

## Design notes (why the templates look like they do)

1. **`flow-definition.json`** is rendered per-topology: `ingress=bda` adds a BDAInvoker LambdaFunction node + wires its output into every specialist's BuildPrompt node + parallel into the Supervisor. `ingress=none` plugs FlowInput straight into the specialists (or straight into the Supervisor if there are no specialists).

2. **Condition node always has a `default` branch** pointing at an `OutputDefault` sink. Bedrock rejects flows where any Condition path can fall through unhandled.

3. **IAM placeholders**: templates use `${AWS_ACCOUNT_ID}` and `${AWS_REGION}`, which `deploy.sh` substitutes via `sed` at deploy time. This keeps the committed policy files free of account-specific ARNs.

4. **Agent role naming**: `AmazonBedrockExecutionRoleForAgents_<project>` matches the AWS console convention so the console shows the role picker correctly.

5. **Idempotency pattern in `deploy.sh`**: every resource has a `ensure_X` function that does `get-X` first, updates in place if found, creates if not. State is cached in `.deploy-state.json` for the teardown script.

6. **Agent ARN injection into the flow**: the deploy script runs a second `sed` pass after agents are published, substituting `${AGENT_<NAME>_ALIAS_ARN}` tokens in the flow definition. This avoids a circular dependency (flow needs agent ARNs; agents don't need the flow).

## What this skill deliberately does NOT do

- Create AWS resources. That's `deploy.sh`'s job.
- ML / fraud-scorer Lambda scaffolding. The SNAP reference has one; it's excluded from the generator because libgomp bundling + manylinux wheel pinning is fragile template territory. Users who need it can hand-author the extra Lambda after scaffold.
- Create OpenSearch Serverless collections for Knowledge Bases. The scaffolder emits KB config JSON but assumes the collection exists (it's stateful + ~$350/mo minimum, so you create it deliberately).
- Claim Amazon Connect instances or register SMS origination identities. The scaffolder emits the contact-flow JSON / Lex bot YAML / SMS handler Lambda; wiring to your Connect instance or SMS short-code is a post-deploy manual step.
- Multi-environment (dev/stage/prod) aliases. The generated scripts produce one `live` alias pointing at the latest flow version; users extending to multi-env should modify `deploy.sh`.
