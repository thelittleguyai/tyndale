# Azure Static Web Apps for the dev marketing landing.
# Free tier includes custom domains, SSL, and 100 GB bandwidth/month.
resource "azurerm_static_web_app" "marketing_dev" {
  name                = "${local.name_prefix}-marketing-swa"
  resource_group_name = azurerm_resource_group.main.name
  location            = "centralus" # SWA Free tier locations are limited; centralus supported
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags

  # App settings consumed by Next.js / NextAuth at runtime. SWA Free tier
  # doesn't support KV-reference app settings (Standard tier only), so values
  # are passed in directly; Terraform marks them sensitive in tfstate.
  #
  # NEXTAUTH_URL is intentionally NOT set here: Auth.js v5 (the version in
  # apps/web-marketing/src/lib/auth.ts) auto-detects the URL from the inbound
  # request headers, so for V1-Lite the SWA default hostname and the future
  # dev.tyndaleapp.net both work without explicit config. If a later phase
  # needs NEXTAUTH_URL pinned (e.g. for external OAuth callback URLs), add it
  # via a null_resource + `az staticwebapp appsettings set` after the SWA
  # exists — an inline reference to default_host_name here triggers a
  # self-referential-block error.
  app_settings = {
    GOOGLE_CLIENT_ID     = var.google_oauth_client_id
    GOOGLE_CLIENT_SECRET = var.google_oauth_client_secret
    AUTH_SECRET          = random_password.nextauth_secret.result
  }
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
