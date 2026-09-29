#!/usr/bin/env bash
# Deja el entorno listo y la API arriba (Bedrock real + Docker real).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "== Comprobaciones previas"
docker info >/dev/null 2>&1 && echo "  ok Docker" || { echo "  FALTA Docker corriendo"; exit 1; }
aws sts get-caller-identity --query Account --output text >/dev/null && echo "  ok credenciales AWS" || { echo "  FALTAN credenciales AWS"; exit 1; }
gh auth status >/dev/null 2>&1 && echo "  ok gh (clon de repos privados)" || { echo "  FALTA gh auth login"; exit 1; }
docker pull -q python:3.12-slim >/dev/null && echo "  ok imagen del sandbox"

echo "== Datos limpios (ejecución nueva, ID 1)"
pkill -f "uvicorn emh.api.app" 2>/dev/null || true
sleep 1
export EMH_DATA_DIR="$(mktemp -d)"
echo "$EMH_DATA_DIR" > /tmp/emh_demo_datadir
nohup uvicorn emh.api.app:app_factory --factory --port 8000 > /tmp/emh_demo_api.log 2>&1 &
for i in $(seq 1 20); do curl -sf localhost:8000/docs >/dev/null && break; sleep 1; done
curl -sf localhost:8000/docs >/dev/null && echo "  ok API en http://localhost:8000 (log: /tmp/emh_demo_api.log)" || { echo "  la API no arrancó"; tail /tmp/emh_demo_api.log; exit 1; }
echo "Listo. Abre el dashboard:  open frontend/index.html"
