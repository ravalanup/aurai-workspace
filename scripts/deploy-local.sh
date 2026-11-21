#!/usr/bin/env bash
# Install the Aurai workspace on the local kind cluster. Mirrors deploy-local.ps1.
# Requires: kubectl, helm, openssl, aurai-workspace (pip install -e .), WORKSPACE_GATEWAY_KEY.
set -euo pipefail
CLUSTER="${CLUSTER:-aurai}"; NS="${NS:-aurai-workspace}"; INFRA_NS="${INFRA_NS:-aurai-system}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"; CHART_VER="${OPENWEBUI_CHART_VERSION:-}"
for t in kubectl helm openssl aurai-workspace; do command -v "$t" >/dev/null || { echo "missing $t" >&2; exit 1; }; done
[ -n "$CHART_VER" ] || echo "warning: OPENWEBUI_CHART_VERSION not pinned" >&2
kubectl config use-context "kind-$CLUSTER" >/dev/null
kubectl get namespace "$NS" >/dev/null 2>&1 || { echo "namespace $NS missing; run aurai-infra/local/scripts/up.sh" >&2; exit 1; }

get() { kubectl get secret "$1" -n "$2" -o "jsonpath={.data.$3}" 2>/dev/null | base64 -d 2>/dev/null || true; }
keep() { local v; v="$(get openwebui-secrets "$NS" "$1")"; if [ -n "$v" ]; then echo "$v"; else echo "$2"; fi; }

CLIENT_SECRET="$(keep OAUTH_CLIENT_SECRET "$(openssl rand -hex 24)")"
DEMO_PASSWORD="${AURAI_DEMO_PASSWORD:-$(openssl rand -hex 8)}"
GATEWAY_KEY="${WORKSPACE_GATEWAY_KEY:-$(get openwebui-secrets "$NS" OPENAI_API_KEY)}"
[ -n "$GATEWAY_KEY" ] || { echo "set WORKSPACE_GATEWAY_KEY (see docs/local-development.md)" >&2; exit 1; }

kubectl port-forward -n "$INFRA_NS" svc/keycloak 18080:8080 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null || true' EXIT; sleep 4
KEYCLOAK_ADMIN_USER="$(get aurai-keycloak-admin "$INFRA_NS" username)" \
KEYCLOAK_ADMIN_PASSWORD="$(get aurai-keycloak-admin "$INFRA_NS" password)" \
OPEN_WEBUI_CLIENT_SECRET="$CLIENT_SECRET" AURAI_DEMO_PASSWORD="$DEMO_PASSWORD" \
  aurai-workspace apply "$REPO/realm/aurai-realm.yaml" --base-url http://localhost:18080

PG="aurai:aurai-local-dev-only@postgres.$INFRA_NS.svc.cluster.local:5432"
kubectl apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Secret
metadata: { name: openwebui-secrets, namespace: $NS }
type: Opaque
stringData:
  WEBUI_SECRET_KEY: "$(keep WEBUI_SECRET_KEY "$(openssl rand -hex 32)")"
  OPENAI_API_KEY: "$GATEWAY_KEY"
  OAUTH_CLIENT_SECRET: "$CLIENT_SECRET"
  DATABASE_URL: "postgresql://$PG/openwebui"
  database-admin-url: "postgresql://$PG/postgres"
YAML

helm upgrade --install aurai-workspace "$REPO/charts/aurai-workspace" -n "$NS" \
  -f "$REPO/charts/aurai-workspace/values-local.yaml" --wait --timeout 5m
kubectl wait --for=condition=complete job/create-openwebui-database -n "$NS" --timeout=180s
helm repo add open-webui https://open-webui.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update open-webui >/dev/null
helm upgrade --install openwebui open-webui/open-webui -n "$NS" \
  -f "$REPO/deploy/open-webui-values.yaml" -f "$REPO/deploy/open-webui-values-local.yaml" \
  ${CHART_VER:+--version "$CHART_VER"} --wait --timeout 15m
echo "Done. Add '127.0.0.1 keycloak.aurai-system.svc.cluster.local' to /etc/hosts, then:"
echo "  kubectl port-forward -n $NS svc/openwebui 3100:80   and   kubectl port-forward -n $INFRA_NS svc/keycloak 8080:8080"
echo "Demo users password for this install: $DEMO_PASSWORD"
