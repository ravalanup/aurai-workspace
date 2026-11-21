# Governance controls in the workspace

## Tier filter (WS-5)

`functions/tier_filter.py` is an Open WebUI *filter function*. Its `inlet` runs before a message goes to the model.

| Tier | Marked "restricted" | Marked "confidential" |
|---|---|---|
| T0 | block | allow |
| T1 (this workspace) | block | warn |
| T2 | block | warn |
| T3 | block | block |

Markers are phrases people put on documents (restricted, strictly confidential, secret; confidential, internal use only). A block shows the user a clear message; a warn shows a status line and lets the message through. An unknown tier gets T3 rules. Messages over a length limit are rejected.

This is a cheap first check, not a classifier: it catches labelled content and cannot see unlabelled sensitive content. PII masking still happens at the gateway, and production would add a classification service.

Install: Admin Panel, Functions, add the file, enable it, and enable it globally. Set the `tier` valve to the gateway team's tier.

## Audit (WS-4)

Open WebUI's audit log is set to `METADATA` and written to stdout: who, which route, when, no message bodies. The cluster log pipeline collects it. The gateway separately records spend per user, and traces carry `aurai.use_case.id`, team and risk tier (see aurai-eval-governance). Retention is set where the logs are stored, by tier: T2 and T3 need extended retention, which this prototype does not implement.

## Document Q&A (WS-3)

`functions/knowledge_search.py` is an Open WebUI *tool*. When the model needs company knowledge it calls `search_knowledge`; the tool sends the question and the user's access token to `POST /v1/search` on the knowledge service and returns numbered, cited passages.

The contract is `contracts/knowledge-service.openapi.yaml`. Its rules:

- Identity comes from the verified bearer token, never from the request body.
- The service applies the caller's entitlements before returning anything and omits, rather than redacts, what the caller cannot read.
- Every passage has a source with title, collection, classification and freshness.
- Errors are explicit: the tool tells the model to say so rather than answer from memory.

**Status: pending.** Until `knowledge_service_url` is set, the tool tells the model that knowledge search is unavailable. The tool reads the user's token from Open WebUI's `__oauth_token__` argument; whether the installed Open WebUI version provides it to tools should be confirmed, and if not the tool says the session is missing. The Open WebUI file upload and knowledge-base features are not part of this design and should be switched off in group permissions.

## Branding

Open WebUI's license (v0.6.6 and later) keeps its name and logo in any deployment unless you hold an enterprise license or fall under its small-deployment exception. This repo leaves the branding untouched and does not set `WEBUI_NAME`.
