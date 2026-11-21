<#
.SYNOPSIS
  Install the Aurai workspace (Keycloak realm + Open WebUI) on the local kind cluster.

.DESCRIPTION
  Prerequisites
    - aurai-infra running (local\scripts\up.ps1); aurai-gateway deployed, with the "workspace" team applied and a
      key issued (see docs\local-development.md). Pass the key with -GatewayKey or $env:WORKSPACE_GATEWAY_KEY.
    - kubectl, helm and Python 3.11+ with this package installed:  pip install -e .
  What it does
    1. Applies the Keycloak realm (roles, groups, OIDC client, demo users) through a temporary port-forward.
    2. Creates the openwebui-secrets Secret (stdin, never written to disk).
    3. Installs the database bootstrap chart, then Open WebUI from its official chart.
  Secrets are generated once and reused on re-runs. The demo password is printed once for local use.
#>
param(
  [string]$ClusterName = "aurai",
  [string]$Namespace = "aurai-workspace",
  [string]$InfraNamespace = "aurai-system",
  [string]$GatewayKey = $env:WORKSPACE_GATEWAY_KEY,
  [string]$OpenWebUIChartVersion = "",
  [string]$DemoPassword = $env:AURAI_DEMO_PASSWORD
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

foreach ($tool in "kubectl", "helm", "aurai-workspace") {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing required tool: $tool (for aurai-workspace run: pip install -e .)" }
}
if (-not $OpenWebUIChartVersion) { Write-Warning "OpenWebUIChartVersion not pinned - installing the latest chart." }

kubectl config use-context "kind-$ClusterName" | Out-Null
kubectl get namespace $Namespace 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Namespace $Namespace not found. Start the platform first: aurai-infra\local\scripts\up.ps1" }

function New-RandomHex([int]$bytes) {
  $buffer = New-Object byte[] $bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
  -join ($buffer | ForEach-Object { $_.ToString("x2") })
}
function Get-SecretValue([string]$secret, [string]$key, [string]$ns) {
  $encoded = kubectl get secret $secret -n $ns -o "jsonpath={.data.$key}" 2>$null
  if ($LASTEXITCODE -eq 0 -and $encoded) { return [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded)) }
  return $null
}
function Get-OrNew([string]$key, [scriptblock]$make) {
  $v = Get-SecretValue "openwebui-secrets" $key $Namespace
  if ($v) { return $v }
  return (& $make)
}

# 1. Keycloak realm ---------------------------------------------------------------------------------------------
$kcUser = Get-SecretValue "aurai-keycloak-admin" "username" $InfraNamespace
$kcPass = Get-SecretValue "aurai-keycloak-admin" "password" $InfraNamespace
if (-not $kcUser -or -not $kcPass) { throw "Keycloak admin credentials not found in secret aurai-keycloak-admin ($InfraNamespace)." }

$clientSecret = Get-OrNew "OAUTH_CLIENT_SECRET" { New-RandomHex 24 }
if (-not $DemoPassword) { $DemoPassword = New-RandomHex 8; $printDemo = $true }

Write-Host "Applying the Keycloak realm"
$pf = Start-Process kubectl -ArgumentList "port-forward -n $InfraNamespace svc/keycloak 18080:8080" -PassThru -WindowStyle Hidden
try {
  Start-Sleep -Seconds 4
  $env:KEYCLOAK_ADMIN_USER = $kcUser
  $env:KEYCLOAK_ADMIN_PASSWORD = $kcPass
  $env:OPEN_WEBUI_CLIENT_SECRET = $clientSecret
  $env:AURAI_DEMO_PASSWORD = $DemoPassword
  aurai-workspace apply "$repo\realm\aurai-realm.yaml" --base-url http://localhost:18080
  if ($LASTEXITCODE -ne 0) { throw "realm apply failed" }
} finally {
  if ($pf -and -not $pf.HasExited) { Stop-Process -Id $pf.Id -Force }
  Remove-Item Env:KEYCLOAK_ADMIN_PASSWORD, Env:OPEN_WEBUI_CLIENT_SECRET, Env:AURAI_DEMO_PASSWORD -ErrorAction SilentlyContinue
}

# 2. Secret -----------------------------------------------------------------------------------------------------
if (-not $GatewayKey) { $GatewayKey = Get-SecretValue "openwebui-secrets" "OPENAI_API_KEY" $Namespace }
if (-not $GatewayKey) { throw "No gateway key. Issue one for the workspace team (docs\local-development.md) and pass -GatewayKey." }

$pgHost = "postgres.$InfraNamespace.svc.cluster.local:5432"
$pgCred = "aurai:aurai-local-dev-only"   # matches aurai-infra values-local.yaml (development only)

@"
apiVersion: v1
kind: Secret
metadata: { name: openwebui-secrets, namespace: $Namespace }
type: Opaque
stringData:
  WEBUI_SECRET_KEY: "$(Get-OrNew 'WEBUI_SECRET_KEY' { New-RandomHex 32 })"
  OPENAI_API_KEY: "$GatewayKey"
  OAUTH_CLIENT_SECRET: "$clientSecret"
  DATABASE_URL: "postgresql://$pgCred@$pgHost/openwebui"
  database-admin-url: "postgresql://$pgCred@$pgHost/postgres"
"@ | kubectl apply -f - | Out-Null
Write-Host "Secret openwebui-secrets applied"

# 3. Charts -----------------------------------------------------------------------------------------------------
helm upgrade --install aurai-workspace "$repo\charts\aurai-workspace" --namespace $Namespace `
  -f "$repo\charts\aurai-workspace\values-local.yaml" --wait --timeout 5m
if ($LASTEXITCODE -ne 0) { throw "support chart install failed" }
kubectl wait --for=condition=complete job/create-openwebui-database -n $Namespace --timeout=180s
if ($LASTEXITCODE -ne 0) { throw "database bootstrap did not complete" }

helm repo add open-webui https://open-webui.github.io/helm-charts 2>$null | Out-Null
helm repo update open-webui | Out-Null
$chartArgs = @()
if ($OpenWebUIChartVersion) { $chartArgs += @("--version", $OpenWebUIChartVersion) }
helm upgrade --install openwebui open-webui/open-webui --namespace $Namespace `
  -f "$repo\deploy\open-webui-values.yaml" -f "$repo\deploy\open-webui-values-local.yaml" @chartArgs --wait --timeout 15m
if ($LASTEXITCODE -ne 0) { throw "Open WebUI install failed" }

Write-Host ""
Write-Host "Workspace installed. One-time setup for sign-in on this machine (see docs\local-development.md):"
Write-Host "  1. Add to C:\Windows\System32\drivers\etc\hosts (as Administrator):  127.0.0.1 keycloak.aurai-system.svc.cluster.local"
Write-Host "  2. .\scripts\port-forward.ps1     # Open WebUI http://localhost:3100, Keycloak :8080"
if ($printDemo) { Write-Host "Demo users (maya.ortega, devon.park, sam.alvarez) password for this install: $DemoPassword" }
