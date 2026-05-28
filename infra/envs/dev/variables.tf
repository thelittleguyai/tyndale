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

variable "enable_swa_custom_domain" {
  type        = bool
  default     = false
  description = "Attach the dev.tyndaleapp.net custom domain to the Static Web App. Set to true ONLY after the registrar's NS records are pointed at Azure's nameservers AND DNS has propagated; otherwise Azure's CNAME validation fails the apply. Flow: first apply with this false → terraform output dns_zone_nameservers → update registrar → wait for propagation → set to true and re-apply."
}

variable "common_tags" {
  type = map(string)
  default = {
    project    = "tyndale"
    managed_by = "terraform"
  }
}
