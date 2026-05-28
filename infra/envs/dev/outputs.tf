output "resource_group_name" {
  value       = azurerm_resource_group.main.name
  description = "Resource group containing all dev resources."
}

output "dns_zone_nameservers" {
  value       = azurerm_dns_zone.main.name_servers
  description = "Azure nameservers. UPDATE THE REGISTRAR FOR tyndaleapp.net TO POINT TO THESE."
}

output "dns_zone_id" {
  value = azurerm_dns_zone.main.id
}

output "marketing_dev_url" {
  value       = var.enable_marketing_custom_domain ? "https://dev.${var.dns_zone_name}" : "https://${azurerm_container_app.marketing.ingress[0].fqdn} (custom domain disabled — set enable_marketing_custom_domain = true after DNS propagates)"
  description = "Dev marketing landing URL. Shows the Container App FQDN until the custom domain is attached."
}

output "marketing_dev_container_app_fqdn" {
  value       = azurerm_container_app.marketing.ingress[0].fqdn
  description = "Marketing Container App's external FQDN."
}

output "marketing_dev_custom_domain_verification_id" {
  value       = azurerm_container_app_environment.external.custom_domain_verification_id
  description = "Verification ID Azure expects in the asuid.dev TXT record (Terraform sets this automatically)."
}

output "postgres_fqdn" {
  value       = azurerm_postgresql_flexible_server.main.fqdn
  description = "Postgres Flexible FQDN (internal only)."
}

output "postgres_database_name" {
  value = azurerm_postgresql_flexible_server_database.tyndale.name
}

output "key_vault_uri" {
  value       = azurerm_key_vault.main.vault_uri
  description = "Key Vault URI for secrets."
}

output "document_intelligence_endpoint" {
  value       = azurerm_cognitive_account.document_intelligence.endpoint
  description = "Document Intelligence endpoint URL."
}

output "document_intelligence_key_secret_name" {
  value       = "AZURE-DOC-INTELLIGENCE-KEY"
  description = "Key Vault secret name where the DI primary key should be stored after deploy. Phil sets via: az keyvault secret set --vault-name <kv> --name AZURE-DOC-INTELLIGENCE-KEY --value <key>"
}

output "container_app_runtime_fqdn" {
  value       = azurerm_container_app.runtime.ingress[0].fqdn
  description = "Runtime Container App FQDN (internal)."
}

output "container_app_litellm_fqdn" {
  value       = azurerm_container_app.litellm.ingress[0].fqdn
  description = "LiteLLM proxy FQDN (internal)."
}

output "container_app_qdrant_fqdn" {
  value       = azurerm_container_app.qdrant.ingress[0].fqdn
  description = "Qdrant FQDN (internal)."
}
