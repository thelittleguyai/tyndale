variable "azure_subscription_id" {
  type        = string
  description = "Target Azure subscription ID."
}

variable "azure_tenant_id" {
  type        = string
  description = "Azure AD tenant ID."
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name (dev|staging|production)."
}

variable "location" {
  type        = string
  default     = "centralus"
  description = "Azure region."
}

variable "dns_zone_name" {
  type        = string
  default     = "tyndaleapp.net"
  description = "Public DNS zone hosted in Azure DNS."
}

variable "postgres_admin_username" {
  type        = string
  default     = "tyndale_admin"
  description = "Postgres administrator username."
}

variable "postgres_admin_password" {
  type        = string
  sensitive   = true
  description = "Postgres administrator password. Provide via terraform.tfvars (gitignored) or the TF_VAR_postgres_admin_password env var. Azure requires 8-128 chars with characters from 3 of: uppercase, lowercase, numbers, non-alphanumeric; cannot contain the admin username."
}

variable "anthropic_api_key" {
  type        = string
  sensitive   = true
  description = "Anthropic API key for the runtime (Claude calls)."
}

variable "voyage_api_key" {
  type        = string
  sensitive   = true
  description = "Voyage AI API key for embeddings + reranking (knowledge layer)."
}

variable "google_oauth_client_id" {
  type        = string
  sensitive   = true
  description = "Google OAuth 2.0 client ID for the marketing landing's NextAuth sign-in. Not strictly secret (exposed to the browser) but treated as sensitive in tfstate."
}

variable "google_oauth_client_secret" {
  type        = string
  sensitive   = true
  description = "Google OAuth 2.0 client secret for the marketing landing's NextAuth sign-in."
}

variable "enable_marketing_custom_domain" {
  type        = bool
  default     = false
  description = "Attach the dev.tyndaleapp.net custom domain to the marketing Container App (HTTP only). Set to true ONLY after DNS records (CNAME + asuid TXT) have propagated publicly; otherwise Azure's domain validation fails the apply. Flow: first apply with this false → DNS records get created in Azure DNS → wait for public propagation (a few minutes once the registrar NS points at Azure DNS) → set to true and re-apply."
}

variable "enable_marketing_managed_cert" {
  type        = bool
  default     = false
  description = "Provision the free managed TLS cert for dev.tyndaleapp.net via `az containerapp hostname bind` and bind it to the custom domain. Requires enable_marketing_custom_domain to also be true and the HTTP binding to be live (dev.tyndaleapp.net must return a 301 from the CA so Azure's HTTP validator can verify ownership). Requires az CLI on the apply host. Flip true on a follow-up apply once HTTP works."
}

variable "common_tags" {
  type = map(string)
  default = {
    project    = "tyndale"
    managed_by = "terraform"
  }
}
