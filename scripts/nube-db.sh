#!/usr/bin/env bash
# Consulta de SOLO LECTURA a la base de datos RDS desplegada.
# RDS es privado (solo alcanzable desde la VPC), así que se lanza una tarea Fargate
# efímera con la imagen de la API (que ya trae psycopg y las credenciales por SSM),
# ejecuta la consulta y su salida se lee del log. La conexión fuerza
# default_transaction_read_only=on: un INSERT/UPDATE/DELETE falla en el servidor.
#
# Uso:  scripts/nube-db.sh                          # últimas 10 ejecuciones
#       scripts/nube-db.sh "select * from fuente where ejecucion_id = 20"
#       scripts/nube-db.sh "select relname, n_live_tup from pg_stat_user_tables order by 1"
set -euo pipefail
CLUSTER=${EMH_CLUSTER:-emh-cluster}
SQL=${1:-"select e.id, e.estado, e.resultado, e.iteraciones_usadas as iter, round(e.costo_estimado_usd::numeric,4) as costo_usd, s.objetivo from ejecucion e join solicitud s on s.id = e.solicitud_id order by e.id desc limit 10"}

SG=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=emh-api-sg" --query 'SecurityGroups[0].GroupId' --output text)
SUBREDES=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=emh-publica-*" --query 'Subnets[].SubnetId' --output text | tr '\t' ',')

read -r -d '' PY <<'PYEOF' || true
import os
from urllib.parse import quote

import psycopg

q = lambda v: quote(os.environ[v], safe="")
dsn = (
    f"postgresql://{q('EMH_DB_USER')}:{q('EMH_DB_PASSWORD')}"
    f"@{os.environ['EMH_DB_HOST']}:5432/{os.environ['EMH_DB_NAME']}?sslmode=require"
)
with psycopg.connect(dsn, options="-c default_transaction_read_only=on", autocommit=True) as c:
    cur = c.execute(os.environ["EMH_SQL"])
    print("=== RESULTADO ===")
    if cur.description:
        print(" | ".join(d.name for d in cur.description))
        for r in cur.fetchall():
            print(" | ".join(str(v).replace("\n", " ")[:90] for v in r))
    print("=== FIN ===")
PYEOF

OVERRIDES=$(python3 - "$PY" "$SQL" <<'EOF'
import json, sys
print(json.dumps({"containerOverrides": [{
    "name": "api", "command": ["python", "-c", sys.argv[1]],
    "environment": [{"name": "EMH_SQL", "value": sys.argv[2]}]}]}))
EOF
)

TAREA=$(aws ecs run-task --cluster "$CLUSTER" --task-definition emh-api --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBREDES],securityGroups=[$SG],assignPublicIp=ENABLED}" \
  --overrides "$OVERRIDES" --query 'tasks[0].taskArn' --output text)
ID=${TAREA##*/}
echo "Consultando (tarea $ID, tarda ~30-60 s)..." >&2
aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TAREA"
sleep 3
aws logs get-log-events --log-group-name /ecs/emh-api --log-stream-name "api/api/$ID" --query 'events[].message' --output text \
  | tr '\t' '\n' | sed -n '/=== RESULTADO ===/,/=== FIN ===/p' | sed '1d;$d' \
  || true
CODIGO=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TAREA" --query 'tasks[0].containers[0].exitCode' --output text)
[ "$CODIGO" = "0" ] || { echo "La consulta falló (código $CODIGO). Log:" >&2; aws logs get-log-events --log-group-name /ecs/emh-api --log-stream-name "api/api/$ID" --query 'events[-5:].message' --output text >&2; exit 1; }
