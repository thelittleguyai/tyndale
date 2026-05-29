# Centralized secrets for the dev environment.
#
# Two channels:
#   * Key Vault — for secrets that the runtime container reads at startup
#     (via a UAMI with Key Vault Secrets User role + Container App `secret`
#     blocks referencing the KV secret ID).
#   * SWA app settings — for the marketing landing's NextAuth values. SWA
#     Free tier doesn't reliably support KV-reference app settings
#     (`@Microsoft.KeyVault(...)` syntax is Standard tier), so for dev we
#     mirror the relevant secrets straight into app settings while still
#     keeping them in KV for centralized storage.
#
# User-provided secrets (supplied by Phil in terraform.tfvars):
#   var.anthropic_api_key, var.voyage_api_key,
#   var.google_oauth_client_id, var.google_oauth_client_secret
#   var.sendgrid_api_key — OPTIONAL; empty string -> the KV secret and the
#     runtime's SENDGRID_API_KEY env are both skipped (count=0 / dynamic),
#     so the runtime logs the magic link instead of emailing it.
#
# Derived / auto-generated secrets:
#   random_password.nextauth_secret      — 64-char random secret (marketing app)
#   random_password.auth_secret          — 64-char random secret; the runtime's
#     HS256 signing key for session + magic-link JWTs (env AUTH_SECRET). No
#     external counterpart, so it is auto-generated rather than a tfvars input.
#   azurerm_cognitive_account...primary_access_key — DI primary key
#   azurerm_postgresql_flexible_server.main.fqdn   — for DATABASE_URL

# --- Auto-generated NextAuth secret -------------------------------------------
resource "random_password" "nextauth_secret" {
  length      = 64
  special     = true
  min_lower   = 8
  min_upper   = 8
  min_numeric = 8
  min_special = 4
}

# --- Auto-generated runtime AUTH_SECRET ---------------------------------------
# The runtime's HS256 signing key for session + magic-link JWTs. No external
# counterpart (unlike the Google secret), so Terraform owns it rather than a
# human supplying it via tfvars. NOTE: this lives in tfstate and is owned by
# Terraform — a state loss / regen rotates it and invalidates all live sessions.
# Acceptable for dev; revisit for prod (generate-once + ignore_changes).
resource "random_password" "auth_secret" {
  length      = 64
  special     = true
  min_lower   = 8
  min_upper   = 8
  min_numeric = 8
  min_special = 4
}

# --- User-assigned managed identity for the runtime Container App ------------
# UAMI lets us grant Key Vault access BEFORE the Container App resolves its
# secret references — avoids the chicken-and-egg of system-assigned identity.
resource "azurerm_user_assigned_identity" "runtime" {
  name                = "${local.name_prefix}-runtime-identity"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.region
  tags                = local.tags
}

resource "azurerm_role_assignment" "runtime_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.runtime.principal_id
}

# --- Same pattern for the marketing Container App ----------------------------
resource "azurerm_user_assigned_identity" "marketing" {
  name                = "${local.name_prefix}-marketing-identity"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.region
  tags                = local.tags
}

resource "azurerm_role_assignment" "marketing_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.marketing.principal_id
}

# --- Key Vault secrets -------------------------------------------------------
# Naming: SCREAMING-KEBAB matches the env var name with dashes instead of
# underscores (KV name rules), so the mapping is mechanical.

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "ANTHROPIC-API-KEY"
  value        = var.anthropic_api_key
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "voyage_api_key" {
  name         = "VOYAGE-API-KEY"
  value        = var.voyage_api_key
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "google_oauth_client_id" {
  name         = "GOOGLE-OAUTH-CLIENT-ID"
  value        = var.google_oauth_client_id
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "google_oauth_client_secret" {
  name         = "GOOGLE-OAUTH-CLIENT-SECRET"
  value        = var.google_oauth_client_secret
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "nextauth_secret" {
  name         = "NEXTAUTH-SECRET"
  value        = random_password.nextauth_secret.result
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "auth_secret" {
  name         = "AUTH-SECRET"
  value        = random_password.auth_secret.result
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

# SendGrid key is OPTIONAL: count=0 when var.sendgrid_api_key is empty, because
# Key Vault rejects empty secret values. With no secret created, the runtime's
# SENDGRID_API_KEY env is also skipped (see compute.tf) and it logs the link.
resource "azurerm_key_vault_secret" "sendgrid_api_key" {
  count        = var.sendgrid_api_key != "" ? 1 : 0
  name         = "SENDGRID-API-KEY"
  value        = var.sendgrid_api_key
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "azure_doc_intelligence_key" {
  name         = "AZURE-DOC-INTELLIGENCE-KEY"
  value        = azurerm_cognitive_account.document_intelligence.primary_access_key
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

resource "azurerm_key_vault_secret" "postgres_admin_password" {
  name         = "POSTGRES-ADMIN-PASSWORD"
  value        = var.postgres_admin_password
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}

# Full DATABASE_URL with embedded credentials — the runtime reads this as a
# single env var rather than assembling it from parts. ?ssl=require because
# Azure Postgres Flexible enforces TLS.
#
# urlencode() on the password is REQUIRED — Phil's actual password contains
# '@' and ':' which collide with the URL grammar's user-info separators and
# crash SQLAlchemy's URL parser with:
#   ValueError: invalid literal for int() with base 10: '<password-tail>@host:port'
resource "azurerm_key_vault_secret" "database_url" {
  name         = "DATABASE-URL"
  value        = "postgresql+asyncpg://${var.postgres_admin_username}:${urlencode(var.postgres_admin_password)}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.tyndale.name}?ssl=require"
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_admin_deployer]
}
