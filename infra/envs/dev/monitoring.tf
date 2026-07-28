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
