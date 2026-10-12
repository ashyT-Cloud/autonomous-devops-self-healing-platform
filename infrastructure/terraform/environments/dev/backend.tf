terraform {
  backend "s3" {
    bucket       = "ashy-project8-tfstate-487054650859"
    key          = "project-8/dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

