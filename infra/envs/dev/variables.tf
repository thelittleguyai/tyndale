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

variable "use_real_claude" {
  type        = bool
  default     = false
  description = "When true, the runtime calls the real Claude API (direct Anthropic) instead of the deterministic fixtures. Real calls cost money per request — set to true in terraform.tfvars to enable live chat/audit, leave false for fixture-only dev."
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

variable "enable_marketing_apex_custom_domain" {
  type        = bool
  default     = false
  description = "Attach the APEX (root) tyndaleapp.net custom domain to the marketing Container App (HTTP only), pointing at the same app as dev. Same phased flow as enable_marketing_custom_domain: first apply lays the apex A record (→ external CAE static IP) + asuid TXT; once they propagate publicly, set true and re-apply so Azure can validate the root hostname."
}

variable "enable_marketing_apex_managed_cert" {
  type        = bool
  default     = false
  description = "Provision + bind the free managed TLS cert for the apex tyndaleapp.net via `az containerapp hostname bind`. Requires enable_marketing_apex_custom_domain true and the apex HTTP binding live (tyndaleapp.net returns a 301 from the CA). Requires az CLI on the apply host. Flip true on a follow-up apply once apex HTTP works."
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

variable "enable_app_custom_domain" {
  type        = bool
  default     = false
  description = "Attach app.tyndaleapp.net to the product app Container App (Expo static web export). Same phased flow as the other domains: first apply lays the app CNAME + asuid.app TXT records; flip true on a follow-up apply once app.tyndaleapp.net resolves publicly."
}

variable "enable_app_managed_cert" {
  type        = bool
  default     = false
  description = "Provision + bind the free managed TLS cert for app.tyndaleapp.net via `az containerapp hostname bind`. Requires enable_app_custom_domain = true and the HTTP binding live. Requires az CLI on the apply host."
}

# --- Phase CO-6A admin console (admin.tyndaleapp.net) -----------------------
variable "admin_allowed_ip_ranges" {
  type = list(string)
  # PLACEHOLDER (RFC 5737 TEST-NET-3) — matches NO real traffic. Because the
  # admin ingress uses Allow-only restrictions, Azure denies every IP not in
  # this list, so the default LOCKS EVERYONE OUT (including Brock). DL-60.
  default     = ["203.0.113.0/24"]
  description = "FLAG FOR BROCK: CIDR ranges allowed to reach admin.tyndaleapp.net (his home/office + VPN/travel fallback). The default is a TEST-NET placeholder that blocks ALL traffic — set real CIDRs in terraform.tfvars BEFORE `terraform apply` or Brock is locked out of his own admin console."
}

variable "enable_admin_custom_domain" {
  type        = bool
  default     = false
  description = "Attach admin.tyndaleapp.net to the admin Container App. Same phased flow as the other domains: first apply lays the admin CNAME + asuid.admin TXT records; flip true on a follow-up apply once admin.tyndaleapp.net resolves publicly."
}

variable "enable_admin_managed_cert" {
  type        = bool
  default     = false
  description = "Provision + bind the free managed TLS cert for admin.tyndaleapp.net via `az containerapp hostname bind`. Requires enable_admin_custom_domain = true and the HTTP binding live. Requires az CLI on the apply host."
}

variable "common_tags" {
  type = map(string)
  default = {
    project    = "tyndale"
    managed_by = "terraform"
  }
}

# --- CO-18: Claude via Azure AI Foundry (DL-79) -----------------------------
variable "enable_foundry" {
  type        = bool
  default     = false
  description = "Create the Azure AI Foundry account + Claude deployments + runtime RBAC. Gated so the plan is a no-op until you opt in. Apply this true first, then flip use_foundry."
}

variable "use_foundry" {
  type        = bool
  default     = false
  description = "Runtime USE_FOUNDRY flag — route Claude through Foundry (managed identity) instead of Anthropic-direct. Flip true only after the enable_foundry resources have provisioned."
}

variable "foundry_location" {
  type        = string
  default     = "eastus2"
  description = "Region for the Foundry account. Must be Claude-supported (eastus2 hosts Haiku/Sonnet/Opus; the dev env's centralus is NOT Claude-supported)."
}

variable "foundry_account_name" {
  type        = string
  default     = ""
  description = "Override the Foundry account / custom-subdomain name (must be globally unique). Empty -> <name_prefix>-foundry."
}

variable "foundry_token_scope" {
  type        = string
  default     = "https://ai.azure.com/.default"
  description = "Entra token scope for Foundry inference. Verified value is https://ai.azure.com/.default (NOT cognitiveservices.azure.com — corrects the scope stated in DL-79)."
}

variable "foundry_deployment_sku" {
  type        = string
  default     = "GlobalStandard"
  description = "Deployment SKU. GlobalStandard works for all Claude models; DataZoneStandard (US residency) is only available for Azure-hosted models (Haiku/Opus), NOT claude-sonnet-4-6 (Hosted on Anthropic)."
}

variable "claude_sonnet_model" {
  type        = string
  default     = "claude-sonnet-4-6"
  description = "Sonnet model id (the LP/BD/MP trio); also the deployment name."
}

variable "claude_haiku_model" {
  type        = string
  default     = "claude-haiku-4-5"
  description = "Haiku model id (crisis/greeting); also the deployment name."
}

variable "foundry_sonnet_version" {
  type        = string
  default     = "1"
  description = "Model version for the Sonnet deployment (version selects the hosting option: 1 = Hosted on Anthropic, 2 = Hosted on Azure). Confirm against the live catalog at apply."
}

variable "foundry_haiku_version" {
  type        = string
  default     = "1"
  description = "Model version for the Haiku deployment (1 = Hosted on Anthropic, 2 = Hosted on Azure)."
}

variable "foundry_sonnet_capacity" {
  type        = number
  default     = 25
  description = "Sonnet deployment capacity in thousands of tokens/min."
}

variable "foundry_haiku_capacity" {
  type        = number
  default     = 25
  description = "Haiku deployment capacity in thousands of tokens/min."
}

variable "claude_organization_name" {
  type        = string
  default     = ""
  description = "Anthropic Marketplace attestation: the legal entity using Claude (e.g. 'The Little Guy LLC'). REQUIRED when enable_foundry is true — set in terraform.tfvars."
}

variable "claude_country_code" {
  type        = string
  default     = "US"
  description = "Anthropic Marketplace attestation: two-letter country code."
}

variable "claude_industry" {
  type        = string
  default     = "technology"
  description = "Anthropic Marketplace attestation: industry (lowercase; one of technology/finance/healthcare/education/retail/manufacturing/government/media/other)."
}
