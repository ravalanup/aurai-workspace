# Runbook

## Cannot sign in

- **Browser cannot reach Keycloak:** the hosts-file entry or the Keycloak port-forward is missing (docs/local-development.md).
- **"Invalid redirect URI":** `WEBUI_URL` and the realm's redirect URI must match exactly (`http://localhost:3100/oauth/oidc/callback` locally). Re-run `aurai-workspace apply` after changing the realm file.
- **Signed in but no admin rights:** the user needs the `admin` role (group `workspace-admins`); sign out and in. Check the token has a `roles` claim.
- **Login loop or "invalid_client":** the client secret in `openwebui-secrets` differs from Keycloak's. Re-run the deploy script, which applies both from one value.

## Models empty or requests fail with 401

- The gateway key in `openwebui-secrets` (`OPENAI_API_KEY`) is wrong, expired or its team lacks the model. Issue a new key and re-run the deploy script.
- Non-admin users only see models their Open WebUI group may use; an admin grants access in the Admin Panel.

## Requests are not attributed to users

- Open WebUI must run with `ENABLE_FORWARD_USER_INFO_HEADERS=true` and the gateway must have `gateway/user-headers.values.yaml` applied. Check spend logs in the gateway UI for the user column.

## Knowledge search says it is unavailable

Expected until `aurai-knowledge-rag` is deployed and the tool's `knowledge_service_url` valve is set.

## Messages are blocked unexpectedly

The tier filter blocked a marker word. Check the `tier` valve; for T1 only "restricted" phrases block. Marker words are matched anywhere in the message.

## Pause the workspace

Block the gateway team: `aurai-governance pause workspace --registry <use-cases> --base-url <gateway>` once a `workspace` use case is registered in aurai-eval-governance, or call the gateway's team block endpoint directly. Users can still sign in but model calls fail until the team is unblocked.

## Rotate secrets

Delete the Secret key and re-run the deploy script to generate a new one. Rotating the OIDC client secret signs everyone out. `WEBUI_SECRET_KEY` rotation invalidates sessions.
