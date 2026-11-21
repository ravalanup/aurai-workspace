# Gateway integration

The workspace sends every model request to the Aurai gateway. The question is how the gateway learns *who* asked.

## Default: one workspace key plus forwarded user headers

- The gateway has a team `workspace` (risk tier T1), defined in `gateway/workspace-team.yaml` and applied with `aurai-teamctl`. Its key lives in the `openwebui-secrets` Secret.
- Open WebUI runs with `ENABLE_FORWARD_USER_INFO_HEADERS=true`, so each call carries `X-OpenWebUI-User-Id`, `-Email`, `-Name` and `-Role`.
- The gateway is configured with `user_header_mappings` (`gateway/user-headers.values.yaml`), so spend and logs are recorded against the person, and the role header is added as a spend tag.

This works with open-source LiteLLM.

**Trust boundary.** The gateway believes the headers because the request carries the workspace key. Anyone holding that key can claim to be any user. Controls: the key sits only in the workspace namespace's Secret; the gateway's NetworkPolicy admits only Aurai platform namespaces; the key's budget and rate limit cap the damage. It is attribution, not authentication.

## Verified identity: JWT overlay (optional, needs a license)

`gateway/jwt.values.yaml` and `deploy/open-webui-jwt.values.yaml` switch to verified identity. Open WebUI sends the signed-in user's Keycloak access token; the gateway checks the signature, issuer and audience, creates the user on first request and treats each Keycloak group as a team, enforcing team model access.

- LiteLLM's JWT authentication is an Enterprise feature and needs `LITELLM_LICENSE`; without it requests are rejected.
- Team ids must equal the Keycloak group names, and every user needs at least one group, admins included.
- Set the audience and issuer, or the gateway accepts any token your identity provider signs.
- The realm already adds the `litellm` audience and a `groups` claim.

This follows LiteLLM's published "Open WebUI for Organizations" guide. It has not been run here because it needs a license.

## Gateway chart change

The gateway chart gained three optional values so this repo can configure it without forking: `litellm.generalSettings`, `litellm.extraSettings` (merged into LiteLLM's config) and `litellm.extraEnv`. Defaults are empty, so existing installs are unchanged.

## Choosing

| | Headers (default) | JWT overlay |
|---|---|---|
| License | Open source | LiteLLM Enterprise |
| Per-user spend and logs | Yes | Yes |
| Identity verified by the gateway | No | Yes |
| Budgets by Keycloak group | No (team-level only) | Yes |
| Tested here | Config validated; not run against a live gateway | Not run |
