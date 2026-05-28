#!/usr/bin/env bash
# One-time GitHub Actions deploy bootstrap for the Tyndale dev environment.
#
# Creates:
#   1. Azure AD app registration (tyndale-github-actions-dev) + service principal
#   2. Federated OIDC credentials trusting the GitHub repo on:
#        - push/dispatch to refs/heads/main
#        - pull requests
#   3. Role assignment: Contributor on the dev resource group (tyndale-dev-rg).
#      Scoped to the RG, NOT subscription, so the SP can only touch dev resources.
#
# Fetches:
#   4. The Static Web App deployment API token for tyndale-dev-marketing-swa
#
# Prints: the four GitHub secrets to add to the repo.

set -euo pipefail

SUBSCRIPTION_ID="${1:-}"
GITHUB_OWNER="${2:-thelittleguyai}"
GITHUB_REPO="${3:-tyndale}"

if [ -z "$SUBSCRIPTION_ID" ]; then
  echo "Usage: $0 <subscription_id> [github_owner] [github_repo]"
  echo "Defaults: github_owner=thelittleguyai, github_repo=tyndale"
  exit 1
fi

APP_NAME="tyndale-github-actions-dev"
RG="tyndale-dev-rg"
SWA_NAME="tyndale-dev-marketing-swa"

az account set --subscription "$SUBSCRIPTION_ID"
TENANT_ID="$(az account show --query tenantId -o tsv)"

# --- 1. Azure AD app + service principal (idempotent) ---
echo "==> Azure AD app registration ($APP_NAME)"
APP_ID="$(az ad app list --display-name "$APP_NAME" --query '[0].appId' -o tsv 2>/dev/null || true)"
if [ -z "$APP_ID" ]; then
  APP_ID="$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)"
  echo "    created app: $APP_ID"
else
  echo "    using existing app: $APP_ID"
fi

SP_OBJECT_ID="$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' -o tsv 2>/dev/null || true)"
if [ -z "$SP_OBJECT_ID" ]; then
  SP_OBJECT_ID="$(az ad sp create --id "$APP_ID" --query id -o tsv)"
  echo "    created sp: $SP_OBJECT_ID"
else
  echo "    using existing sp: $SP_OBJECT_ID"
fi

# --- 2. Federated OIDC credentials (idempotent — skip if name exists) ---
# Three subjects covered:
#   * environment:dev — workflows that declare `environment: dev` (current
#                       deploy-runtime + deploy-web-marketing workflows)
#   * ref:refs/heads/main — workflows on main that don't use a GitHub env
#   * pull_request        — future PR-triggered jobs (e.g. SWA preview deploys)
echo "==> Federated OIDC credentials"
existing_creds="$(az ad app federated-credential list --id "$APP_ID" --query '[].name' -o tsv 2>/dev/null || true)"
for SUB in "repo:${GITHUB_OWNER}/${GITHUB_REPO}:environment:dev" \
           "repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/main" \
           "repo:${GITHUB_OWNER}/${GITHUB_REPO}:pull_request"; do
  NAME="$(echo "$SUB" | tr ':/' '-')"
  if echo "$existing_creds" | grep -qx "$NAME"; then
    echo "    skip (exists): $NAME"
    continue
  fi
  az ad app federated-credential create --id "$APP_ID" --parameters "$(cat <<JSON
{
  "name": "$NAME",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "$SUB",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
)" >/dev/null
  echo "    created: $NAME"
done

# --- 3. Role assignment: Contributor on the dev RG ---
echo "==> Role assignment (Contributor on $RG)"
RG_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}"
if az role assignment list --assignee "$SP_OBJECT_ID" --scope "$RG_SCOPE" --role Contributor --query '[0].id' -o tsv 2>/dev/null | grep -q .; then
  echo "    skip (exists): Contributor on $RG"
else
  az role assignment create \
    --assignee-object-id "$SP_OBJECT_ID" \
    --assignee-principal-type ServicePrincipal \
    --role Contributor \
    --scope "$RG_SCOPE" >/dev/null
  echo "    granted: Contributor on $RG"
fi

# --- 4. Fetch SWA deployment token ---
echo "==> SWA deployment token ($SWA_NAME)"
SWA_TOKEN="$(az staticwebapp secrets list --name "$SWA_NAME" --resource-group "$RG" --query "properties.apiKey" -o tsv)"
if [ -z "$SWA_TOKEN" ]; then
  echo "ERROR: could not fetch SWA deployment token. Is $SWA_NAME deployed yet?" >&2
  exit 1
fi

cat <<EOF

=========================================================================
GitHub Actions deploy setup complete.

1. Create the GitHub environment named "dev" (if it doesn't already exist):
     https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/environments
   (one click: "New environment" → name it "dev" → save; no protection
    rules needed for dev)

2. Add these four secrets at the ENVIRONMENT level (NOT repo level), at:
     https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/environments/dev

   AZURE_CLIENT_ID                  = ${APP_ID}
   AZURE_TENANT_ID                  = ${TENANT_ID}
   AZURE_SUBSCRIPTION_ID            = ${SUBSCRIPTION_ID}
   AZURE_STATIC_WEB_APPS_API_TOKEN  = ${SWA_TOKEN}

Auth model:
  - OIDC SP scoped to Contributor on ${RG} only (not subscription-wide).
  - Federated trust matches three GitHub subjects: environment:dev (the one
    the current workflows use), ref:refs/heads/main, and pull_request.
  - SWA token is per-SWA; rotate with:
      az staticwebapp secrets reset-api-key --name ${SWA_NAME} --resource-group ${RG}
=========================================================================
EOF
