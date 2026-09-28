# Repositorios de imágenes -- volumen mínimo, costo de centavos (ADR-006).

resource "aws_ecr_repository" "api" {
  name                 = "${var.nombre_proyecto}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # para que `terraform destroy` no deje huérfanos

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "sandbox" {
  name                 = "${var.nombre_proyecto}-sandbox"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "expirar_no_taggeadas" {
  for_each   = { api = aws_ecr_repository.api.name, sandbox = aws_ecr_repository.sandbox.name }
  repository = each.value
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Purgar imágenes sin tag tras 3 días (higiene de costo)"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 3
      }
      action = { type = "expire" }
    }]
  })
}
