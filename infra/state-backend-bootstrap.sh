#!/usr/bin/env bash
# One-time state-backend bootstrap. Run BEFORE the first terraform init.
# Requires az CLI authenticated to the target subscription.

set -euo pipefail

SUBSCRIPTION_ID="${1:-}"
LOCATION="${2:-eastus2}"

if [ -z "$SUBSCRIPTION_ID" ]; then
  echo "Usage: $0 <subscription_id> [location]"
  exit 1
fi

RG="tyndale-tfstate-rg"
SA_BASE="tyndaletfstate"
CONTAINER="tfstate"

az account set --subscription "$SUBSCRIPTION_ID"

# Generate a deterministic-looking suffix from the subscription ID so re-runs
# find the same storage account name.
SUFFIX=$(echo -n "$SUBSCRIPTION_ID" | shasum | cut -c1-6)
SA="${SA_BASE}${SUFFIX}"

echo "Creating resource group $RG in $LOCATION..."
az group create --name "$RG" --location "$LOCATION" --tags managed-by=manual purpose=tfstate

echo "Creating storage account $SA..."
az storage account create \
  --name "$SA" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --tags managed-by=manual purpose=tfstate

echo "Creating container $CONTAINER..."
az storage container create \
  --name "$CONTAINER" \
  --account-name "$SA" \
  --auth-mode login

echo ""
echo "State backend ready. Use these values in infra/envs/dev/backend.tf:"
echo "  resource_group_name  = \"$RG\""
echo "  storage_account_name = \"$SA\""
echo "  container_name       = \"$CONTAINER\""
echo "  key                  = \"dev.tfstate\""
