#!/usr/bin/env bash
# Uso: scripts/03-aprobar.sh <ejecucion_id> [APROBADO|RECHAZADO]
set -euo pipefail
B=localhost:8000; ID=$1; DEC=${2:-APROBADO}
P=$(curl -s $B/ejecuciones/$ID/plan)
PID=$(echo "$P" | python3 -c "import sys,json;print(json.load(sys.stdin)['plan_id'])")
H=$(echo "$P" | python3 -c "import sys,json;print(json.load(sys.stdin)['hash'])")
curl -s -X POST $B/ejecuciones/$ID/aprobacion -H "Content-Type: application/json" \
  -d "{\"plan_id\":$PID,\"plan_hash\":\"$H\",\"decision\":\"$DEC\",\"aprobador\":\"dev:tu-correo@example.com\"}" | python3 -m json.tool
echo -n "Ejecutando"
for i in $(seq 1 90); do
  S=$(curl -s $B/ejecuciones/$ID); echo "$S" | grep -q '"resultado":"' && break; echo -n "."; sleep 8
done; echo
echo "$S" | python3 -m json.tool
echo "Reporte:  scripts/04-reporte.sh $ID"
