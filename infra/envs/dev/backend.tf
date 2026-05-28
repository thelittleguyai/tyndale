terraform {
  backend "azurerm" {
    # Values populated by Phil after running infra/state-backend-bootstrap.sh.
    # The storage_account_name below is a placeholder — replace the trailing
    # underscores with the actual account name printed by the bootstrap script
    # (it includes a 6-char suffix derived from the subscription ID).
    # Alternatively, supply at init time:
    #   terraform init -backend-config="storage_account_name=tyndaletfstateXXXXXX"
    resource_group_name  = "tyndale-tfstate-rg"
    storage_account_name = "tyndaletfstate______" # placeholder; Phil fills after bootstrap
    container_name       = "tfstate"
    key                  = "dev.tfstate"
  }
}
