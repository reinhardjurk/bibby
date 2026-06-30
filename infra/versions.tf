terraform {
  required_version = ">= 1.6"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.40"
    }
  }

  # Empfohlen: State in einen Object-Storage-Bucket (S3-Backend) auslagern.
  # backend "s3" {
  #   bucket                      = "bibby-tfstate"
  #   key                         = "terraform.tfstate"
  #   region                      = "fr-par"
  #   endpoints                   = { s3 = "https://s3.fr-par.scw.cloud" }
  #   skip_credentials_validation = true
  #   skip_region_validation      = true
  #   skip_requesting_account_id  = true
  # }
}
