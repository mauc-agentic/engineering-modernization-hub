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
  description = "vCPU de la tarea Fargate de la API (0.5 vCPU: uvicorn + git + pip download del wheelhouse)."
  type        = string
  default     = "512" # unidades Fargate: 512 = 0.5 vCPU
}

variable "api_memoria" {
  type    = string
  default = "1024" # MB
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

variable "cidr_acceso_api" {
  description = "CIDR(s) autorizados a llamar a la API (puerto 8000). La API no tiene autenticación en F1 (RN-14): nunca 0.0.0.0/0. Ej.: [\"203.0.113.7/32\"]."
  type        = list(string)

  validation {
    condition     = !contains(var.cidr_acceso_api, "0.0.0.0/0")
    error_message = "La API no tiene autenticación: no se permite 0.0.0.0/0 (RN-14)."
  }
}

variable "sandbox_imagen_tag" {
  type    = string
  default = "latest"
}
