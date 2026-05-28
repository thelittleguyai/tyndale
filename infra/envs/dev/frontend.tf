# Azure Static Web Apps for the dev marketing landing.
# Free tier includes custom domains, SSL, and 100 GB bandwidth/month.
resource "azurerm_static_web_app" "marketing_dev" {
  name                = "${local.name_prefix}-marketing-swa"
  resource_group_name = azurerm_resource_group.main.name
  location            = "centralus" # SWA Free tier locations are limited; centralus supported
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

# Attach custom domain dev.tyndaleapp.net to the SWA.
# This requires the CNAME record (dns.tf) to be created first; depends_on enforces order.
resource "azurerm_static_web_app_custom_domain" "dev" {
  static_web_app_id = azurerm_static_web_app.marketing_dev.id
  domain_name       = "dev.${var.dns_zone_name}"
  validation_type   = "cname-delegation"

  depends_on = [
    azurerm_dns_cname_record.dev
  ]
}
