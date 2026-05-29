# Public DNS zone for tyndaleapp.net.
# Registrar (Route 53 Domains) NS records must point at the name_servers
# attribute of this zone (output: dns_zone_nameservers).
resource "azurerm_dns_zone" "main" {
  name                = var.dns_zone_name
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

# CNAME for dev.tyndaleapp.net → marketing Container App FQDN.
resource "azurerm_dns_cname_record" "dev" {
  name                = "dev"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  record              = azurerm_container_app.marketing.ingress[0].fqdn
  tags                = local.tags
}

# TXT record asuid.dev.tyndaleapp.net = Container App Environment's custom
# domain verification ID. Azure looks this up when attaching the custom
# domain to verify domain ownership. Required before the
# azurerm_container_app_custom_domain resource can succeed.
resource "azurerm_dns_txt_record" "asuid_dev" {
  name                = "asuid.dev"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  tags                = local.tags

  record {
    value = azurerm_container_app_environment.external.custom_domain_verification_id
  }
}

# CNAME for api.tyndaleapp.net → runtime Container App FQDN (now in the external
# CAE, so it has a public FQDN).
resource "azurerm_dns_cname_record" "api" {
  name                = "api"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  record              = azurerm_container_app.runtime.ingress[0].fqdn
  tags                = local.tags
}

# TXT asuid.api = external CAE's custom-domain verification ID (same env as the
# marketing CA). Azure checks this when attaching api.tyndaleapp.net.
resource "azurerm_dns_txt_record" "asuid_api" {
  name                = "asuid.api"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  tags                = local.tags

  record {
    value = azurerm_container_app_environment.external.custom_domain_verification_id
  }
}
