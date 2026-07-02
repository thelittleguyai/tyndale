# Postgres Flexible — Burstable B1ms (cheapest production-shape tier)
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "${local.name_prefix}-postgres-flex-${random_string.suffix.result}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = local.region
  version                = "16"
  sku_name               = "B_Standard_B1ms"
  storage_mb             = 32768
  storage_tier           = "P4"
  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false # dev: no geo-redundant backups
  zone                         = "1"

  delegated_subnet_id = azurerm_subnet.postgres.id
  private_dns_zone_id = azurerm_private_dns_zone.postgres.id

  public_network_access_enabled = false # dev: no public access

  tags = local.tags

  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.postgres
  ]
}

resource "azurerm_postgresql_flexible_server_database" "tyndale" {
  name      = "tyndale"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "UTF8"
}

# Allow-list the extensions the schema needs. Azure Database for PostgreSQL
# Flexible Server blocks CREATE EXTENSION unless the extension name is in the
# server-level `azure.extensions` parameter — without this, the 0001 migration's
# `CREATE EXTENSION IF NOT EXISTS pgcrypto` fails with:
#   FeatureNotSupportedError: extension "pgcrypto" is not allow-listed ...
# (pgcrypto is used by the 0001 migration; gen_random_uuid() is core in PG16 but
# the extension is created defensively + may back future crypt()/digest() use.)
# This is a dynamic parameter — applied without a server restart.
resource "azurerm_postgresql_flexible_server_configuration" "azure_extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "PGCRYPTO"
}

# Storage Account — Standard LRS Hot for cheap dev
resource "azurerm_storage_account" "main" {
  name                     = "tyndale${local.env}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = local.region
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  access_tier              = "Hot"
  min_tls_version          = "TLS1_2"

  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true # dev: simpler; production should use Entra ID

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 7
    }
  }

  tags = local.tags
}

# Container for Qdrant snapshots (daily snapshot target per developer spec D9)
resource "azurerm_storage_container" "qdrant_snapshots" {
  name                  = "qdrant-snapshots"
  storage_account_id    = azurerm_storage_account.main.id # renamed from storage_account_name in azurerm 4.x
  container_access_type = "private"
}

# Container for uploaded user documents (also insurance-card images —
# routes/insurance.py passes this container to BlobStorage explicitly)
resource "azurerm_storage_container" "uploads" {
  name                  = "uploads"
  storage_account_id    = azurerm_storage_account.main.id # renamed from storage_account_name in azurerm 4.x
  container_access_type = "private"
}

# Container for bulk-data staging (Phase CO-3A: CMS MCD / Medicare PFS /
# Hospital MRF / TiC downloads) — BlobStorage's default container
# (config.py azure_storage_bulk_container = "bulk-data"). BlobStorage
# best-effort-creates it at runtime, but declare it so it exists regardless.
resource "azurerm_storage_container" "bulk_data" {
  name                  = "bulk-data"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# Key Vault — Standard tier
data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                = "${local.name_prefix}-kv-${random_string.suffix.result}"
  location            = local.region
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  enabled_for_disk_encryption     = false
  enabled_for_deployment          = false
  enabled_for_template_deployment = false
  purge_protection_enabled        = false # dev: skip purge protection for cheap cleanup
  soft_delete_retention_days      = 7

  rbac_authorization_enabled = true # Use RBAC, not access policies (renamed from enable_rbac_authorization in azurerm 4.x)

  # Dev env: default_action = "Allow" because the container_apps subnet is delegated
  # to Microsoft.App/environments, which precludes Microsoft.KeyVault service endpoints
  # on the same subnet. RBAC (rbac_authorization_enabled = true above) still enforces
  # auth on every secret-plane call. Production should switch to a private endpoint
  # + default_action = "Deny" model.
  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = local.tags
}

# Grant the deploying identity Key Vault Administrator for setup
resource "azurerm_role_assignment" "kv_admin_deployer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}
