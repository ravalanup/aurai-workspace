<# Port-forward Open WebUI (3100) and Keycloak (8080). Sign-in needs the hosts-file entry in docs\local-development.md. #>
param([string]$Namespace = "aurai-workspace", [string]$InfraNamespace = "aurai-system")
$ErrorActionPreference = "Stop"
$jobs = @(
  Start-Job { kubectl port-forward -n $using:Namespace svc/openwebui 3100:80 },
  Start-Job { kubectl port-forward -n $using:InfraNamespace svc/keycloak 8080:8080 }
)
Write-Host "Open WebUI http://localhost:3100   Keycloak http://keycloak.aurai-system.svc.cluster.local:8080   (Ctrl+C to stop)"
try { Wait-Job $jobs | Out-Null } finally { $jobs | Stop-Job; $jobs | Remove-Job }
