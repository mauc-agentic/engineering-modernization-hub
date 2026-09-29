# ADR-006: una VPC con subredes PÚBLICAS únicamente -- sin NAT Gateway.
# La API y el sandbox reciben IP pública directa; RDS pide dos subredes en
# AZ distintas solo porque su grupo de subredes lo exige, aunque la
# instancia sea Single-AZ (ADR-007) y `publicly_accessible = false`.

data "aws_availability_zones" "disponibles" {
  state = "available"
}

resource "aws_vpc" "principal" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.nombre_proyecto}-vpc" }
}

resource "aws_internet_gateway" "principal" {
  vpc_id = aws_vpc.principal.id
  tags   = { Name = "${var.nombre_proyecto}-igw" }
}

resource "aws_subnet" "publica" {
  count                   = 2
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = "10.42.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.disponibles.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.nombre_proyecto}-publica-${count.index}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.principal.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.principal.id
  }
  tags = { Name = "${var.nombre_proyecto}-rt-publica" }
}

resource "aws_route_table_association" "publica" {
  count          = 2
  subnet_id      = aws_subnet.publica[count.index].id
  route_table_id = aws_route_table.publica.id
}

# -- Grupos de seguridad -----------------------------------------------------

resource "aws_security_group" "api" {
  name_prefix = "${var.nombre_proyecto}-api-"
  description = "API FastAPI: entrada 8000 (demo), salida libre (Bedrock, ECS RunTask)"
  vpc_id      = aws_vpc.principal.id

  ingress {
    description = "API HTTP solo desde los CIDR autorizados (sin autenticacion en F1, RN-14)"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = var.cidr_acceso_api
  }

  ingress {
    description     = "API HTTP desde el ALB (CloudFront -> ALB -> Fargate)"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.nombre_proyecto}-api-sg" }
}

resource "aws_security_group" "sandbox" {
  name_prefix = "${var.nombre_proyecto}-sandbox-"
  description = "Tarea efimera de verificacion: SIN entrada; salida solo HTTPS (ECR + S3 prefirmado)"
  vpc_id      = aws_vpc.principal.id

  # Sin bloque ingress -> ninguna regla de entrada (control 2/NFR-005:
  # coherente con que el sandbox NUNCA acepta conexiones).
  #
  # Salida: solo TCP 443. La tarea la necesita para bajar su imagen de ECR y
  # leer/escribir sus dos URLs prefirmadas de S3; el wheelhouse ya viaja
  # dentro del trabajo, asi que pip nunca sale a internet (--no-index).
  # DESVIACION CONSCIENTE frente al sandbox local (network=none): en una VPC
  # sin NAT ni endpoints privados no se puede negar todo internet y a la vez
  # bajar la imagen; se mitiga con rol IAM vacio, sin secretos en el entorno
  # (el ejecutor retira EMH_*), tarea efimera y solo 443. Ver ADR-006.
  egress {
    description = "HTTPS (ECR, S3)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.nombre_proyecto}-sandbox-sg" }
}

resource "aws_security_group" "rds" {
  name_prefix = "${var.nombre_proyecto}-rds-"
  description = "Postgres: solo alcanzable desde la tarea de la API"
  vpc_id      = aws_vpc.principal.id

  ingress {
    description     = "Postgres desde la API"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.nombre_proyecto}-rds-sg" }
}
