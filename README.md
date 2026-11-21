# aurai-workspace

The employee-facing chat workspace for the Aurai platform: Open WebUI behind Keycloak single sign-on, wired to the Aurai gateway, with roles, a tier-aware content filter, an audit trail and a defined interface to the knowledge service.

Part of **Aurai**, a fictional enterprise AI platform built for Amazing-Enterprise. All data and people are synthetic.
This is a prototype with production patterns: it documents what a real deployment would add and what has not been verified.

## What is here

| Path | Purpose |
|---|---|
| `realm/` | Keycloak realm as code: roles, groups, OIDC client, demo users |
| `src/aurai_workspace/` | `aurai-workspace` CLI: validate, plan and apply the realm through Keycloak's admin API |
| `functions/` | Open WebUI functions: `tier_filter.py` (content check by risk tier) and `knowledge_search.py` (tool for the knowledge service) |
| `contracts/` | OpenAPI contract for the knowledge service that `aurai-knowledge-rag` implements |
| `gateway/` | The workspace's gateway team, per-user attribution settings, optional verified-identity (JWT) overlay |
| `deploy/` | Open WebUI values for the official Helm chart (local, AWS, JWT overlay) |
| `charts/aurai-workspace/` | Support chart: database bootstrap and network policy |
| `scripts/` | Local deploy, port-forward and undeploy (PowerShell; bash deploy) |
| `docs/` | Architecture, identity and roles, gateway integration, governance controls, local development, runbook |

## Quick start: realm library and functions

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
aurai-workspace validate realm\aurai-realm.yaml
pytest
```

## Quick start: local workspace

Needs the `aurai-infra` cluster and a deployed `aurai-gateway`. Follow [docs/local-development.md](docs/local-development.md): create the gateway team and key, run `scripts\deploy-local.ps1`, add one hosts-file line for sign-in, then open http://localhost:3100.

## How it works in one paragraph

Users sign in through Keycloak. Their roles and groups arrive in the token and become Open WebUI roles and groups. Chat requests go only to the gateway, tagged with the person's identity so spend and logs are per user. A filter function checks messages against the workspace's risk tier before they leave. Document questions go to the knowledge service through a tool, with the user's own token, and answers carry citations. A verified-identity mode (Keycloak JWTs at the gateway) is available as an overlay for deployments with a LiteLLM Enterprise license.

## Honest status

Verified: the realm library against an in-memory Keycloak fake, the tier filter and knowledge tool against fakes, the OpenAPI contract's request and response shapes, lint, YAML validity, Helm template syntax of the support chart, and the gateway chart change.

Not verified: any Helm install or render; Open WebUI chart value names (the official chart's layout is followed from its documentation, pin the chart version); Open WebUI environment variables beyond the OIDC and audit ones documented upstream (for example default permission settings); Keycloak admin API behaviour against a real server; whether Open WebUI passes the user's token to tools; LiteLLM user header mappings and the JWT overlay against a live gateway; the knowledge service, which does not exist yet. Expect small fixes on first install.

Licensing note: Open WebUI v0.6.6 and later carries a branding clause. This repo keeps the Open WebUI name and logo.

## Related repos

`aurai-docs` (product and governance), `aurai-infra` (cluster, Keycloak, PostgreSQL), `aurai-gateway` (LiteLLM, guardrails, teams), `aurai-eval-governance` (tracing, risk tiers), `aurai-knowledge-rag` (next: implements the knowledge contract).

## License

MIT
