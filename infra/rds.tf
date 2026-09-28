# ADR-007: instancia simple, Single-AZ, sin protección de borrado -- para
# que `terraform destroy` limpie todo sin pasos manuales. Contraseña en SSM
# Parameter Store (SecureString, gratis) en vez de Secrets Manager
# (USD 0.40/mes que no se justifican para un recurso de un par de días).

resource "aws_db_subnet_group" "principal" {
  name       = "${var.nombre_proyecto}-db-subnets"
  subnet_ids = aws_subnet.publica[*].id # RDS exige >=2 AZ en el grupo, aunque la instancia sea Single-AZ
}

resource "random_password" "db" {
  length  = 24
  special = false # evita problemas de escape en la cadena de conexión
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/${var.nombre_proyecto}/db/password"
  type  = "SecureString"
  value = random_password.db.result
}

resource "aws_db_instance" "principal" {
  identifier     = "${var.nombre_proyecto}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro" # ADR-007: USD 0.016/h confirmado (AWS Pricing API, us-east-1)

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = var.db_nombre
  username = var.db_usuario
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.principal.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false # alcanzable solo dentro de la VPC, aunque la subred sea "pública"

  multi_az                = false # ADR-007: Single-AZ, un prototipo de un día no justifica el doble de costo
  backup_retention_period = 1     # mínimo, no 7: menos almacenamiento de snapshots que sobreviva al destroy
  deletion_protection     = false # para que `terraform destroy` funcione sin pasos manuales
  skip_final_snapshot     = true

  tags = { Name = "${var.nombre_proyecto}-db" }
}
