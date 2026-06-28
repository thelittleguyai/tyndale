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

# CNAME for app.tyndaleapp.net → product app Container App FQDN (external CAE).
resource "azurerm_dns_cname_record" "app" {
  name                = "app"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  record              = azurerm_container_app.app.ingress[0].fqdn
  tags                = local.tags
}

# TXT asuid.app = external CAE's custom-domain verification ID. Azure checks
# this when attaching app.tyndaleapp.net.
resource "azurerm_dns_txt_record" "asuid_app" {
  name                = "asuid.app"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  tags                = local.tags

  record {
    value = azurerm_container_app_environment.external.custom_domain_verification_id
  }
}

# CNAME for admin.tyndaleapp.net → admin console Container App FQDN (Phase CO-6A).
resource "azurerm_dns_cname_record" "admin" {
  name                = "admin"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  record              = azurerm_container_app.admin.ingress[0].fqdn
  tags                = local.tags
}

# TXT asuid.admin = external CAE's custom-domain verification ID. Azure checks
# this when attaching admin.tyndaleapp.net.
resource "azurerm_dns_txt_record" "asuid_admin" {
  name                = "asuid.admin"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  tags                = local.tags

  record {
    value = azurerm_container_app_environment.external.custom_domain_verification_id
  }
}

# ---------------------------------------------------------------------------
# APEX (root) tyndaleapp.net → same marketing Container App as dev.
#
# The apex of a zone CANNOT be a CNAME (RFC 1034 — the apex already carries the
# zone's SOA/NS records). So instead of a CNAME-to-FQDN like the `dev` record,
# the apex uses an A record pointing at the external Container Apps Environment's
# static inbound IP. Container Apps routes by Host header, so the marketing app
# serves any custom domain bound to it (dev + apex both → marketing).
resource "azurerm_dns_a_record" "apex" {
  name                = "@"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  records             = [azurerm_container_app_environment.external.static_ip_address]
  tags                = local.tags
}

# TXT asuid.tyndaleapp.net (apex verification) = external CAE's custom-domain
# verification ID. For an apex/root custom domain the verification record name is
# "asuid" (vs "asuid.<sub>" for a subdomain). Azure looks this up when attaching
# the root tyndaleapp.net custom domain to the marketing Container App.
resource "azurerm_dns_txt_record" "asuid_apex" {
  name                = "asuid"
  zone_name           = azurerm_dns_zone.main.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  tags                = local.tags

  record {
    value = azurerm_container_app_environment.external.custom_domain_verification_id
  }
}
