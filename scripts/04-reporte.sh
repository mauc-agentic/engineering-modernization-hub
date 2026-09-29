#!/usr/bin/env bash
# Uso: scripts/04-reporte.sh <ejecucion_id>   -> verificaciones, eventos y reporte
set -euo pipefail
B=${EMH_API:-localhost:8000}; ID=$1
echo "=== Verificaciones (salida real capturada)"
curl -s $B/ejecuciones/$ID/verificaciones | python3 -c "
import sys,json
for v in json.load(sys.stdin): print(v['resultado'], f\"{v['pruebas_exitosas']}/{v['pruebas_totales']}\", v['comando'])"
echo "=== Eventos de seguridad"
curl -s $B/ejecuciones/$ID/eventos | python3 -m json.tool
echo "=== Reporte"
curl -s $B/ejecuciones/$ID/reporte | python3 -m json.tool
