# Container Apps Environment — consumption tier
resource "azurerm_container_app_environment" "main" {
  name                       = "${local.name_prefix}-cae"
  location                   = local.region
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  infrastructure_subnet_id       = azurerm_subnet.container_apps.id
  internal_load_balancer_enabled = true # dev: internal-only per developer spec

  tags = local.tags
}

# Runtime FastAPI Container App
resource "azurerm_container_app" "runtime" {
  name                         = "${local.name_prefix}-runtime"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    min_replicas = 0 # scale-to-zero for cheap dev
    max_replicas = 2

    container {
      name   = "runtime"
      image  = "mcr.microsoft.com/azuredocs/aci-helloworld" # placeholder; CI rolls this to ghcr.io/.../runtime:<sha>
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "PORT"
        value = "4000"
      }
      env {
        name  = "NODE_ENV"
        value = "development"
      }
      # DATABASE_URL etc. wired in Phase 2D when secrets land in Key Vault
    }
  }

  ingress {
    external_enabled = false # internal-only; SWA + Container App ingress wires later
    target_port      = 4000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # The image is rolled by .github/workflows/deploy-runtime.yml on each push to main.
  # Ignoring it here prevents subsequent `terraform apply`s from reverting to the
  # placeholder above; the runtime image is owned by CI from now on.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }
}

# LiteLLM proxy Container App
resource "azurerm_container_app" "litellm" {
  name                         = "${local.name_prefix}-litellm"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "litellm"
      image  = "ghcr.io/berriai/litellm:main-latest"
      cpu    = 0.5
      memory = "1Gi"
      # config.yaml mounted via secret/volume in Phase 4
    }
  }

  ingress {
    external_enabled = false
    target_port      = 4000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# Qdrant Container App
resource "azurerm_container_app" "qdrant" {
  name                         = "${local.name_prefix}-qdrant"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    min_replicas = 0 # scale-to-zero
    max_replicas = 1 # single replica for dev

    container {
      name   = "qdrant"
      image  = "qdrant/qdrant:latest"
      cpu    = 0.5
      memory = "1Gi"
      # Storage persistence: Container Apps + volumes is more complex than dev needs;
      # dev runs ephemeral. Production attaches Azure Files. Note in README.
    }
  }

  ingress {
    external_enabled = false
    target_port      = 6333
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}
