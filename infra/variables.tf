variable "region" {
  description = "Región de AWS. us-east-1 tiene acceso confirmado a Nova 2 Lite (ADR-002)."
  type        = string
  default     = "us-east-1"
}

variable "nombre_proyecto" {
  type    = string
  default = "emh"
}

variable "bedrock_model_id" {
  description = "Inference profile de Nova 2 Lite (ADR-002)."
  type        = string
  default     = "us.amazon.nova-2-lite-v1:0"
}

variable "email_alertas_presupuesto" {
  description = "Correo que recibe las alertas de AWS Budgets (ADR-006)."
  type        = string
}

variable "limite_presupuesto_usd" {
  description = "Techo del AWS Budget mensual (ADR-006: se estima ~USD 6 de gasto real; USD 100 es el crédito disponible)."
  type        = number
  default     = 100
}

variable "db_nombre" {
  type    = string
  default = "emh"
}

variable "db_usuario" {
  type    = string
  default = "emh_app"
}

variable "api_vcpu" {
  description = "vCPU de la tarea Fargate de la API (ADR-006: 0.25 vCPU)."
  type        = string
  default     = "256" # unidades Fargate: 256 = 0.25 vCPU
}

variable "api_memoria" {
  type    = string
  default = "512" # MB
}

variable "sandbox_vcpu" {
  description = "vCPU de la tarea efímera de sandbox (más holgada: pip install + pytest)."
  type        = string
  default     = "512" # 0.5 vCPU
}

variable "sandbox_memoria" {
  type    = string
  default = "1024" # MB
}

variable "api_imagen_tag" {
  description = "Tag de la imagen de la API en ECR (se publica fuera de Terraform, vía CI/CD o build manual)."
  type        = string
  default     = "latest"
}

variable "sandbox_imagen_tag" {
  type    = string
  default = "latest"
}
