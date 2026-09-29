# URL pública HTTPS del dashboard y de la API (ADR-006): CloudFront con dos
# orígenes -- el bucket S3 privado del sitio (OAC) y el ALB de la API -- bajo UN
# mismo dominio *.cloudfront.net, así el navegador no bloquea el contenido mixto
# ni hace falta CORS. La API no tiene autenticación propia en F1 (RN-14): una
# función de CloudFront exige autenticación HTTP básica en TODAS las rutas.

resource "random_password" "web" {
  length  = 20
  special = false
}

resource "aws_s3_bucket" "sitio" {
  bucket        = "${var.nombre_proyecto}-sitio-${data.aws_caller_identity.actual.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "sitio" {
  bucket                  = aws_s3_bucket.sitio.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "index" {
  bucket        = aws_s3_bucket.sitio.id
  key           = "index.html"
  source        = "${path.module}/../frontend/index.html"
  etag          = filemd5("${path.module}/../frontend/index.html")
  content_type  = "text/html; charset=utf-8"
  cache_control = "no-cache"
}

resource "aws_cloudfront_origin_access_control" "sitio" {
  name                              = "${var.nombre_proyecto}-sitio"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "auth_basica" {
  name    = "${var.nombre_proyecto}-auth-basica"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-JS
    function handler(event) {
      var h = event.request.headers;
      var esperado = 'Basic ${base64encode("${var.usuario_web}:${random_password.web.result}")}';
      if (!h.authorization || h.authorization.value !== esperado) {
        return {
          statusCode: 401,
          statusDescription: 'Unauthorized',
          headers: { 'www-authenticate': { value: 'Basic realm="Wenia - Engineering Modernization Hub"' } }
        };
      }
      return event.request;
    }
  JS
}

data "aws_cloudfront_cache_policy" "sin_cache" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "todo_menos_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

locals {
  rutas_api = ["/solicitudes*", "/ejecuciones*", "/docs*", "/openapi.json", "/redoc"]
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  comment             = "Engineering Modernization Hub (dashboard + API)"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # solo EE. UU./Europa: el más barato, suficiente para la demo
  http_version        = "http2and3"

  origin {
    origin_id                = "sitio"
    domain_name              = aws_s3_bucket.sitio.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.sitio.id
  }

  origin {
    origin_id   = "api"
    domain_name = aws_lb.api.dns_name

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = random_password.origen_secreto.result
    }
  }

  default_cache_behavior {
    target_origin_id       = "sitio"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.sin_cache.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.auth_basica.arn
    }
  }

  dynamic "ordered_cache_behavior" {
    for_each = local.rutas_api
    content {
      path_pattern             = ordered_cache_behavior.value
      target_origin_id         = "api"
      viewer_protocol_policy   = "redirect-to-https"
      allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods           = ["GET", "HEAD"]
      cache_policy_id          = data.aws_cloudfront_cache_policy.sin_cache.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.todo_menos_host.id
      compress                 = true

      function_association {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.auth_basica.arn
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# El bucket solo lo puede leer ESTA distribución (OAC).
resource "aws_s3_bucket_policy" "sitio" {
  bucket = aws_s3_bucket.sitio.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "SoloCloudFront"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.sitio.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.web.arn } }
    }]
  })
}
