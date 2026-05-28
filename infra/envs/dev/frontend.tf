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
# Gated behind var.enable_swa_custom_domain (default false) because Azure validates
# the CNAME via public DNS, which requires the registrar's NS records to be pointed
# at Azure's nameservers AND for DNS to have propagated. The first apply will create
# the DNS zone + CNAME record but leave this resource off; flip the variable to true
# on a later apply once DNS is live. See variables.tf for the full flow.
resource "azurerm_static_web_app_custom_domain" "dev" {
  count             = var.enable_swa_custom_domain ? 1 : 0
  static_web_app_id = azurerm_static_web_app.marketing_dev.id
  domain_name       = "dev.${var.dns_zone_name}"
  validation_type   = "cname-delegation"

  depends_on = [
    azurerm_dns_cname_record.dev
  ]
}
