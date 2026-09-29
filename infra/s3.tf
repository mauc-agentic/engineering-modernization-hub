# Intercambio de trabajos entre la API y la tarea efímera del sandbox
# (ADR-006). La API sube un tar con workspace + wheelhouse + comandos y firma
# dos URLs de UN objeto (entrada GET, salida PUT) que caducan en minutos: el
# sandbox no tiene rol IAM (NFR-004), así que este bucket es su único canal.
# Privado, cifrado y con expiración a 1 día: no acumula código de clientes.

resource "aws_s3_bucket" "trabajos" {
  bucket        = "${var.nombre_proyecto}-trabajos-${data.aws_caller_identity.actual.account_id}"
  force_destroy = true # `terraform destroy` no debe fallar por objetos residuales
}

resource "aws_s3_bucket_public_access_block" "trabajos" {
  bucket                  = aws_s3_bucket.trabajos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "trabajos" {
  bucket = aws_s3_bucket.trabajos.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "trabajos" {
  bucket = aws_s3_bucket.trabajos.id
  rule {
    id     = "expirar-trabajos"
    status = "Enabled"
    filter {
      prefix = "jobs/"
    }
    expiration {
      days = 1
    }
  }
}
