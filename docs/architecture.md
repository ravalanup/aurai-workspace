# Architecture

```
 Employee browser
      |  OIDC (authorization code)
      v
 Open WebUI  ------------------------------>  Keycloak (realm "aurai")
  |   |  \                                     roles, groups, OIDC client
  |   |   \ tier filter (function, inlet)
  |   |    \ knowledge search (tool)  -- Bearer user token -->  Knowledge service (aurai-knowledge-rag)
  |   |
  |   | OpenAI-compatible API + user headers (or user JWT)
  |   v
  |  LiteLLM gateway (aurai-gateway)  -->  PII masking, budgets, routing  -->  model providers
  |
  +--> PostgreSQL (database "openwebui")      traces: gateway -> otel-collector -> Langfuse / Phoenix
```

## What this repo owns

| Concern | Where | Notes |
|---|---|---|
| Identity: realm, roles, groups, OIDC client, demo users | `realm/`, `src/aurai_workspace/` | Applied idempotently through Keycloak's admin API |
| Workspace deployment | `deploy/`, `charts/aurai-workspace/` | Official Open WebUI chart plus a small support chart (database bootstrap, network policy) |
| Governance in the UI | `functions/tier_filter.py` | Tier-aware content check before a message leaves the workspace |
| Document Q&A | `functions/knowledge_search.py`, `contracts/` | Calls the knowledge service; contract defined here, implementation in `aurai-knowledge-rag` |
| Gateway wiring | `gateway/` | The workspace team, per-user attribution settings, and an optional verified-identity overlay |

## Design decisions

**Open WebUI is UI only.** It does not run its own retrieval, hold provider keys or choose models outside the gateway catalog. Everything that needs governance happens in a service the platform team owns.

**One identity provider.** Keycloak holds users, groups and roles. Open WebUI derives its own roles and groups from the token on every sign-in, so changing access is a Keycloak change, not a manual edit in the workspace.

**Realm as code.** The realm file is reviewed like any other change, validated in CI, and applied by `aurai-workspace apply`. The tool never deletes: removing a user or role from the file does not remove it from Keycloak.

**Per-user attribution at the gateway.** The default mode forwards the user's id and email as request headers so spend and logs are per person. The stronger mode, verified JWTs, is an opt-in overlay because it needs a LiteLLM Enterprise license. See [gateway-integration.md](gateway-integration.md).

## What production would add

- Keycloak with an external database, several replicas, TLS and a corporate identity provider federated in; no demo users.
- Verified user identity to the gateway (the JWT overlay) so a compromised workspace cannot claim another person's identity.
- SSO group-to-team mapping at the gateway so budgets follow organisational groups.
- Audit logs shipped to a retained, access-controlled store, with retention set by risk tier.
- Content filters backed by a classification service rather than markers typed by users.
- Open WebUI on several replicas with Redis-backed websockets and S3 storage (the AWS values show the shape).
- Conformance tests of the knowledge contract run against the real service in CI.

## Not verified here

Helm charts were not rendered or installed, Open WebUI and Keycloak were not run, and the LiteLLM JWT path needs a license. The realm library, filter, knowledge tool and contract are covered by unit tests against fakes. See the README for the full list.
