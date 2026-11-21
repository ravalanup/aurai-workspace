# Identity and roles

## Roles

| Keycloak role | Open WebUI role | Can do |
|---|---|---|
| `member` | user | Chat with approved models; use knowledge search; manage own chats |
| `builder` | user, in group `workspace-builders` | Everything a member can, plus create prompts and assistants for their group when an admin grants that group workspace permissions |
| `admin` | admin | Manage models, groups and settings; reach the admin panel |

Groups carry roles: `workspace-members` (member), `workspace-builders` (member, builder), `workspace-admins` (member, admin). Users belong to groups; roles follow from groups.

Three further groups, `knowledge-ops`, `knowledge-hr` and `knowledge-finance`, carry no roles. They grant access to document collections in `aurai-knowledge-rag`, whose `config/entitlements.yaml` maps each group name to collections and a classification ceiling. They are granted by the data owners, and `workspace-admins` deliberately gets no document access from them. Demo users: `omar.haddad` (builder, ops reports), `lee.chen` (member, HR policies) and `priya.nair` (member, finance reporting).

Two approver groups, `approvers-ops` and `approvers-finance`, also carry no roles. `aurai-agent-runtime` (`config/approvers.yaml`) maps them to the teams whose agent actions they may approve. Membership is granted by the owner of the team's data; a person never approves a request they, or their own agent run, made. Demo approvers: `rosa.delgado` (`approvers-ops`) and `hana.kim` (`approvers-finance`).

## What the token carries

The `open-webui` client has three mapped claims, all in the access token:

| Claim | Source | Used by |
|---|---|---|
| `roles` | realm roles | Open WebUI role mapping (`OAUTH_ROLES_CLAIM`, allowed and admin roles) |
| `groups` | group membership, short names | Open WebUI group sync; gateway teams in JWT mode |
| audience `litellm` | audience mapper | Gateway verifies tokens were meant for it (JWT mode) |

Tokens last 15 minutes. The client is confidential, uses the authorization code flow only, and has direct access grants and implicit flow off. Sign-up is disabled and so is the password form in Open WebUI, so Keycloak is the only way in.

## Requirements coverage

| Requirement | How it is met |
|---|---|
| WS-1 Secure chat, SSO | Open WebUI behind Keycloak; models only through the gateway |
| WS-2 Role-based access | Keycloak roles and groups mapped to Open WebUI roles and groups |
| WS-3 Document Q&A with citations | Knowledge tool and contract (pending the knowledge service) |
| WS-4 Audit log | Open WebUI audit log at metadata level to stdout; gateway spend logs per user; traces in Langfuse |
| WS-5 Content filters by tier | Tier filter function, `functions/tier_filter.py` |

## Operating the realm

```powershell
aurai-workspace validate realm/aurai-realm.yaml      # no network
aurai-workspace plan     realm/aurai-realm.yaml --base-url http://localhost:18080
aurai-workspace apply    realm/aurai-realm.yaml --base-url http://localhost:18080
```

Credentials come from the environment (`KEYCLOAK_ADMIN_USER`, `KEYCLOAK_ADMIN_PASSWORD`, `OPEN_WEBUI_CLIENT_SECRET`, optional `AURAI_DEMO_PASSWORD`). The realm file holds no secrets and no passwords. Adding a user to a group changes their roles at the next sign-in; Open WebUI users must sign out and in to pick up a role change.

## Group permissions inside Open WebUI

Per-group workspace permissions (for example letting builders create assistants, or switching file upload off) live in Open WebUI's database and are set in the Admin Panel under Users, Groups. Groups are created automatically from the token. This part is not code yet; production would script it through Open WebUI's admin API.
