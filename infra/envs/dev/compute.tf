# Container Apps Environment — consumption tier
resource "azurerm_container_app_environment" "main" {
  name                       = "${local.name_prefix}-cae"
  location                   = local.region
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  infrastructure_subnet_id       = azurerm_subnet.container_apps.id
  internal_load_balancer_enabled = true # dev: internal-only per developer spec

  tags = local.tags
}

# Runtime FastAPI Container App
resource "azurerm_container_app" "runtime" {
  name = "${local.name_prefix}-runtime"
  # Runtime now lives in the EXTERNAL CAE so it can have a PUBLIC ingress
  # (fronts api.tyndaleapp.net). Same VNet as the internal CAE, so it still
  # reaches the VNet-only Postgres and the internal qdrant/litellm by FQDN.
  # NOTE: changing the environment forces a replace of this Container App.
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  # UAMI grants the Container App permission to read Key Vault secrets at
  # secret-resolution time. Defined in secrets.tf alongside the role assignment.
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.runtime.id]
  }

  # KV-backed secrets, resolved at Container App revision creation via the UAMI.
  secret {
    name                = "anthropic-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.anthropic_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "voyage-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.voyage_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "azure-doc-intelligence-key"
    key_vault_secret_id = azurerm_key_vault_secret.azure_doc_intelligence_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "azure-storage-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.azure_storage_connection_string.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "auth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.auth_secret.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  # Only present when a SendGrid key was supplied; otherwise the runtime logs
  # the magic link (dev stub). Gated on the same condition as the KV secret.
  dynamic "secret" {
    for_each = var.sendgrid_api_key != "" ? [1] : []
    content {
      name                = "sendgrid-api-key"
      key_vault_secret_id = azurerm_key_vault_secret.sendgrid_api_key[0].versionless_id
      identity            = azurerm_user_assigned_identity.runtime.id
    }
  }
  # Google OAuth client secret — the runtime now performs the OAuth exchange
  # (it owns auth), so it needs the same secret the marketing app has.
  secret {
    name                = "google-oauth-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.google_oauth_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  # Phase 3.3: Qdrant now requires auth; the client sends this key (config.qdrant_api_key).
  secret {
    name                = "qdrant-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.qdrant_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }

  template {
    min_replicas = 1 # kept warm — avoids 20-30s cold-start latency on user requests
    max_replicas = 2

    container {
      name   = "runtime"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls this to ghcr.io/.../runtime:<sha>
      cpu    = 0.5
      memory = "1Gi"

      # Plain env (non-secret)
      env {
        name  = "PORT"
        value = "4000"
      }
      env {
        name  = "NODE_ENV"
        value = "development"
      }
      # OCR (Azure Document Intelligence). Env names MUST match config.py's
      # azure_doc_intelligence_* settings fields: AZURE_DOC_INTELLIGENCE_*
      # (not AZURE_DOCUMENT_INTELLIGENCE_* — pydantic would ignore those).
      env {
        name  = "AZURE_DOC_INTELLIGENCE_ENDPOINT"
        value = azurerm_cognitive_account.document_intelligence.endpoint
      }
      # Real OCR is gated on `use_real_ocr` (terraform.tfvars; default false keeps
      # the deterministic stub even though the endpoint/key above are wired).
      env {
        name  = "USE_REAL_OCR"
        value = tostring(var.use_real_ocr)
      }
      env {
        name = "QDRANT_URL"
        # Container Apps HTTP ingress serves on :80/:443 and routes by Host header —
        # NOT the container's target_port (6333). Use the ingress port (:80, with
        # allow_insecure_connections on the qdrant ingress). Port is explicit because
        # qdrant-client defaults a portless URL to 6333.
        value = "http://${azurerm_container_app.qdrant.ingress[0].fqdn}:80"
      }
      env {
        name        = "QDRANT_API_KEY"
        secret_name = "qdrant-api-key"
      }
      # Real Claude via DIRECT Anthropic. LITELLM_PROXY_URL is intentionally unset so
      # the runtime's _client() goes straight to the Anthropic API — the litellm proxy
      # config/hardening is the security contact's Phase-4 work. Re-add LITELLM_PROXY_URL
      # (http://...litellm...:80) once that proxy is configured. Real calls are gated on
      # `use_real_claude` (terraform.tfvars; $ per call; default false).
      env {
        name  = "USE_REAL_CLAUDE"
        value = tostring(var.use_real_claude)
      }
      # CO-18 — Claude via Azure AI Foundry (managed identity; no key). USE_FOUNDRY
      # flips the code path; the endpoint / scope / deployment names come from the
      # Foundry resources (ai_foundry.tf) and are empty when enable_foundry is false.
      env {
        name  = "USE_FOUNDRY"
        value = tostring(var.use_foundry)
      }
      env {
        name  = "FOUNDRY_ENDPOINT"
        value = local.foundry_endpoint
      }
      env {
        name  = "FOUNDRY_TOKEN_SCOPE"
        value = var.foundry_token_scope
      }
      env {
        name  = "FOUNDRY_DEPLOYMENT_SONNET"
        value = local.foundry_deployment_sonnet
      }
      env {
        name  = "FOUNDRY_DEPLOYMENT_HAIKU"
        value = local.foundry_deployment_haiku
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
      # Auth: false keeps the seeded-admin dev stub; true requires real sign-in.
      env {
        name  = "USE_REAL_AUTH"
        value = tostring(var.use_real_auth)
      }
      env {
        name  = "SENDGRID_FROM_EMAIL"
        value = var.sendgrid_from_email
      }
      # Google OAuth + public-URL config. The redirect URI and magic-link base
      # URL MUST be the runtime's public host (api.tyndaleapp.net) so the
      # browser lands on a reachable callback and the session cookie can be set
      # on .tyndaleapp.net. CORS allows the web/app origins (with credentials).
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_oauth_client_id
      }
      env {
        name  = "GOOGLE_REDIRECT_URI"
        value = "https://api.${var.dns_zone_name}/v1/auth/callback"
      }
      env {
        name  = "MAGIC_LINK_BASE_URL"
        value = "https://api.${var.dns_zone_name}"
      }
      # Land sign-in directly on the product dashboard, skipping the marketing
      # /signed-in interstitial.
      env {
        name  = "AUTH_SUCCESS_REDIRECT"
        value = "https://app.${var.dns_zone_name}"
      }
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = "https://dev.${var.dns_zone_name},https://app.${var.dns_zone_name},https://admin.${var.dns_zone_name}"
      }
      # Azure Blob (Phase 2D uploads + CO-17 card images + CO-3A bulk staging).
      # routes/upload.py uses AZURE_STORAGE_ACCOUNT_URL + DefaultAzureCredential
      # (managed identity — backed by the Storage Blob Data Contributor role
      # assignment in secrets.tf). AZURE_CLIENT_ID pins DefaultAzureCredential to
      # the runtime UAMI — the Container App has NO system-assigned identity, so
      # without it the managed-identity probe fails and uploads fall back to the
      # replica's local disk. BlobStorage (blob_storage.py) additionally needs the
      # connection string (secret env below) — its SAS generation requires the
      # account key, which only the connection string carries.
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = trimsuffix(azurerm_storage_account.main.primary_blob_endpoint, "/")
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.runtime.client_id
      }

      # Secret env — bound to the secret blocks above.
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }
      env {
        name        = "VOYAGE_API_KEY"
        secret_name = "voyage-api-key"
      }
      env {
        name        = "AZURE_DOC_INTELLIGENCE_KEY"
        secret_name = "azure-doc-intelligence-key"
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-connection-string"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "AUTH_SECRET"
        secret_name = "auth-secret"
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "google-oauth-client-secret"
      }
      # Skipped entirely when no SendGrid key is supplied -> runtime logs the
      # link. Same gating condition as the secret block + KV secret.
      dynamic "env" {
        for_each = var.sendgrid_api_key != "" ? [1] : []
        content {
          name        = "SENDGRID_API_KEY"
          secret_name = "sendgrid-api-key"
        }
      }
    }
  }

  ingress {
    external_enabled           = true # PUBLIC — fronts api.tyndaleapp.net
    target_port                = 4000
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # The image is rolled by .github/workflows/deploy-runtime.yml on each push to main.
  # Ignoring it here prevents subsequent `terraform apply`s from reverting to the
  # placeholder above; the runtime image is owned by CI from now on.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.runtime_kv_secrets_user
  ]
}

# ===========================================================================
# Container Apps Job — runs Alembic migrations + dev seed against the
# VNet-only Postgres. Same internal CAE as the runtime CA so it can reach
# the private Postgres FQDN; same UAMI so it can resolve the KV-backed
# DATABASE_URL secret. CI rolls its image right before rolling the runtime
# CA's image, so migrations land before the new code starts serving.
# ===========================================================================
resource "azurerm_container_app_job" "runtime_migrations" {
  name                         = "${local.name_prefix}-runtime-migrations"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  location                     = local.region
  tags                         = local.tags

  replica_timeout_in_seconds = 600
  replica_retry_limit        = 1

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.runtime.id]
  }

  # DATABASE_URL is what both alembic + the seed need. Same KV-backed
  # secret the runtime CA uses, resolved through the same UAMI.
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }

  template {
    container {
      name   = "migrations"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls
      cpu    = 0.5
      memory = "1Gi"

      # `alembic.ini` is at /app in the runtime image (Dockerfile WORKDIR);
      # the alembic binary is on PATH via /app/.venv/bin. Seed script lives
      # at /app/scripts/seed_dev_dashboard.py and is idempotent.
      command = ["sh", "-c"]
      args = [
        "set -euo pipefail; alembic upgrade head; python scripts/seed_dev_dashboard.py"
      ]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "NODE_ENV"
        value = "development"
      }
    }
  }

  # CI rolls the image to the same SHA the runtime CA gets. Ignore drift on
  # subsequent terraform apply runs.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.runtime_kv_secrets_user
  ]
}

# ===========================================================================
# Qdrant knowledge-corpus seed job.
# Co-located in the EXTERNAL env with qdrant — cross-env routing into the
# internal `main` CAE is unsupported (the migrations job sits in `main` only
# because Postgres is VNet-only). Runs scripts/init_collections.py +
# scripts/seed_fixtures.py against the dev qdrant so chat/audit retrieval is
# grounded instead of hitting an empty index.
#
# Occasional/one-off: terraform creates it with a placeholder image; sync the
# image to the CURRENT runtime SHA and run it on demand (CI does NOT auto-roll
# or auto-start it, so you always seed with the running runtime's image + corpus):
#   SHA=$(az containerapp show -n ${local.name_prefix}-runtime -g ${local.name_prefix}-rg \
#           --query "properties.template.containers[0].image" -o tsv)
#   az containerapp job update -n ${local.name_prefix}-runtime-seed -g ${local.name_prefix}-rg --image "$SHA"
#   az containerapp job start  -n ${local.name_prefix}-runtime-seed -g ${local.name_prefix}-rg
#
# DATABASE_URL is bound only so app.config.Settings() instantiates (a required
# field); seeding touches qdrant + Voyage, never Postgres. VOYAGE_API_KEY unset
# -> deterministic stub vectors (search runs but isn't semantically meaningful).
# ===========================================================================
resource "azurerm_container_app_job" "runtime_seed" {
  name                         = "${local.name_prefix}-runtime-seed"
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  location                     = local.region
  tags                         = local.tags

  replica_timeout_in_seconds = 600
  replica_retry_limit        = 1

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.runtime.id]
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "voyage-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.voyage_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }

  template {
    container {
      name   = "seed"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; synced to the runtime SHA at seed time
      cpu    = 0.5
      memory = "1Gi"

      command = ["sh", "-c"]
      args = [
        "set -euo pipefail; python scripts/init_collections.py; python scripts/seed_fixtures.py"
      ]

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "VOYAGE_API_KEY"
        secret_name = "voyage-api-key"
      }
      env {
        name = "QDRANT_URL"
        # Same as the runtime: qdrant HTTP ingress on :80 (allow_insecure), not 6333.
        value = "http://${azurerm_container_app.qdrant.ingress[0].fqdn}:80"
      }
      env {
        name  = "TYNDALE_INTELLIGENCE_LAYER_ROOT"
        value = "/app/intelligence-layer"
      }
      env {
        name  = "NODE_ENV"
        value = "development"
      }
    }
  }

  # CI does not manage this job's image (it's synced manually at seed time).
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.runtime_kv_secrets_user
  ]
}

# LiteLLM proxy Container App.
# Co-located in the EXTERNAL env with the runtime (its only caller): a request
# from the external env into the internal `main` env's load balancer returns the
# platform "Unavailable" page even for a warm, healthy app — cross-env routing
# into an internal CAE is not supported. Same-env service-to-service IS. Ingress
# stays internal (external_enabled=false) so it's private within the VNet.
resource "azurerm_container_app" "litellm" {
  name                         = "${local.name_prefix}-litellm"
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    # min 1 (see qdrant): cross-env static-IP routing doesn't activate scale-to-zero apps.
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "litellm"
      image  = "ghcr.io/berriai/litellm:main-latest"
      cpu    = 0.5
      memory = "1Gi"
      # config.yaml mounted via secret/volume in Phase 4
    }
  }

  ingress {
    external_enabled           = false
    target_port                = 4000
    transport                  = "http"
    allow_insecure_connections = true # internal-only (external_enabled=false); lets the runtime reach it over plain http on :80

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# Qdrant Container App.
# Co-located in the EXTERNAL env with the runtime (see litellm above): cross-env
# routing into the internal `main` env returns the platform "Unavailable" page.
# Ingress stays internal (external_enabled=false) so qdrant is private. Ephemeral
# storage, so the env move (destroy/recreate) loses nothing.
# Phase 3.3: Azure Files storage registered on the (external) CAE that qdrant runs in,
# so the vector store survives restarts (previously ephemeral — a restart wiped every
# collection, including the 50-state seed).
resource "azurerm_container_app_environment_storage" "qdrant" {
  name                         = "qdrant-storage"
  container_app_environment_id = azurerm_container_app_environment.external.id
  account_name                 = azurerm_storage_account.main.name
  share_name                   = azurerm_storage_share.qdrant.name
  access_key                   = azurerm_storage_account.main.primary_access_key
  access_mode                  = "ReadWrite"
}

resource "azurerm_container_app" "qdrant" {
  name                         = "${local.name_prefix}-qdrant"
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  # Reuse the runtime UAMI (already Key Vault Secrets User) to pull the API-key secret.
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.runtime.id]
  }

  secret {
    name                = "qdrant-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.qdrant_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }

  template {
    # min 1 (NOT scale-to-zero): the runtime reaches qdrant via the env's static-IP
    # wildcard DNS (cross-environment). That path does NOT trigger KEDA scale-from-zero
    # activation, so a request to a 0-replica app returns the platform "Unavailable" 404.
    # One warm replica keeps it routable (and avoids cold-start latency). Cheap in dev.
    min_replicas = 1
    max_replicas = 1 # single replica for dev

    container {
      name   = "qdrant"
      image  = var.qdrant_image # PINNED (Phase 3.3) — never :latest
      cpu    = 0.5
      memory = "1Gi"

      # Auth: qdrant reads QDRANT__SERVICE__API_KEY; the runtime + cron jobs send the same key.
      env {
        name        = "QDRANT__SERVICE__API_KEY"
        secret_name = "qdrant-api-key"
      }

      # Persist collections on the Azure Files volume (qdrant's default storage dir).
      volume_mounts {
        name = "qdrant-storage"
        path = "/qdrant/storage"
      }
    }

    volume {
      name         = "qdrant-storage"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.qdrant.name
    }
  }

  ingress {
    external_enabled           = false
    target_port                = 6333
    transport                  = "http"
    allow_insecure_connections = true # internal-only (external_enabled=false); lets the runtime reach it over plain http on :80

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# ============================================================================
# EXTERNAL Container Apps Environment — for public-facing apps (marketing).
# Separate from the internal-only CAE above so the runtime/llm/qdrant stay
# VNet-private while the marketing landing can take public traffic.
# ============================================================================
resource "azurerm_container_app_environment" "external" {
  name                       = "${local.name_prefix}-cae-external"
  location                   = local.region
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  infrastructure_subnet_id       = azurerm_subnet.container_apps_external.id
  internal_load_balancer_enabled = false # public-facing

  tags = local.tags
}

# Marketing landing Container App — Next.js hybrid mode (SSR + API routes).
# External ingress on :3000 (next start default). UAMI grants KV secret access
# for NextAuth secrets.
resource "azurerm_container_app" "marketing" {
  name                         = "${local.name_prefix}-marketing"
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.marketing.id]
  }

  secret {
    name                = "google-oauth-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.google_oauth_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.marketing.id
  }
  secret {
    name                = "nextauth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.nextauth_secret.versionless_id
    identity            = azurerm_user_assigned_identity.marketing.id
  }

  template {
    min_replicas = 1 # kept warm — avoids cold-start latency on user requests
    max_replicas = 3

    container {
      name   = "marketing"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls this to ghcr.io/.../web-marketing:<sha>
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "NODE_ENV"
        value = "production"
      }
      env {
        name  = "PORT"
        value = "3000"
      }
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_oauth_client_id
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "google-oauth-client-secret"
      }
      env {
        name        = "AUTH_SECRET"
        secret_name = "nextauth-secret"
      }
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 3000
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # CI rolls the image on each push to main touching apps/web-marketing/**.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.marketing_kv_secrets_user
  ]
}

# Custom domain binding — gated behind enable_marketing_custom_domain.
# Same pattern as the prior SWA gate: first apply lays the DNS records; flip
# the variable to true on a follow-up apply once DNS propagates, then this
# attaches dev.tyndaleapp.net to the marketing Container App.
#
# certificate_binding_type = "Disabled" means HTTP only. The managed TLS
# cert + HTTPS binding is provisioned by null_resource.bind_marketing_cert
# below (gated by enable_marketing_managed_cert) — via `az containerapp
# hostname bind`, which atomically provisions the free Let's Encrypt cert
# AND binds it. Terraform can't do this declaratively because the managed
# cert resource depends on the binding existing first (Azure HTTP-validates
# the domain), but the binding wants to reference the cert ID, creating a
# dependency cycle.
resource "azurerm_container_app_custom_domain" "marketing_dev" {
  count                    = var.enable_marketing_custom_domain ? 1 : 0
  name                     = "dev.${var.dns_zone_name}"
  container_app_id         = azurerm_container_app.marketing.id
  certificate_binding_type = "Disabled"

  depends_on = [
    azurerm_dns_cname_record.dev,
    azurerm_dns_txt_record.asuid_dev,
  ]

  lifecycle {
    # `az containerapp hostname bind` mutates these out-of-band. Ignore the
    # drift so subsequent `terraform apply`s don't revert the cert binding.
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}

# Provisions the free managed TLS cert AND binds it to dev.tyndaleapp.net on
# the marketing Container App. Requires az CLI on the apply host. Runs once
# per binding change (triggered by the custom domain resource's ID).
#
# Flip enable_marketing_managed_cert = true in terraform.tfvars on a
# follow-up apply once the HTTP binding above is healthy and dev.tyndaleapp.net
# returns a 301 from the CA — Azure's HTTP validator needs to hit it.
resource "null_resource" "bind_marketing_cert" {
  count = var.enable_marketing_custom_domain && var.enable_marketing_managed_cert ? 1 : 0

  triggers = {
    custom_domain_id = azurerm_container_app_custom_domain.marketing_dev[0].id
    container_app_id = azurerm_container_app.marketing.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      az containerapp hostname bind \
        --hostname "dev.${var.dns_zone_name}" \
        --name "${azurerm_container_app.marketing.name}" \
        --resource-group "${azurerm_resource_group.main.name}" \
        --environment "${azurerm_container_app_environment.external.name}" \
        --validation-method HTTP
    EOT
  }

  depends_on = [
    azurerm_container_app_custom_domain.marketing_dev,
  ]
}

# Apex (root) custom domain — binds tyndaleapp.net to the SAME marketing
# Container App as dev, behind the same phased gates. Identical lifecycle to
# marketing_dev; the only difference is the hostname (the bare zone name) and
# that DNS validation rides the apex A + asuid TXT records (dns.tf) instead of a
# CNAME. A Container App can carry multiple custom domains, so dev + apex coexist.
resource "azurerm_container_app_custom_domain" "marketing_apex" {
  count                    = var.enable_marketing_apex_custom_domain ? 1 : 0
  name                     = var.dns_zone_name
  container_app_id         = azurerm_container_app.marketing.id
  certificate_binding_type = "Disabled"

  depends_on = [
    azurerm_dns_a_record.apex,
    azurerm_dns_txt_record.asuid_apex,
  ]

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}

# Managed TLS cert for the apex tyndaleapp.net — same `az containerapp hostname
# bind` pattern as the dev cert. Flip enable_marketing_apex_managed_cert = true
# on a follow-up apply once the apex HTTP binding is healthy (tyndaleapp.net
# returns a 301 from the CA so Azure's HTTP validator can verify ownership).
resource "null_resource" "bind_marketing_apex_cert" {
  count = var.enable_marketing_apex_custom_domain && var.enable_marketing_apex_managed_cert ? 1 : 0

  triggers = {
    custom_domain_id = azurerm_container_app_custom_domain.marketing_apex[0].id
    container_app_id = azurerm_container_app.marketing.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      az containerapp hostname bind \
        --hostname "${var.dns_zone_name}" \
        --name "${azurerm_container_app.marketing.name}" \
        --resource-group "${azurerm_resource_group.main.name}" \
        --environment "${azurerm_container_app_environment.external.name}" \
        --validation-method HTTP
    EOT
  }

  depends_on = [
    azurerm_container_app_custom_domain.marketing_apex,
  ]
}

# ===========================================================================
# api.tyndaleapp.net → runtime Container App (external CAE). Same gated,
# phased pattern as the marketing custom domain above:
#   1. apply with enable_runtime_custom_domain = false → DNS records (api
#      CNAME + asuid.api TXT) land; runtime is public on its raw
#      *.azurecontainerapps.io FQDN.
#   2. once api.tyndaleapp.net resolves, set enable_runtime_custom_domain =
#      true → attaches the hostname (HTTP).
#   3. set enable_runtime_managed_cert = true → provisions + binds the free
#      managed TLS cert via `az containerapp hostname bind`.
# The session-cookie auth REQUIRES this HTTPS subdomain — a raw
# azurecontainerapps.io host cannot set a cookie on .tyndaleapp.net.
# ===========================================================================
resource "azurerm_container_app_custom_domain" "runtime_api" {
  count                    = var.enable_runtime_custom_domain ? 1 : 0
  name                     = "api.${var.dns_zone_name}"
  container_app_id         = azurerm_container_app.runtime.id
  certificate_binding_type = "Disabled"

  depends_on = [
    azurerm_dns_cname_record.api,
    azurerm_dns_txt_record.asuid_api,
  ]

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}

resource "null_resource" "bind_runtime_cert" {
  count = var.enable_runtime_custom_domain && var.enable_runtime_managed_cert ? 1 : 0

  triggers = {
    custom_domain_id = azurerm_container_app_custom_domain.runtime_api[0].id
    container_app_id = azurerm_container_app.runtime.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      az containerapp hostname bind \
        --hostname "api.${var.dns_zone_name}" \
        --name "${azurerm_container_app.runtime.name}" \
        --resource-group "${azurerm_resource_group.main.name}" \
        --environment "${azurerm_container_app_environment.external.name}" \
        --validation-method HTTP
    EOT
  }

  depends_on = [
    azurerm_container_app_custom_domain.runtime_api,
  ]
}

# ===========================================================================
# Tyndale product app — Expo static web export served by nginx. Public at
# app.tyndaleapp.net (external CAE). No secrets: the API base URL is baked into
# the JS bundle at build time, and the runtime issues the session cookie on
# .tyndaleapp.net (shared across dev./app./api.). CI rolls the image.
# ===========================================================================
resource "azurerm_container_app" "app" {
  name                         = "${local.name_prefix}-app"
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    min_replicas = 1 # kept warm — avoids cold-start latency on user requests
    max_replicas = 3

    container {
      name   = "app"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls this to ghcr.io/.../app:<sha>
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 80 # nginx
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # CI rolls the image on each push to main touching apps/mobile/**.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }
}

# app.tyndaleapp.net → product app CA. Same phased pattern as the others:
#   1. apply with enable_app_custom_domain = false → DNS records land
#   2. enable_app_custom_domain = true  → attach hostname (HTTP)
#   3. enable_app_managed_cert  = true  → provision + bind managed TLS
resource "azurerm_container_app_custom_domain" "app" {
  count                    = var.enable_app_custom_domain ? 1 : 0
  name                     = "app.${var.dns_zone_name}"
  container_app_id         = azurerm_container_app.app.id
  certificate_binding_type = "Disabled"

  depends_on = [
    azurerm_dns_cname_record.app,
    azurerm_dns_txt_record.asuid_app,
  ]

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}

resource "null_resource" "bind_app_cert" {
  count = var.enable_app_custom_domain && var.enable_app_managed_cert ? 1 : 0

  triggers = {
    custom_domain_id = azurerm_container_app_custom_domain.app[0].id
    container_app_id = azurerm_container_app.app.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      az containerapp hostname bind \
        --hostname "app.${var.dns_zone_name}" \
        --name "${azurerm_container_app.app.name}" \
        --resource-group "${azurerm_resource_group.main.name}" \
        --environment "${azurerm_container_app_environment.external.name}" \
        --validation-method HTTP
    EOT
  }

  depends_on = [
    azurerm_container_app_custom_domain.app,
  ]
}

# ===========================================================================
# Phase CO-6A — admin console (admin.tyndaleapp.net), Brock-only. (DL-60)
#
# Dual-layer auth:
#   (1) APP layer    — runtime /v1/admin/* requires user_type='admin' (404 else).
#   (2) NETWORK layer — the ingress IP allowlist below.
#
# ████████████████████  FLAG FOR BROCK — IP ALLOWLIST  ████████████████████
# `var.admin_allowed_ip_ranges` defaults to an RFC-5737 TEST-NET placeholder
# (203.0.113.0/24) that matches NO real traffic. Because at least one "Allow"
# restriction is present, Azure DENIES every source IP not in the list — so with
# the default, the admin console is unreachable by EVERYONE, INCLUDING BROCK.
# Brock MUST set his real CIDRs (home/office + VPN/travel fallback) in
# terraform.tfvars (admin_allowed_ip_ranges) BEFORE `terraform apply`, or he
# locks himself out of his own console.
# ██████████████████████████████████████████████████████████████████████████
resource "azurerm_container_app" "admin" {
  name                         = "${local.name_prefix}-admin"
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.marketing.id]
  }

  secret {
    name                = "google-oauth-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.google_oauth_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.marketing.id
  }
  secret {
    name                = "nextauth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.nextauth_secret.versionless_id
    identity            = azurerm_user_assigned_identity.marketing.id
  }

  template {
    min_replicas = 1 # kept warm
    max_replicas = 2

    container {
      name   = "admin"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls to ghcr.io/.../admin:<sha>
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "NODE_ENV"
        value = "production"
      }
      env {
        name  = "PORT"
        value = "3000"
      }
      env {
        name  = "NEXT_PUBLIC_RUNTIME_URL"
        value = "https://api.${var.dns_zone_name}"
      }
      env {
        name  = "NEXT_PUBLIC_PLAUSIBLE_DOMAIN"
        value = "admin.${var.dns_zone_name}"
      }
      env {
        name  = "AUTH_URL"
        value = "https://admin.${var.dns_zone_name}"
      }
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_oauth_client_id
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "google-oauth-client-secret"
      }
      env {
        name        = "AUTH_SECRET"
        secret_name = "nextauth-secret"
      }
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 3000
    transport                  = "http"
    allow_insecure_connections = false

    # NETWORK-layer allowlist (DL-60). All restrictions are "Allow", so Azure
    # default-DENIES every other source IP (mixing Allow+Deny is invalid for
    # Container Apps — a single Allow set is the correct deny-by-default pattern).
    # SEE THE FLAG-FOR-BROCK BANNER ABOVE: the default range blocks everyone.
    dynamic "ip_security_restriction" {
      for_each = var.admin_allowed_ip_ranges
      content {
        action           = "Allow"
        name             = "admin-allow-${ip_security_restriction.key}"
        ip_address_range = ip_security_restriction.value
        description      = "Brock-provided admin allowlist entry"
      }
    }

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [
    azurerm_role_assignment.marketing_kv_secrets_user
  ]
}

# admin.tyndaleapp.net custom domain — same phased pattern as the others.
resource "azurerm_container_app_custom_domain" "admin" {
  count                    = var.enable_admin_custom_domain ? 1 : 0
  name                     = "admin.${var.dns_zone_name}"
  container_app_id         = azurerm_container_app.admin.id
  certificate_binding_type = "Disabled"

  depends_on = [
    azurerm_dns_cname_record.admin,
    azurerm_dns_txt_record.asuid_admin,
  ]

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}

resource "null_resource" "bind_admin_cert" {
  count = var.enable_admin_custom_domain && var.enable_admin_managed_cert ? 1 : 0

  triggers = {
    custom_domain_id = azurerm_container_app_custom_domain.admin[0].id
    container_app_id = azurerm_container_app.admin.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      az containerapp hostname bind \
        --hostname "admin.${var.dns_zone_name}" \
        --name "${azurerm_container_app.admin.name}" \
        --resource-group "${azurerm_resource_group.main.name}" \
        --environment "${azurerm_container_app_environment.external.name}" \
        --validation-method HTTP
    EOT
  }

  depends_on = [
    azurerm_container_app_custom_domain.admin,
  ]
}
