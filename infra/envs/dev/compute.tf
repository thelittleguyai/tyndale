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
  name                         = "${local.name_prefix}-runtime"
  container_app_environment_id = azurerm_container_app_environment.main.id
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
    key_vault_secret_id = azurerm_key_vault_secret.anthropic_api_key.id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "voyage-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.voyage_api_key.id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "azure-doc-intelligence-key"
    key_vault_secret_id = azurerm_key_vault_secret.azure_doc_intelligence_key.id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.id
    identity            = azurerm_user_assigned_identity.runtime.id
  }

  template {
    min_replicas = 0 # scale-to-zero for cheap dev
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
    }
  }

  ingress {
    external_enabled = false # internal-only; SWA + Container App ingress wires later
    target_port      = 4000
    transport        = "http"

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
    key_vault_secret_id = azurerm_key_vault_secret.database_url.id
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
    key_vault_secret_id = azurerm_key_vault_secret.google_oauth_client_secret.id
    identity            = azurerm_user_assigned_identity.marketing.id
  }
  secret {
    name                = "nextauth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.nextauth_secret.id
    identity            = azurerm_user_assigned_identity.marketing.id
  }

  template {
    min_replicas = 0 # scale-to-zero idle
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
