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

variable "sendgrid_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "SendGrid Email API key (Pro tier under a BAA, per DL-18) for sending magic-link sign-in emails. OPTIONAL: leave empty and the runtime logs the sign-in link instead of emailing it — the KV secret and the runtime's SENDGRID_API_KEY env wiring are both skipped, so apply succeeds without a SendGrid account. Set it to a real 'SG.…' value to send real email."
}

variable "sendgrid_from_email" {
  type        = string
  default     = "no-reply@tyndaleapp.net"
  description = "From-address for magic-link emails. Must be a verified SendGrid sender (domain or single-sender) or SendGrid rejects the send. Not sensitive."
}

variable "use_real_auth" {
  type        = bool
  default     = false
  description = "When false (dev default), the runtime keeps the seeded-admin stub and no sign-in/cookie is required. When true, the runtime requires real Google / magic-link auth — which also needs AUTH_SECRET (auto-generated, see secrets.tf), the runtime reachable from the browser (ingress + CORS-with-credentials), and the Google redirect URI registered. Flip on a follow-up apply once those are in place."
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

variable "enable_runtime_custom_domain" {
  type        = bool
  default     = false
  description = "Attach api.tyndaleapp.net to the runtime Container App. Same phased flow as the marketing domain: first apply lays the api CNAME + asuid.api TXT records (the runtime is reachable on its raw external FQDN meanwhile); flip true on a follow-up apply once api.tyndaleapp.net resolves publicly, then Azure can validate the hostname."
}

variable "enable_runtime_managed_cert" {
  type        = bool
  default     = false
  description = "Provision + bind the free managed TLS cert for api.tyndaleapp.net via `az containerapp hostname bind`. Requires enable_runtime_custom_domain = true and the HTTP binding live. Requires az CLI on the apply host. The cookie-based auth needs this HTTPS host, so flip true once the HTTP binding works."
}

variable "common_tags" {
  type = map(string)
  default = {
    project    = "tyndale"
    managed_by = "terraform"
  }
}
