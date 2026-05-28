# Staging environment

Phase 2D+ work. Copy infra/envs/dev/ as the starting point and adjust:
  - Postgres: bump to B2s or D2ds for more realistic load
  - Container Apps: min_replicas = 1, max_replicas = 3
  - Static Web App: Standard tier (better SLA)
  - Backup retention: 14 days, geo-redundant
  - state backend key: staging.tfstate
