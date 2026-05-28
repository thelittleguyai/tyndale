# Public DNS zone for tyndaleapp.net.
# After first terraform apply, output the nameservers and update the
# registrar's NS records to point at Azure's nameservers.
resource "azurerm_dns_zone" "main" {
  name                = var.dns_zone_name
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

# CNAME for dev.tyndaleapp.net → Static Web App default hostname
# Validation TXT record is created automatically by Azure when the custom
# domain is attached to the SWA.
resource "azurerm_dns_cname_record" "dev" {
  name                = "dev"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  record              = azurerm_static_web_app.marketing_dev.default_host_name
  tags                = local.tags
}
