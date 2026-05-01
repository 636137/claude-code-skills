---
name: bda-blueprint-authoring
description: Guidance for designing Amazon Bedrock Data Automation custom blueprints. Use when adding document extraction to a Bedrock Prompt Flow.
---

# bda-blueprint-authoring

How to design a Bedrock Data Automation custom blueprint for document extraction.

## Shape

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "description": "<human-readable purpose>",
  "class": "<DocumentClass>",   // e.g. US-Drivers-License-Or-State-ID
  "type": "object",
  "properties": {
    "field_name": {
      "type": "string",
      "inferenceType": "explicit",
      "instruction": "..."
    }
  }
}
```

## `inferenceType`

- `explicit` — the value appears verbatim or near-verbatim on the document. BDA extracts literal text.
- `inferred` — a boolean or categorical judgment BDA makes over the document. Use sparingly; these are less reliable.

Default to `explicit`. Only use `inferred` when you genuinely need a judgment (e.g., `document_appears_valid: boolean`).

## Writing good `instruction` fields

The instruction is a prompt. Treat it that way:

1. **Name the field's semantics, not just its appearance.** "Cardholder's full name as printed, preserving casing" is better than "name".
2. **Specify the output format.** Dates → "YYYY-MM-DD format. Convert from any printed format." Money → "Dollar amount as a number, no currency symbol."
3. **Call out common confusions.** "ID number. Do NOT confuse with SSN or document class code."
4. **For inferred fields, define truth conditions.** "True if layout matches a genuine ID, photograph present, no obvious tampering. False if obviously fake or not a photo ID."

## Blueprint class

`class` is the matching key — when BDA runs a project with multiple blueprints against a document, it picks the blueprint whose `class` most closely matches. Use distinct, descriptive class names (`US-Drivers-License-Or-State-ID`, `US-Paystub`, `US-Utility-Bill`).

## Project vs. blueprint

One project = many blueprints. The project's `CustomOutputConfiguration` lists the blueprint ARNs. At runtime BDA picks the best-matching blueprint per document. This is how `snap-intake` classifies ID vs. income vs. residency documents without the caller knowing which PDF is which.

## Watch out for

- BDA enforces a per-account concurrency limit — a case with many PDFs may queue.
- `inferenceType: inferred` boolean fields sometimes come back as the string `"true"` rather than the JSON boolean — handler code should coerce.
- BDA output JSON uses `inference_result` at the top level, not the blueprint's property names directly. Your post-processing Lambda needs to unwrap.
- Cross-region inference profile `us.data-automation-v1` may route requests to any US region; your Lambda's IAM policy needs a `*` on the region for the profile ARN.
