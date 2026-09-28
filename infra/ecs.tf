# ADR-006: un clúster, dos definiciones de tarea. `emh-api` es un servicio
# persistente (mínima réplica); `emh-sandbox` NO tiene `aws_ecs_service` --
# la API la lanza bajo demanda con `ecs:RunTask` (una tarea efímera por
# ejecución, el equivalente en la nube de ADR-005). Sin balanceador de
# carga: la tarea de la API recibe IP pública directa.

resource "aws_ecs_cluster" "principal" {
  name = "${var.nombre_proyecto}-cluster"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.nombre_proyecto}-api"
  retention_in_days = 14 # higiene de costo: sin retención indefinida
}

resource "aws_cloudwatch_log_group" "sandbox" {
  name              = "/ecs/${var.nombre_proyecto}-sandbox"
  retention_in_days = 7
}

# -- Tarea persistente: API ----------------------------------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.nombre_proyecto}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_vcpu
  memory                   = var.api_memoria
  execution_role_arn       = aws_iam_role.ejecucion.arn
  task_role_arn            = aws_iam_role.tarea_api.arn

  container_definitions = jsonencode([{
    name         = "api"
    image        = "${aws_ecr_repository.api.repository_url}:${var.api_imagen_tag}"
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "EMH_ENV", value = "aws" },
      { name = "EMH_BEDROCK_MODEL_ID", value = var.bedrock_model_id },
      { name = "EMH_DB_HOST", value = aws_db_instance.principal.address },
      { name = "EMH_DB_NAME", value = var.db_nombre },
      { name = "EMH_DB_USER", value = var.db_usuario },
      { name = "EMH_ECS_CLUSTER", value = aws_ecs_cluster.principal.arn },
      { name = "EMH_SANDBOX_TASK_DEFINITION", value = aws_ecs_task_definition.sandbox.family },
      { name = "EMH_SUBNET_IDS", value = join(",", aws_subnet.publica[*].id) },
      { name = "EMH_SANDBOX_SECURITY_GROUP", value = aws_security_group.sandbox.id },
    ]
    secrets = [
      { name = "EMH_DB_PASSWORD", valueFrom = aws_ssm_parameter.db_password.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "${var.nombre_proyecto}-api"
  cluster         = aws_ecs_cluster.principal.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.publica[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = true # sin ALB (ADR-006): IP pública directa de la tarea
  }
}

# -- Definición de tarea efímera: sandbox (sin aws_ecs_service) -----------------

resource "aws_ecs_task_definition" "sandbox" {
  family                   = "${var.nombre_proyecto}-sandbox"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.sandbox_vcpu
  memory                   = var.sandbox_memoria
  execution_role_arn       = aws_iam_role.ejecucion.arn
  task_role_arn            = aws_iam_role.tarea_sandbox.arn # vacío (NFR-004)

  container_definitions = jsonencode([{
    name    = "sandbox"
    image   = "${aws_ecr_repository.sandbox.repository_url}:${var.sandbox_imagen_tag}"
    command = ["sleep", "infinity"] # la API hace exec/RunTask con el comando real por invocación
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.sandbox.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "sandbox"
      }
    }
  }])
}
