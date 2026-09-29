# Origen de la API para CloudFront (ADR-006, "URL pública"). CloudFront necesita un
# origen con nombre DNS estable y la IP pública de la tarea Fargate cambia en
# cada reinicio, así que se antepone un ALB. Es un costo por hora (~USD 0.03/h)
# que solo existe mientras dure la demo (`terraform destroy`).
#
# El ALB acepta tráfico de internet en el 80, pero SOLO reenvía a la API las
# peticiones que traen la cabecera secreta que CloudFront añade al origen; el
# resto recibe 403. (Se evita la lista de prefijos administrada de CloudFront en
# el grupo de seguridad porque consume casi toda la cuota de reglas por SG.)

resource "random_password" "origen_secreto" {
  length  = 40
  special = false
}

resource "aws_security_group" "alb" {
  name_prefix = "${var.nombre_proyecto}-alb-"
  description = "ALB de la API: HTTP 80; solo reenvia con la cabecera secreta de CloudFront"
  vpc_id      = aws_vpc.principal.id

  ingress {
    description = "HTTP desde internet (filtrado por cabecera secreta, ver alb.tf)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.nombre_proyecto}-alb-sg" }
}

resource "aws_lb" "api" {
  name               = "${var.nombre_proyecto}-api"
  load_balancer_type = "application"
  subnets            = aws_subnet.publica[*].id
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = 60
}

resource "aws_lb_target_group" "api" {
  name        = "${var.nombre_proyecto}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip" # Fargate awsvpc
  vpc_id      = aws_vpc.principal.id

  health_check {
    path                = "/openapi.json"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
  }

  deregistration_delay = 10
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }
}

resource "aws_lb_listener_rule" "solo_cloudfront" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 1

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [random_password.origen_secreto.result]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
