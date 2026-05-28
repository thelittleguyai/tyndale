resource "azurerm_cognitive_account" "document_intelligence" {
  name                = "${local.name_prefix}-doc-intel"
  location            = local.region
  resource_group_name = azurerm_resource_group.main.name
  kind                = "FormRecognizer"
  sku_name            = "F0" # Free tier: 500 pages/month
  tags                = local.tags

  custom_subdomain_name = "${local.name_prefix}-doc-intel"
}
