---
name: bedrock-agent-authoring
description: Guidance for writing effective Bedrock Agent instructions and OpenAPI action-group schemas. Use when designing specialists for a Bedrock Prompt Flow.
---

# bedrock-agent-authoring

How to write a good Bedrock Agent.

## Instructions file (`<name>-instructions.md`)

Structure your agent's instruction field like this:

1. **Role + scope** — one sentence. "You are a [domain] specialist for [system]. Your job is to [single verb + object]."
2. **Input contract** — name the exact fields the agent will receive. Don't rely on the model to infer.
3. **Tool-use protocol** — numbered steps, in order. "1. Call `check_X` with A, B, C. If result is INVALID, STOP and return FAIL. 2. Call `check_Y`..."
4. **Decision rules** — top-to-bottom priority. First-match-wins is easier for the model than "consider all these factors."
5. **Output schema** — exact JSON shape. Keys, value enums, required fields.
6. **Refusal / error posture** — what to do if a tool errors or returns unexpected data. Default: note in evidence and return REVIEW, don't fabricate.

## OpenAPI action-group schema (`<name>-actions-openapi.json`)

Required shape:
- `openapi: "3.0.0"` (Bedrock rejects 3.1)
- Every operation has `operationId` (Bedrock uses this as the tool name; must be valid Python identifier)
- Every operation has `description` — short, action-oriented. This is what the agent sees when deciding which tool to call.
- `requestBody.content.application/json.schema` is a JSON Schema object. Use `required` to mark mandatory fields.
- `responses.200.content.application/json.schema` documents what the tool returns. The agent reads the response before deciding next steps — be specific about enum values.

## Tool design principles

1. **Name tools as verbs on nouns.** `check_id_validity`, `compute_monthly_gross`, `lookup_claim`. Not `id_tool_1` or `get_info`.
2. **One tool, one job.** Don't bundle "validate and compare" — make them two calls the agent can sequence.
3. **Return enums for verdicts.** `"verdict": "VALID" | "INVALID" | "UNVERIFIED"` not free-text. Agents reason better about discrete values.
4. **Include `reasons` arrays.** The agent will often cite them verbatim in its final JSON.
5. **Stay under 5 tools per agent.** More than that and the agent's tool-selection accuracy drops noticeably.

## What will bite you

- Trailing commas in the OpenAPI JSON — `jq empty < file.json` to validate.
- `$ref` references — Bedrock's OpenAPI parser doesn't resolve them reliably. Inline everything.
- Optional parameters that the model forgets to pass — mark them `required` if the handler can't cope with missing values, and have the handler return a descriptive error rather than crashing.
- Action-group Lambda returning anything other than the Bedrock agent envelope — see `action-lambda.py.j2` in `bedrock-flow-scaffolder` for the exact shape.
