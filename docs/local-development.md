# Local development

Prerequisites: the local cluster from `aurai-infra` (`local\scripts\up.ps1`), `aurai-gateway` deployed, `kubectl`, `helm`, and Python 3.11+.

## 1. Gateway team and key

```powershell
$env:LITELLM_MASTER_KEY = "<master key from the litellm-secrets Secret>"
aurai-teamctl apply gateway\workspace-team.yaml --catalog ..\aurai-gateway\config\model-catalog.yaml --base-url http://localhost:4000
aurai-teamctl issue-key workspace --teams gateway\workspace-team.yaml --catalog ..\aurai-gateway\config\model-catalog.yaml --base-url http://localhost:4000 --alias open-webui
```

(Port-forward the gateway first: `..\aurai-gateway\scripts\port-forward.ps1`.) Keep the printed key; pass it to the deploy script.

Enable per-user attribution on the gateway:

```powershell
helm upgrade aurai-gateway ..\aurai-gateway\charts\aurai-gateway -n aurai-gateway --reuse-values -f gateway\user-headers.values.yaml
```

## 2. Deploy the workspace

```powershell
pip install -e .
.\scripts\deploy-local.ps1 -GatewayKey "<key>" -OpenWebUIChartVersion <version>
```

The script applies the Keycloak realm, creates the Secret, installs the support chart and Open WebUI, and prints the demo password.

## 3. Sign in from your browser

The token issuer is Keycloak's in-cluster address, so the browser must reach the same name. One time, as Administrator, add this line to `C:\Windows\System32\drivers\etc\hosts`:

```
127.0.0.1 keycloak.aurai-system.svc.cluster.local
```

Then `.\scripts\port-forward.ps1` and open http://localhost:3100. Sign in as `sam.alvarez` (admin), `devon.park` (builder) or `maya.ortega` (member) with the demo password. `omar.haddad`, `lee.chen` and `priya.nair` hold knowledge groups for `aurai-knowledge-rag`.

## 4. Install the functions

Admin Panel, Functions: add `functions\tier_filter.py`, enable it and make it global, and set its `tier` valve to T1. Add `functions\knowledge_search.py` under Tools when the knowledge service exists.

## Tests

```powershell
pip install -e ".[dev]"
ruff check .; pytest
```
