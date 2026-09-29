output "ecr_repositorio_api" {
  value = aws_ecr_repository.api.repository_url
}

output "ecr_repositorio_sandbox" {
  value = aws_ecr_repository.sandbox.repository_url
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.principal.arn
}

output "url_web" {
  description = "URL pública HTTPS del dashboard y de la API (autenticación básica)."
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "usuario_web" {
  value = var.usuario_web
}

output "contrasena_web" {
  value     = random_password.web.result
  sensitive = true
}

output "ecs_cluster_nombre" {
  value = aws_ecs_cluster.principal.name
}

output "servicio_api" {
  value = aws_ecs_service.api.name
}

output "bucket_trabajos" {
  value = aws_s3_bucket.trabajos.bucket
}

output "obtener_url_de_la_api" {
  description = "La API no tiene balanceador (ADR-006): su IP pública es la de la tarea. Este comando la imprime."
  value       = "aws ecs list-tasks --cluster ${aws_ecs_cluster.principal.name} --service-name ${aws_ecs_service.api.name} --query 'taskArns[0]' --output text | xargs -I{} aws ecs describe-tasks --cluster ${aws_ecs_cluster.principal.name} --tasks {} --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text | xargs -I{} aws ec2 describe-network-interfaces --network-interface-ids {} --query 'NetworkInterfaces[0].Association.PublicIp' --output text"
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
