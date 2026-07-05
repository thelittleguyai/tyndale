# ============================================================================
# Scheduled cron jobs (Phase 3.2)
# ----------------------------------------------------------------------------
# One Azure Container Apps Job per registered cron (runtime/app/crons/registry.py),
# cron-triggered, running `python -m app.crons <name>` on the runtime image. Each run
# records a CronRunLog row (triggered_source='scheduled'), so the admin console's existing
# real last-run panel reflects scheduled executions. Same CAE (external) + UAMI as the
# runtime, so they reach Postgres (VNet) + Qdrant (same CAE) exactly like the runtime does.
# 'noop' is deliberately NOT scheduled (manual smoke-test only). CI rolls the placeholder
# image to the runtime image (deploy-runtime.yml), and Terraform ignores that drift.
# ============================================================================

locals {
  # cron_expression is standard 5-field (min hour dom mon dow), UTC.
  scheduled_crons = {
    cms_ncd_lcd_bulk = { cron = "0 3 * * 0", timeout = 1800 }   # weekly, Sun 03:00
    medicare_pfs     = { cron = "0 4 5 1 *", timeout = 3600 }   # annual, ~Jan 5 04:00
    hospital_mrf     = { cron = "0 5 1-7 * 0", timeout = 1800 } # monthly, first Sun 05:00
    tic_mrf          = { cron = "0 6 1 * *", timeout = 1800 }   # monthly, 1st 06:00
    outcome_followup = { cron = "0 7 * * *", timeout = 600 }    # daily 07:00
    qdrant_snapshot  = { cron = "0 2 * * *", timeout = 900 }    # daily 02:00 (Phase 3.3 backup)
  }
}

resource "azurerm_container_app_job" "cron" {
  for_each = local.scheduled_crons

  # Azure caps Container App Job names at 32 chars; the longest keys (cms_ncd_lcd_bulk,
  # outcome_followup) overflow, so truncate the TAIL only — the "<prefix>-cron-" head stays
  # intact for the deploy workflow's starts_with() image-roll filter, and args=[each.key]
  # (below) carries the real registry key so behavior is unaffected by a trimmed name.
  name                         = substr("${local.name_prefix}-cron-${replace(each.key, "_", "-")}", 0, 32)
  container_app_environment_id = azurerm_container_app_environment.external.id
  resource_group_name          = azurerm_resource_group.main.name
  location                     = local.region
  tags                         = local.tags

  replica_timeout_in_seconds = each.value.timeout
  replica_retry_limit        = 1

  schedule_trigger_config {
    cron_expression          = each.value.cron
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
  secret {
    name                = "azure-storage-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.azure_storage_connection_string.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  secret {
    name                = "qdrant-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.qdrant_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }

  template {
    container {
      name   = "cron"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls to the runtime image
      cpu    = 0.5
      memory = "1Gi"

      command = ["python", "-m", "app.crons"]
      args    = [each.key]

      env {
        name  = "NODE_ENV"
        value = "development"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "VOYAGE_API_KEY"
        secret_name = "voyage-api-key"
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-connection-string"
      }
      env {
        name  = "QDRANT_URL"
        value = "http://${azurerm_container_app.qdrant.ingress[0].fqdn}:80"
      }
      env {
        name        = "QDRANT_API_KEY"
        secret_name = "qdrant-api-key"
      }
    }
  }

  # CI rolls the image to the runtime image per SHA; ignore that drift.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.runtime_kv_secrets_user]
}
