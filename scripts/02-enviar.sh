#!/usr/bin/env bash
# Uso: scripts/02-enviar.sh 1|2|4     (1 exitosa, 2 inviable, 4 insegura)
# Registra la solicitud y espera al análisis + plan (o al resultado final).
set -euo pipefail
cd "$(dirname "$0")"
B=${EMH_API:-localhost:8000}   # en AWS: export EMH_API=$(scripts/nube-url.sh)
F=$(ls solicitudes/$1-*.json)
R=$(curl -s -X POST $B/solicitudes -H "Content-Type: application/json" -d @"$F")
ID=$(echo "$R" | python3 -c "import sys,json;print(json.load(sys.stdin)['ejecucion_id'])")
echo "Solicitud registrada -> ejecucion_id=$ID   (ver en el dashboard: Seguir $ID)"
echo -n "Esperando análisis y plan"
for i in $(seq 1 60); do
  S=$(curl -s $B/ejecuciones/$ID)
  echo "$S" | grep -q 'ESPERANDO_APROBACION\|"resultado":"' && break
  echo -n "."; sleep 5
done; echo
echo "$S" | python3 -m json.tool
echo "--- viabilidad"; curl -s $B/ejecuciones/$ID/analisis-viabilidad | python3 -m json.tool
if echo "$S" | grep -q ESPERANDO_APROBACION; then
  echo "--- plan"; curl -s $B/ejecuciones/$ID/plan | python3 -m json.tool
  echo; echo "Aprobar:  scripts/03-aprobar.sh $ID     (o el botón del dashboard)"
fi
