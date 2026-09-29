#!/usr/bin/env bash
# Imprime host:puerto de la API desplegada en AWS (la tarea Fargate no tiene
# balanceador, ADR-006: su IP pública es la de la interfaz de red de la tarea).
# Uso:  export EMH_API=$(scripts/nube-url.sh)   y luego scripts/02-enviar.sh 1
set -euo pipefail
CLUSTER=${EMH_CLUSTER:-emh-cluster}
SERVICIO=${EMH_SERVICIO:-emh-api}
TAREA=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name "$SERVICIO" --desired-status RUNNING \
  --query 'taskArns[0]' --output text)
[ "$TAREA" != "None" ] || { echo "La API no está corriendo (¿imágenes en ECR y terraform apply completo?)" >&2; exit 1; }
ENI=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TAREA" \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)
IP=$(aws ec2 describe-network-interfaces --network-interface-ids "$ENI" \
  --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
echo "$IP:8000"
