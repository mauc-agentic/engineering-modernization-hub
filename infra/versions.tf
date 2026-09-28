# ADR-006/ADR-007: provider oficial de AWS, versión confirmada el 2026-09-28.

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Proyecto      = "engineering-modernization-hub"
      Caso          = "wenia-staff-ai-platform-engineer"
      GestionadoPor = "terraform"
    }
  }
}
