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

variable "use_real_ocr" {
  type        = bool
  default     = false
  description = "Runtime USE_REAL_OCR flag — when true, deployed OCR flips from the deterministic stub to real Azure Document Intelligence (the doc-intel endpoint/key are always wired into the runtime; this just activates them). Set true in terraform.tfvars to enable real OCR without a code change; leave false for stub-only dev."
}

variable "enable_chat_first_audit" {
  type        = bool
  default     = false
  description = "Chat-first audit flow (DL-91 Phase A) — when true, upload lands in the case thread and the thread orchestrates the journey; classic screens when false. Server-driven: the app follows the chat_first signal in the upload response, no app rebuild needed."
}

variable "enable_record_view" {
  type        = bool
  default     = false
  description = "Tyndale Record + sub-case views (D5 Phase C) — when true, the dashboard becomes the Record and sub-case summary views are reachable. Server-driven via record_enabled in the dashboard response."
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
  default     = "https://cognitiveservices.azure.com/.default"
  description = "Entra token scope (audience) for keyless Foundry inference; runtime-configurable via FOUNDRY_TOKEN_SCOPE. Canonical Azure AI Services audience. HISTORY: https://ai.cognitiveservices.com/.default (what MS's Foundry how-to shows) was REJECTED with `invalid_scope` 400 by the Container Apps managed-identity token endpoint on 2026-07-04 — do not use it. If this value ever fails auth, the remaining alternate is https://ai.azure.com/.default (flip via terraform.tfvars, no code change). Only matters when the runtime CALLS Foundry, not at deployment."
}

variable "foundry_deployment_sku" {
  type        = string
  default     = "GlobalStandard"
  description = "Deployment SKU (shared by both deployments). GlobalStandard works for every Claude model. DataZoneStandard (US residency) is available ONLY for the Azure-hosted models — claude-haiku-4-5 (v2), claude-sonnet-5, claude-opus-4-8 — NOT claude-sonnet-4-6 (Hosted on Anthropic, GlobalStandard only). To put Haiku on DataZone while Sonnet-4-6 stays Global, split this into per-deployment SKU vars."
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
  description = "Model version for the Sonnet deployment. claude-sonnet-4-6 is Hosted on Anthropic ONLY, so v1 is the sole option (it deployed cleanly). Version selects hosting (1 = Hosted on Anthropic, 2 = Hosted on Azure); for an Azure-hosted / Data-Zone-eligible Sonnet you must switch the MODEL to claude-sonnet-5 (which has a v2) — see the residency note in ai_foundry.tf."
}

variable "foundry_haiku_version" {
  type        = string
  default     = "2"
  description = "Model version for the Haiku deployment. 2 = Hosted on Azure (GA default; runs end-to-end on Azure — the residency/BAA-preferred line and Data-Zone-eligible). 1 = Hosted on Anthropic. Deploying claude-haiku-4-5 as v1 returned DeploymentModelNotSupported, so v2 is the default. (The deployment NAME stays claude-haiku-4-5 either way, so no runtime change.)"
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

# --- Phase 3.3: Qdrant launch posture (persistence + auth) ------------------
variable "qdrant_image" {
  type        = string
  default     = "qdrant/qdrant:v1.12.4"
  description = "Pinned Qdrant image — NEVER :latest. A silent upstream bump could break the on-disk storage format under the persistent volume. Bump deliberately and test a restore. Confirm the tag exists before apply."
}

variable "qdrant_storage_quota_gb" {
  type        = number
  default     = 20
  description = "Azure Files share size (GB) backing Qdrant's /qdrant/storage volume. The 50-state + billing-code corpora are small; 20 GB is generous headroom."
}

# --- Coverage connection: 1upHealth wrapper service -------------------------
# The wrapper is an internal-only Container App (like qdrant/litellm) that fronts
# the 1upHealth FHIR integration. The runtime reaches it over the VNet and
# registers matching source adapters behind the DL-68 interfaces. Everything is
# gated OFF by default (enable_coverage_connection=false): the service deploys,
# serves /health, and returns 503 on data routes until the gate is flipped.
variable "enable_coverage_connection" {
  type        = bool
  default     = false
  description = "Master gate for the 1up wrapper (DL-70). When false (default), the runtime's ENABLE_COVERAGE_CONNECTION is false so it never calls the wrapper, and the wrapper itself 503s on data routes. Flip true ONLY after a durable TokenStore replaces the in-memory one AND the BAA is signed. Ships closed as a fast-follow behind uploads-first launch."
}

variable "oneup_environment" {
  type        = string
  default     = "sandbox"
  description = "Which 1upHealth environment the wrapper targets: sandbox|production. Surfaced to the service as ONEUP_ENVIRONMENT."
}

variable "oneup_client_id" {
  type        = string
  sensitive   = true
  default     = ""
  description = "1upHealth app client ID for the wrapper. OPTIONAL: empty (default) skips the KV secret + the service's ONEUP_CLIENT_ID env (same optional pattern as sendgrid_api_key), so apply succeeds before 1up creds exist — the service boots and 503s on data routes. Set the real value in terraform.tfvars to configure it."
}

variable "oneup_client_secret" {
  type        = string
  sensitive   = true
  default     = ""
  description = "1upHealth app client secret for the wrapper. OPTIONAL: empty (default) skips the KV secret + env wiring (Key Vault rejects empty values), so apply succeeds without 1up creds. Set in terraform.tfvars alongside oneup_client_id."
}

variable "oneup_redirect_uri" {
  type        = string
  default     = ""
  description = "Registered 1upHealth payer-OAuth redirect URI (Setup Call 4). OPTIONAL like the client id/secret; empty skips the env wiring. Must match a URI registered with 1up when set."
}
