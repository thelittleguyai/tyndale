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
   ./infra/state-backend-bootstrap.sh <subscription_id> centralus
   ```

3. Update `infra/envs/dev/backend.tf` with the `storage_account_name` from the
   bootstrap output.

4. Copy `terraform.tfvars.example` to `terraform.tfvars` (gitignored) and fill
   in `subscription_id`, `tenant_id`, and `postgres_admin_password`. The
   password lives in `terraform.tfvars` so you don't have to re-export it
   every apply; if you'd rather keep it out of any file, alternatively:
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

## CI/CD deploys

The dev environment has two GitHub Actions workflows that ship code to the
already-provisioned infra. Both use the same shape: Docker build → GHCR push →
`az containerapp update`.

- `.github/workflows/deploy-runtime.yml` — builds `runtime/Dockerfile`, pushes
  to GHCR (`ghcr.io/thelittleguyai/tyndale/runtime:<sha>`), and rolls the
  `tyndale-dev-runtime` Container App (internal CAE) to the new image.
- `.github/workflows/deploy-web-marketing.yml` — builds
  `apps/web-marketing/Dockerfile` from the repo root (so the npm workspace dep
  `@tyndale/shared` resolves), pushes to GHCR
  (`ghcr.io/thelittleguyai/tyndale/web-marketing:<sha>`), and rolls the
  `tyndale-dev-marketing` Container App (external CAE) to the new image.

Both fire on push to `main` for the relevant paths plus manual
`workflow_dispatch`. Both run inside the GitHub `dev` environment so OIDC
subjects + secrets are env-scoped.

### One-time setup

1. **Create a `dev` GitHub environment** at
   `https://github.com/thelittleguyai/tyndale/settings/environments`
   (one click: "New environment" → "dev" → save; no protection rules needed).
   The workflows declare `environment: dev` so their secrets come from this
   environment, not the repo-level secret store. When staging/production
   land later, each gets its own environment + secrets without name
   collisions.

2. Run `./infra/setup-github-deploy.sh <subscription_id>` from the repo root.
   It creates an Azure AD app, federated OIDC credentials trusting three
   GitHub subjects (`environment:dev`, `ref:refs/heads/main`, `pull_request`),
   grants the SP `Contributor` on `tyndale-dev-rg` (RG-scoped, NOT
   subscription-wide), and prints the four GitHub secrets to add.

3. Add the three secrets at the **environment level** (NOT the repo level), at
   `https://github.com/thelittleguyai/tyndale/settings/environments/dev`:
   - `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (both deploy
     workflows use OIDC end-to-end; no per-service tokens needed).

4. Both Container Apps (`tyndale-dev-runtime`, `tyndale-dev-marketing`) have
   `lifecycle.ignore_changes = [template[0].container[0].image]` in
   `compute.tf` — CI owns their image attribute; subsequent
   `terraform apply`s won't revert to the placeholder.

### Rollback

- Runtime: `az containerapp update --name tyndale-dev-runtime --resource-group
  tyndale-dev-rg --image ghcr.io/thelittleguyai/tyndale/runtime:<previous-sha>`
  (or use the Azure portal's revision list to traffic-shift to an older revision).
- Web-marketing: re-run the workflow against an older commit, or use the SWA
  portal's deployment history.

### After the custom domain attaches

The first `terraform apply` with `enable_marketing_custom_domain = true` binds
`dev.tyndaleapp.net` to the marketing Container App with
`certificate_binding_type = "Disabled"` — HTTP only at first. To get HTTPS:

1. In the Azure portal, navigate to `tyndale-dev-marketing` Container App →
   **Custom domains** → click `dev.tyndaleapp.net` → **Add managed certificate**.
   Azure provisions a free Let's Encrypt cert (takes a few minutes).
2. Bind the cert to the custom domain (the portal can do both in one click).
3. The `lifecycle.ignore_changes` on `azurerm_container_app_custom_domain` in
   `compute.tf` prevents subsequent `terraform apply`s from reverting the
   cert binding.

Alternatively, Terraform-manage the cert later via
`azurerm_container_app_environment_managed_certificate` + updating the
custom domain resource's `container_app_environment_certificate_id`.

## Security/HIPAA contact review

The VPC config, Key Vault access controls, LiteLLM proxy hardening, and
audit-log encryption key setup are partially owned by the security/HIPAA
contact (per docs/integration-contracts.md Section 2.5 reconciliations).
Have them review `infra/envs/dev/` when they engage.
