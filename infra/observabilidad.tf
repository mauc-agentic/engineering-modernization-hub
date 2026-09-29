# Observabilidad del agente (AgentCore Observability para agentes alojados FUERA de
# AgentCore Runtime): el ADOT SDK dentro de la imagen de la API exporta trazas y
# métricas con OpenTelemetry a CloudWatch, y aparecen en la vista GenAI Observability.
# Ver ADR-008. Prerrequisito de cuenta, una sola vez (no gestionable con Terraform):
#   aws xray update-trace-segment-destination --destination CloudWatchLogs
# El ADOT Collector NO está soportado para esto: solo el SDK (aws-opentelemetry-distro).
#
# Privacidad: NO se activa AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT (dejaría prompts y
# respuestas del modelo en los spans). Los spans llevan nombres, tiempos y tokens.

locals {
  grupo_observabilidad = "/aws/bedrock-agentcore/runtimes/${var.nombre_proyecto}-agente"
}

resource "aws_cloudwatch_log_group" "agente" {
  name              = local.grupo_observabilidad
  retention_in_days = 14 # higiene de costo
}

# X-Ray debe poder escribir los spans en este grupo y en los compartidos de Transaction Search.
data "aws_iam_policy_document" "xray_spans" {
  statement {
    sid     = "TransactionSearchXRayAccess"
    effect  = "Allow"
    actions = ["logs:PutLogEvents"]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.actual.account_id}:log-group:aws/spans:*",
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.actual.account_id}:log-group:/aws/application-signals/data:*",
      "${aws_cloudwatch_log_group.agente.arn}:*",
    ]
    principals {
      type        = "Service"
      identifiers = ["xray.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:xray:${var.region}:${data.aws_caller_identity.actual.account_id}:*"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.actual.account_id]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "xray_spans" {
  policy_name     = "${var.nombre_proyecto}-xray-spans"
  policy_document = data.aws_iam_policy_document.xray_spans.json
}

# Permisos del rol de la API para exportar telemetría (el sandbox NO recibe ninguno, NFR-004).
data "aws_iam_policy_document" "telemetria_api" {
  statement {
    sid    = "EscribirTelemetriaEnElGrupoDelAgente"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams", "logs:DescribeLogGroups",
    ]
    resources = [aws_cloudwatch_log_group.agente.arn, "${aws_cloudwatch_log_group.agente.arn}:*"]
  }

  statement {
    sid       = "EnviarTrazasAXRayOTLP"
    effect    = "Allow"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"] # X-Ray no admite permisos por recurso para estas acciones
  }

  statement {
    sid       = "MetricasDelAgente"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
}

resource "aws_iam_role_policy" "telemetria_api" {
  name   = "telemetria-agente"
  role   = aws_iam_role.tarea_api.id
  policy = data.aws_iam_policy_document.telemetria_api.json
}
