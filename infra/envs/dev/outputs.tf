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
  value       = var.enable_swa_custom_domain ? "https://dev.${var.dns_zone_name}" : "https://${azurerm_static_web_app.marketing_dev.default_host_name} (custom domain disabled — set enable_swa_custom_domain = true after DNS propagates)"
  description = "Dev marketing landing URL. Shows the SWA default hostname until the custom domain is enabled + DNS is live."
}

output "marketing_dev_swa_default_hostname" {
  value       = azurerm_static_web_app.marketing_dev.default_host_name
  description = "SWA default hostname before custom domain propagates."
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
