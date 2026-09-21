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
#
# ADDING A CRON: terraform creates the new job WITH the placeholder image, and it keeps it
# until the next runtime deploy rolls the fleet — meanwhile the schedule fires a hello-world
# container that idles to the job timeout and shows as Failed (stuck_audits, 2026-09-18).
# After the apply, either dispatch deploy-runtime or roll the one job by hand:
#   az containerapp job update -n tyndale-dev-cron-<name> -g tyndale-dev-rg \
#     --image "$(az containerapp show -n tyndale-dev-runtime -g tyndale-dev-rg \
#       --query 'properties.template.containers[0].image' -o tsv)"
#
# CHANGING A SCHEDULE IS SAFE — it is an in-place update. The 2026-09-18 deep review said
# `schedule_trigger_config` is ForceNew (so editing a `cron =` below would destroy + recreate
# the job on the placeholder). CHECKED 2026-09-21 against the pinned provider with a real plan
# of a one-field change: "azurerm_container_app_job.cron["nudge"] will be updated in-place …
# Plan: 0 to add, 1 to change, 0 to destroy". An earlier revision of this comment repeated the
# review's claim as fact; it was wrong. What DOES reopen the placeholder door is anything the
# plan reports as "will be created" or "must be replaced" for a job (a new cron, a rename, a
# provider upgrade that changes the rule) — so the habit stands: READ THE PLAN, and after an
# apply that created or replaced a job, roll it (above). The check lives in
# docs/build-kit/DEV_TEST_DAY.md §0.3.
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
    # Registered in the runtime since the P0 analytics sprint but never scheduled here, so
    # the admin dashboard's daily metrics silently never accumulated (deep review, finding 3).
    # 04:00 UTC, after qdrant_snapshot, matching the registry's stated cadence.
    analytics_rollup = { cron = "0 4 * * *", timeout = 900 }  # nightly 04:00
    nudge            = { cron = "0 15 * * *", timeout = 600 } # daily 15:00 (registry cadence)
    # Heals audits a deploy roll / OOM stranded in audit_running (2026-09-18): the boot-time
    # reconcile sweep, on a schedule, so a strand between deploys is bounded instead of open.
    stuck_audits = { cron = "*/15 * * * *", timeout = 300 } # every 15 min
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
  workload_profile_name        = "Consumption" # see compute.tf CAE workload_profile note
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
  # Crons write system_action audit rows through the shared envelope
  # (app/crons/_cron_util.audit_cron_run) — without the key here, cron-written
  # audit payloads would persist clear-text even after the runtime is keyed.
  secret {
    name                = "audit-log-enc-key"
    key_vault_secret_id = azurerm_key_vault_secret.audit_log_enc_key.versionless_id
    identity            = azurerm_user_assigned_identity.runtime.id
  }
  # Audit 2026-08-27 item 4 (third life of this bug): the nudge cron read
  # enable_nudge_emails + the SendGrid pair from Settings, but the job env never carried
  # them — every send silently skipped while tfvars said true. Same conditional as
  # compute.tf's runtime app.
  dynamic "secret" {
    for_each = var.sendgrid_api_key != "" ? [1] : []
    content {
      name                = "sendgrid-api-key"
      key_vault_secret_id = azurerm_key_vault_secret.sendgrid_api_key[0].versionless_id
      identity            = azurerm_user_assigned_identity.runtime.id
    }
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
      env {
        name        = "AUDIT_LOG_ENC_KEY"
        secret_name = "audit-log-enc-key"
      }
      env {
        name  = "AUDIT_LOG_KEY_VERSION"
        value = tostring(var.audit_log_key_version)
      }
      env {
        name  = "ENABLE_NUDGE_EMAILS"
        value = tostring(var.enable_nudge_emails)
      }
      env {
        name  = "ENABLE_AUDIT_READY_EMAIL"
        value = tostring(var.enable_audit_ready_email)
      }
      # stuck_audits (2026-09-18) reconciles through the orchestrator's status chokepoint: the
      # thread projection, the result projection (_assemble_result) and the review-queue policy
      # all run INSIDE the cron. Everything below is what that path reads that the runtime
      # container also carries — the list is ENFORCED, not remembered:
      # runtime/tests/test_flag_env_wiring.py walks the cron path's Settings reads and fails
      # when the runtime wires one that this block does not (deep review C4).
      env {
        name  = "ENABLE_CHAT_FIRST_AUDIT"
        value = tostring(var.enable_chat_first_audit)
      }
      # thread_bridge posts the D5 record message on a terminal status only when this is on —
      # without it a cron-healed case silently omitted the message the runtime path emits.
      env {
        name  = "ENABLE_RECORD_VIEW"
        value = tostring(var.enable_record_view)
      }
      # _regime_provenance (inside _assemble_result) adds "No Surprises Act checks are not yet
      # enabled" when this is off — with the runtime on and the cron off, a cron-projected
      # result would say something false.
      env {
        name  = "ENABLE_NSA_CHECKS"
        value = tostring(var.enable_nsa_checks)
      }
      # The healer's threshold = max(3 x budget, floor): both halves, same source as the runtime.
      env {
        name  = "AUDIT_WALL_CLOCK_BUDGET_SECONDS"
        value = tostring(var.audit_wall_clock_budget_seconds)
      }
      env {
        name  = "AUDIT_RECONCILE_STALE_SECONDS"
        value = tostring(var.audit_reconcile_stale_seconds)
      }
      # review/queue.py::decide() reads the dial and ALL FIVE triggers; only SYSTEM_ERROR was
      # wired, so flipping any other in tfvars applied to the API and not to cron-healed runs.
      env {
        name  = "REVIEW_SAMPLE_PCT"
        value = tostring(var.review_sample_pct)
      }
      env {
        name  = "REVIEW_TRIGGER_FIRST_CASE"
        value = tostring(var.review_trigger_first_case)
      }
      env {
        name  = "REVIEW_TRIGGER_LOW_CONFIDENCE"
        value = tostring(var.review_trigger_low_confidence)
      }
      env {
        name  = "REVIEW_TRIGGER_SYSTEM_ERROR"
        value = tostring(var.review_trigger_system_error)
      }
      env {
        name  = "REVIEW_TRIGGER_CANARY"
        value = tostring(var.review_trigger_canary)
      }
      env {
        name  = "REVIEW_TRIGGER_MATERIAL_DISAGREEMENT"
        value = tostring(var.review_trigger_material_disagreement)
      }
      env {
        name  = "SENDGRID_FROM_EMAIL"
        value = var.sendgrid_from_email
      }
      dynamic "env" {
        for_each = var.sendgrid_api_key != "" ? [1] : []
        content {
          name        = "SENDGRID_API_KEY"
          secret_name = "sendgrid-api-key"
        }
      }
      env {
        name  = "AUTH_SUCCESS_REDIRECT"
        value = "https://app.${var.dns_zone_name}"
      }
    }
  }

  # CI rolls the image to the runtime image per SHA; ignore that drift.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.runtime_kv_secrets_user]
}
