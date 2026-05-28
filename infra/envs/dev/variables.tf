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
  default     = "eastus2"
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
  description = "Postgres administrator password. Provide via TF_VAR_postgres_admin_password env var, NOT terraform.tfvars."
}

variable "common_tags" {
  type = map(string)
  default = {
    project    = "tyndale"
    managed_by = "terraform"
  }
}
