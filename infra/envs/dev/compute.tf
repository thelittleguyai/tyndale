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
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
        value = azurerm_cognitive_account.document_intelligence.endpoint
      }
      env {
        name  = "QDRANT_URL"
        value = "http://${azurerm_container_app.qdrant.ingress[0].fqdn}:6333"
      }
      env {
        name  = "LITELLM_PROXY_URL"
        value = "http://${azurerm_container_app.litellm.ingress[0].fqdn}:4000"
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
      env {
        name  = "AUTH_SUCCESS_REDIRECT"
        value = "https://dev.${var.dns_zone_name}/signed-in"
      }
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = "https://dev.${var.dns_zone_name},https://app.${var.dns_zone_name}"
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
        name        = "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        secret_name = "azure-doc-intelligence-key"
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

# LiteLLM proxy Container App
resource "azurerm_container_app" "litellm" {
  name                         = "${local.name_prefix}-litellm"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    min_replicas = 0
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
    external_enabled = false
    target_port      = 4000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# Qdrant Container App
resource "azurerm_container_app" "qdrant" {
  name                         = "${local.name_prefix}-qdrant"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    min_replicas = 0 # scale-to-zero
    max_replicas = 1 # single replica for dev

    container {
      name   = "qdrant"
      image  = "qdrant/qdrant:latest"
      cpu    = 0.5
      memory = "1Gi"
      # Storage persistence: Container Apps + volumes is more complex than dev needs;
      # dev runs ephemeral. Production attaches Azure Files. Note in README.
    }
  }

  ingress {
    external_enabled = false
    target_port      = 6333
    transport        = "http"

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
