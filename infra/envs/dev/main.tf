locals {
  env         = var.environment
  region      = var.location
  name_prefix = "tyndale-${local.env}"

  tags = merge(var.common_tags, {
    environment = local.env
    region      = local.region
  })
}

resource "azurerm_resource_group" "main" {
  name     = "${local.name_prefix}-rg"
  location = local.region
  tags     = local.tags
}

# Random suffix to make globally-unique resource names (storage, key vault, etc.)
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
  numeric = true
}
