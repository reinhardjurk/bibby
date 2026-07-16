# Terraform-/OpenTofu-State liegt remote in einem Scaleway-Object-Storage-Bucket
# (S3-kompatibel), damit CI und Team denselben State teilen. KEIN natives Locking
# (Scaleway hat kein DynamoDB-Äquivalent) -> nicht zwei Applies gleichzeitig.
#
# Zugang über AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY = Scaleway Access-/Secret-Key.
# Einmalige Migration des bestehenden lokalen States:
#   1) privaten Bucket "bibby-tfstate" in fr-par anlegen
#   2) cd infra
#      AWS_ACCESS_KEY_ID=$SCW_ACCESS_KEY AWS_SECRET_ACCESS_KEY=$SCW_SECRET_KEY \
#      tofu init -migrate-state
terraform {
  backend "s3" {
    bucket = "bibby-tfstate"
    key    = "bibby/terraform.tfstate"
    region = "fr-par"

    endpoints = {
      s3 = "https://s3.fr-par.scw.cloud"
    }

    # Scaleway ist nicht AWS -> die AWS-spezifischen Checks überspringen.
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
    use_path_style              = false
  }
}
