resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name_prefix}-law"
  location            = local.region
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 1 # dev: cap worst-case ingestion (runaway-cost circuit breaker; lower to 0.5 to tighten)
  tags                = local.tags
}

resource "azurerm_application_insights" "main" {
  name                = "${local.name_prefix}-appi"
  location            = local.region
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.tags
}

# ============================================================================
# "Needs a person" — the alert path (readiness B2; e2e re-test 2026-09-23 item 3)
# ----------------------------------------------------------------------------
# The system_error apology tells the user "the team has been notified". Admin › System lists
# it, but a panel nobody opens notifies nobody. This rule reads the runtime's and the crons'
# own log lines and mails a person when an audit ends system_error or a recovery re-run gives
# up. The lines carry ids and error classes only — no document content, no member data.
# alert_email empty (the default) = the rule still fires into Azure Monitor (portal › Alerts)
# but mails nobody: set it in terraform.tfvars.
# ============================================================================

resource "azurerm_monitor_action_group" "needs_a_person" {
  count               = var.alert_email != "" ? 1 : 0
  name                = "${local.name_prefix}-needs-a-person"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "needsperson"
  tags                = local.tags

  email_receiver {
    name                    = "on-call"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "audit_system_error" {
  name                 = "${local.name_prefix}-audit-system-error"
  resource_group_name  = azurerm_resource_group.main.name
  location             = local.region
  scopes               = [azurerm_log_analytics_workspace.main.id]
  description          = "An audit ended system_error (the user was told the team was notified), or the audit_retry cron gave up re-running one. Open Admin › System › Needs a person."
  display_name         = "Tyndale dev — an audit needs a person"
  severity             = 1
  evaluation_frequency = "PT15M"
  window_duration      = "PT15M"
  tags                 = local.tags

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s contains "audit.system_error"
          or Log_s contains "orchestrator.finalize.failed"
          or Log_s contains "audit_retry.recovery_exhausted"
      | project TimeGenerated, ContainerAppName_s, ContainerJobName_s, Log_s
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  dynamic "action" {
    for_each = var.alert_email != "" ? [1] : []
    content {
      action_groups = [azurerm_monitor_action_group.needs_a_person[0].id]
    }
  }
}
