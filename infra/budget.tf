# ADR-006 "Guardarraíl de presupuesto": alertas a USD 20/50/80 de los
# USD 100 disponibles. Solo alertas -- sin acción automática de apagado,
# para no arriesgar la demo en vivo si se dispara durante la sustentación.

resource "aws_sns_topic" "alertas_presupuesto" {
  name = "${var.nombre_proyecto}-alertas-presupuesto"
}

resource "aws_sns_topic_subscription" "correo" {
  topic_arn = aws_sns_topic.alertas_presupuesto.arn
  protocol  = "email"
  endpoint  = var.email_alertas_presupuesto
}

resource "aws_budgets_budget" "mensual" {
  name         = "${var.nombre_proyecto}-mensual"
  budget_type  = "COST"
  limit_amount = tostring(var.limite_presupuesto_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [20, 50, 80]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_sns_topic_arns  = [aws_sns_topic.alertas_presupuesto.arn]
      subscriber_email_addresses = [var.email_alertas_presupuesto]
    }
  }
}
