#!/usr/bin/env bash
# Construye (ARM64, como las tareas Fargate) y publica las dos imágenes en ECR.
# Requiere que los repositorios ECR ya existan (terraform apply -target=... o el
# apply completo). Uso: scripts/nube-publicar-imagenes.sh [tag]   (por defecto: latest)
set -euo pipefail
cd "$(dirname "$0")/.."
TAG=${1:-latest}
REGION=${AWS_REGION:-us-east-1}
CUENTA=$(aws sts get-caller-identity --query Account --output text)
REGISTRO="$CUENTA.dkr.ecr.$REGION.amazonaws.com"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRO" >/dev/null
for componente in api sandbox; do
  docker build --platform linux/arm64 -f "Dockerfile.$componente" -t "$REGISTRO/emh-$componente:$TAG" .
  docker push "$REGISTRO/emh-$componente:$TAG"
done
echo "Imágenes publicadas: $REGISTRO/emh-{api,sandbox}:$TAG"
