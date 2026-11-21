<# Remove the workspace releases. Data volumes and secrets are kept unless -Purge is given. The Keycloak realm is not touched. #>
param([string]$Namespace = "aurai-workspace", [switch]$Purge)
foreach ($r in "openwebui", "aurai-workspace") { helm uninstall $r --namespace $Namespace 2>$null }
if ($Purge) {
  kubectl delete pvc --all -n $Namespace
  kubectl delete secret openwebui-secrets -n $Namespace --ignore-not-found
}
Write-Host "Done."
