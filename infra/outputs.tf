output "ecr_repositorio_api" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_repositorio_sandbox" {
  value = aws_ecr_repository.sandbox.repository_url
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.principal.arn
}

output "rds_endpoint" {
  value     = aws_db_instance.principal.address
  sensitive = false
}

output "vpc_id" {
  value = aws_vpc.principal.id
}

output "subredes_publicas" {
  value = aws_subnet.publica[*].id
}

output "nota_costo" {
  value = "Recuerda 'terraform destroy' al terminar la sustentación -- RDS es el único recurso con costo por hora corriendo continuamente (ADR-006/ADR-007)."
}
