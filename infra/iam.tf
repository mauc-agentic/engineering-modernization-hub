# Roles de mínimo privilegio (ADR-006). Dos tipos por tarea ECS:
# - "ejecución" (execution role): lo usa el AGENTE de ECS para arrancar la
#   tarea (pull de ECR, escribir logs) -- nunca lo ve el código de la app.
# - "tarea" (task role): permisos que la APLICACIÓN usa en tiempo de
#   ejecución. El de `sandbox` se deja VACÍO a propósito (refuerza NFR-004:
#   ni siquiera permisos de AWS, no solo sin variables de entorno).

data "aws_caller_identity" "actual" {}

# -- Rol de ejecución (compartido por ambas tareas) --------------------------

data "aws_iam_policy_document" "asume_ecs_tasks" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ejecucion" {
  name               = "${var.nombre_proyecto}-ecs-ejecucion"
  assume_role_policy = data.aws_iam_policy_document.asume_ecs_tasks.json
}

resource "aws_iam_role_policy_attachment" "ejecucion_ecs" {
  role       = aws_iam_role.ejecucion.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ejecucion_ssm_lectura" {
  name = "leer-parametro-db"
  role = aws_iam_role.ejecucion.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameters", "ssm:GetParameter"]
      Resource = [aws_ssm_parameter.db_password.arn]
    }]
  })
}

# -- Rol de tarea: API (Bedrock + RunTask del sandbox) ------------------------

data "aws_iam_policy_document" "tarea_api" {
  statement {
    sid     = "InvocarNova2Lite"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel", "bedrock:Converse"]
    resources = [
      "arn:aws:bedrock:${var.region}::foundation-model/amazon.nova-2-lite-v1:0",
      "arn:aws:bedrock:*:${data.aws_caller_identity.actual.account_id}:inference-profile/${var.bedrock_model_id}",
    ]
  }

  statement {
    sid     = "LanzarTareaSandbox"
    effect  = "Allow"
    actions = ["ecs:RunTask", "ecs:DescribeTasks", "ecs:StopTask"]
    resources = [
      "${replace(aws_ecs_task_definition.sandbox.arn, "/:\\d+$/", "")}:*",
    ]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.principal.arn]
    }
  }

  statement {
    sid       = "PasarRolesDeLaTareaSandbox"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ejecucion.arn, aws_iam_role.tarea_sandbox.arn]
  }
}

resource "aws_iam_role" "tarea_api" {
  name               = "${var.nombre_proyecto}-tarea-api"
  assume_role_policy = data.aws_iam_policy_document.asume_ecs_tasks.json
}

resource "aws_iam_role_policy" "tarea_api" {
  name   = "permisos-api"
  role   = aws_iam_role.tarea_api.id
  policy = data.aws_iam_policy_document.tarea_api.json
}

# -- Rol de tarea: sandbox -- VACÍO a propósito (NFR-004) --------------------

resource "aws_iam_role" "tarea_sandbox" {
  name               = "${var.nombre_proyecto}-tarea-sandbox"
  assume_role_policy = data.aws_iam_policy_document.asume_ecs_tasks.json
  # Sin aws_iam_role_policy adjunta: 0 permisos de AWS para el código del
  # repositorio objetivo que corre dentro de esta tarea.
}
