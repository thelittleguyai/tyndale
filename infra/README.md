# Tyndale Infrastructure

Terraform-managed Azure infrastructure for Tyndale. Currently scoped to the
dev environment; staging + production land in later phases.

## Layout

```
infra/
  envs/
    dev/         # Active — V1-Lite dev environment
    staging/     # Placeholder
    production/  # Placeholder
  modules/       # Reusable modules (extracted when staging lands)
  state-backend-bootstrap.sh
  .terraform-version
```

## One-time setup

1. Authenticate the az CLI to the target subscription:
   ```
   az login
   az account set --subscription <subscription_id>
   ```

2. Bootstrap the state backend (creates the `tyndale-tfstate-rg` resource
   group and the state container):
   ```
   ./infra/state-backend-bootstrap.sh <subscription_id> eastus2
   ```

3. Update `infra/envs/dev/backend.tf` with the `storage_account_name` from the
   bootstrap output.

4. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill in the
   subscription_id + tenant_id. Provide `postgres_admin_password` via env var:
   ```
   export TF_VAR_postgres_admin_password='<strong-password>'
   ```

## Deploy (dev)

```
cd infra/envs/dev
terraform init
terraform plan
terraform apply
```

## After first apply

1. Get the Azure nameservers from the apply output:
   ```
   terraform output dns_zone_nameservers
   ```

2. Update the registrar for `tyndaleapp.net` to point to those nameservers.
   DNS propagation takes 24-48 hours.

3. Set the Document Intelligence key in Key Vault:
   ```
   az keyvault secret set \
     --vault-name $(terraform output -raw key_vault_uri | sed 's|https://||;s|.vault.azure.net/||') \
     --name AZURE-DOC-INTELLIGENCE-KEY \
     --value $(az cognitiveservices account keys list \
                 --name $(terraform output -raw container_app_runtime_fqdn | cut -d'.' -f1 | sed 's|-runtime|-doc-intel|') \
                 --resource-group $(terraform output -raw resource_group_name) \
                 --query key1 -o tsv)
   ```
   (Or copy the keys from the Azure Portal — Document Intelligence resource → Keys & Endpoint.)

4. Once DNS propagates, `https://dev.tyndaleapp.net` resolves to the dev SWA.

## Cost expectations (dev)

Rough monthly cost with scale-to-zero usage:

| Resource | Cost |
|---|---|
| Postgres Flexible B1ms | ~$12-15 |
| Container Apps (scale-to-zero) | <$5 |
| Key Vault Standard | <$1 |
| Storage Account LRS | <$1 |
| Log Analytics + App Insights (free 5 GB) | free |
| Static Web App Free tier | $0 |
| Document Intelligence F0 (500 pages/month) | $0 |
| DNS Zone | $0.50 |

Total: ~$15-25/month for an idle dev environment. Active use adds Container
Apps consumption costs (~$0.000024 per vCPU-second beyond free quota).

## Pre-deploy gates

- Azure tenancy provisioned + subscription identified (Brock confirms)
- Phil has Contributor or Owner role on the subscription
- `state-backend-bootstrap.sh` has run successfully

## Security/HIPAA contact review

The VPC config, Key Vault access controls, LiteLLM proxy hardening, and
audit-log encryption key setup are partially owned by the security/HIPAA
contact (per docs/integration-contracts.md Section 2.5 reconciliations).
Have them review `infra/envs/dev/` when they engage.
