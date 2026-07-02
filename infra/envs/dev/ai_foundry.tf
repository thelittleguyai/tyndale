# ============================================================================
# Azure AI Foundry + Claude (CO-18 / DL-79)
# ----------------------------------------------------------------------------
# Routes Claude through Microsoft Foundry (the Anthropic Messages API at
# https://{account}.services.ai.azure.com/anthropic) so the Azure BAA covers
# Claude. The runtime authenticates with its managed identity (Entra) — NO API
# key — via the Cognitive Services User role granted below.
#
# Everything here is gated by `enable_foundry` (default false) so the plan is a
# clean, reviewable no-op until you opt in. Deploy order (see DL-79 note):
#   1. apply with enable_foundry = true  -> lands account + deployments + RBAC
#   2. once the deployments resolve, set use_foundry = true -> flips the code path
#
# Resource shapes follow the official Azure-Samples/claude Terraform:
#   - The Foundry account is an azapi_resource (kind = AIServices) with a custom
#     subdomain (required for Entra token auth).
#   - Each Claude deployment is an azapi_resource with schema_validation_enabled
#     = false so the `modelProviderData` block (which azurerm_cognitive_deployment
#     does not yet expose — hashicorp/terraform-provider-azurerm#31140) can be set.
#     That block auto-accepts the Anthropic Azure Marketplace offer on apply.
#
# HOSTING / RESIDENCY NOTE (verified against the Foundry model catalog + MS docs,
# 2026-06-29). Foundry offers Claude in two lines: version 1 = "Hosted on Anthropic"
# (runs on Anthropic infra) and version 2 = "Hosted on Azure" (runs end-to-end on
# Azure — the stronger residency/BAA posture, and Data-Zone-Standard eligible). Per
# model used here:
#   * claude-sonnet-4-6 — Hosted on Anthropic ONLY (v1), GlobalStandard only. This is
#     the runtime's LP/BD/MP trio, so that traffic runs on Anthropic infra (still
#     Azure-BAA-covered via Foundry, but NOT end-to-end on Azure). For a fully
#     Azure-hosted trio, switch the model to claude-sonnet-5 (Hosted on Azure, v2).
#   * claude-haiku-4-5 — available BOTH ways; we deploy v2 (Hosted on Azure), the GA
#     default. Deploying v1 (Hosted on Anthropic) returned DeploymentModelNotSupported.
# DataZoneStandard (US residency) is available for the Azure-hosted models
# (claude-haiku-4-5 v2, claude-sonnet-5, claude-opus-4-8), NOT claude-sonnet-4-6.
# Deployments use var.foundry_deployment_sku (default GlobalStandard).
# ============================================================================

locals {
  foundry_account_name = var.foundry_account_name != "" ? var.foundry_account_name : "${local.name_prefix}-foundry"
  # The Anthropic Messages API lives at /anthropic on the account's services.ai
  # host. Pure string + flag (no count-gated resource ref) so the container env
  # below is safe when enable_foundry = false.
  foundry_endpoint = var.enable_foundry ? "https://${local.foundry_account_name}.services.ai.azure.com" : ""
  # Deployments are named after the model ids, so the deployment name the runtime
  # passes as `model` equals what claude_model_for(role) already resolves.
  foundry_deployment_sonnet = var.enable_foundry ? var.claude_sonnet_model : ""
  foundry_deployment_haiku  = var.enable_foundry ? var.claude_haiku_model : ""
}

# --- Foundry account (kind = AIServices) -----------------------------------
resource "azapi_resource" "foundry" {
  count     = var.enable_foundry ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts@2025-10-01-preview"
  name      = local.foundry_account_name
  parent_id = azurerm_resource_group.main.id
  location  = var.foundry_location
  tags      = local.tags

  body = {
    kind = "AIServices"
    sku  = { name = "S0" }
    properties = {
      # Custom subdomain is REQUIRED for Entra (token) auth.
      customSubDomainName = local.foundry_account_name
      publicNetworkAccess = "Enabled"
      disableLocalAuth    = false # keep the account key available as an emergency fallback
    }
  }

  response_export_values = ["name", "properties.endpoint"]
}

# --- Claude deployments -----------------------------------------------------
# schema_validation_enabled = false is required to send modelProviderData.
# versionUpgradeOption/raiPolicyName mirror the official starter kit.
resource "azapi_resource" "claude_sonnet" {
  count                     = var.enable_foundry ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview"
  name                      = var.claude_sonnet_model
  parent_id                 = azapi_resource.foundry[0].id
  schema_validation_enabled = false

  body = {
    sku = {
      name     = var.foundry_deployment_sku
      capacity = var.foundry_sonnet_capacity
    }
    properties = {
      model = {
        format  = "Anthropic"
        name    = var.claude_sonnet_model
        version = var.foundry_sonnet_version
      }
      modelProviderData = {
        organizationName = var.claude_organization_name
        countryCode      = var.claude_country_code
        industry         = var.claude_industry
      }
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
      raiPolicyName        = "Microsoft.DefaultV2"
    }
  }

  depends_on = [azurerm_role_assignment.foundry_runtime]
}

resource "azapi_resource" "claude_haiku" {
  count                     = var.enable_foundry ? 1 : 0
  type                      = "Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview"
  name                      = var.claude_haiku_model
  parent_id                 = azapi_resource.foundry[0].id
  schema_validation_enabled = false

  body = {
    sku = {
      name     = var.foundry_deployment_sku
      capacity = var.foundry_haiku_capacity
    }
    properties = {
      model = {
        format  = "Anthropic"
        name    = var.claude_haiku_model
        version = var.foundry_haiku_version
      }
      modelProviderData = {
        organizationName = var.claude_organization_name
        countryCode      = var.claude_country_code
        industry         = var.claude_industry
      }
      versionUpgradeOption = "OnceNewDefaultVersionAvailable"
      raiPolicyName        = "Microsoft.DefaultV2"
    }
  }

  # Serialize after Sonnet — Foundry 409s on concurrent per-account deployment creates.
  depends_on = [azapi_resource.claude_sonnet, azurerm_role_assignment.foundry_runtime]
}

# --- RBAC: runtime managed identity -> Cognitive Services User -------------
# Least-privilege data-plane role for keyless inference (Microsoft.Cognitive
# Services/accounts/MaaS/*). Granted to the runtime's user-assigned identity.
resource "azurerm_role_assignment" "foundry_runtime" {
  count                = var.enable_foundry ? 1 : 0
  scope                = azapi_resource.foundry[0].id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_user_assigned_identity.runtime.principal_id
}
