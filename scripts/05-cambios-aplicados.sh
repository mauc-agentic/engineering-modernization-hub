#!/usr/bin/env bash
# Uso: scripts/05-cambios-aplicados.sh <ejecucion_id>  -> diff real en el workspace clonado
set -euo pipefail
D=$(cat /tmp/emh_demo_datadir)/workspaces/$1
cd "$D" && git --no-pager diff --stat && git --no-pager diff
