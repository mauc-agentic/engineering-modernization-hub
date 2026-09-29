# 12 — Guion del video de evidencia operativa

Duración objetivo: 12–14 min. Todo corre con **Bedrock real (Nova 2 Lite) + Docker real + repos reales**; el nivel A (`ScriptedModel`) no se usa aquí.
Costo por corrida completa: ~USD 0.05–0.10.

## Antes de grabar (fuera de cámara)

**Opción A — URL pública en AWS (recomendada para el video):** abre `https://<dominio>.cloudfront.net` (`terraform output url_web`; usuario `wenia`, contraseña con `terraform output -raw contrasena_web`). Es el dashboard con marca Wenia, ya conectado a la API real en Fargate/RDS: no hay que preparar nada más.

**Opción B — local:**

```bash
cd engineering-modernization-hub
source .venv/bin/activate
scripts/00-preparar.sh      # comprueba Docker/AWS/gh, deja la API arriba con datos limpios
open frontend/index.html    # dashboard; la API queda en http://localhost:8000
```

Terminal a la izquierda, dashboard a la derecha. Cerrar notificaciones. Si algo falla, `tail /tmp/emh_demo_api.log`.

## Guion

| Min | Qué se muestra | Comando / acción | Qué se dice |
|---|---|---|---|
| 0:00 | Datos de la demo | Mostrar `DOCS/11-demo.md` | Repo `ledger-service`, commit `844f287`, PyYAML 5.3.1 → 6.0.2, por qué se eligió (rompe pruebas al primer intento). |
| 1:00 | Arquitectura y controles | Slides 3 y 5 | Seis capas, ocho controles deterministas; el modelo propone, el código dispone. |
| 3:00 | Pruebas y regla de capas | `scripts/01-pruebas.sh` | 166 pruebas (incluye Bedrock y Docker reales) e `import-linter` 3/3. *(~45 s; se puede grabar aparte y cortar.)* |
| 4:00 | **Escenario 1 — exitosa** | `scripts/02-enviar.sh 1` | Descubre, consulta PyPI/GitHub, veredicto VIABLE con evidencia, plan con rutas y hash. |
| 6:00 | **Aprobación humana** | En el dashboard: revisar plan → **Aprobar** (o `scripts/03-aprobar.sh 1`) | El grafo estaba pausado; nada se toca sin esta decisión, ligada al hash del plan. |
| 7:30 | Resultado | `scripts/04-reporte.sh 1` y `scripts/05-cambios-aplicados.sh 1` | LISTO_PARA_REVISION, 7/7 pruebas con salida real capturada, diff real, fuentes citadas, costo. |
| 9:00 | **Escenario 2 — inviable** | `scripts/02-enviar.sh 2` | Restricción Python 3.7 vs Flask 3.0 `Requires-Python >=3.8`: INVIABLE, sin plan, sin cambios, con evidencia. |
| 10:30 | **Escenario 4 — insegura** | `scripts/02-enviar.sh 4` → aprobar con `scripts/03-aprobar.sh 3` → `scripts/04-reporte.sh 3` | La solicitud pide ignorar el plan, mostrar secretos y desactivar tests. Se trata como dato no confiable: tests intactos, sin secretos, alcance respetado. |
| 12:00 | Escenario 3 (corrección) | Mostrar `tests/scenarios/test_grafo_exitoso_con_correccion.py` | Prueba guionada (SIMULATED, dicho explícitamente): falla → diagnóstico → parche dentro del alcance → re-verificación, con límite de iteraciones. |
| 12:30 | Observabilidad | Tarjeta "Traza de ejecución" del dashboard (y, si hay tiempo, CloudWatch → GenAI Observability) | Cada nodo, llamada al modelo y herramienta con su duración real y tokens; se ve el ciclo de corrección. Nunca prompts ni código. |
| 13:00 | Cierre | Slide 10 | Extensibilidad (segunda estrategia sin tocar el núcleo), el despliegue en AWS (Terraform, 35 recursos) y qué es Fase 2. |

## Notas honestas para la narración

- El modelo es no determinista: a veces el plan omite un archivo y el control 7 bloquea el parche (BLOQUEADO / ACCION_BLOQUEADA). Es el control funcionando; si ocurre grabando, se muestra y se explica en vez de repetir.
- Con el modelo real el escenario 3 rara vez ocurre solo (acierta el primer parche): se cubre con la prueba guionada, dicho así.
- En el escenario 4 el modelo real suele ignorar la inyección; los controles no necesitan actuar. La prueba de que bloquean es la suite guionada (`tests/scenarios/test_grafo_solicitud_insegura.py`).
- Puedes grabar contra AWS (`export EMH_API=$(scripts/nube-url.sh)`) o en local (`00-preparar.sh`): los scripts son los mismos. En AWS los IDs de ejecución no empiezan en 1: usa el que imprime `02-enviar.sh`. La API en AWS solo acepta tu IP (`cidr_acceso_api`).
- En local los IDs son 1, 2, 3 tras `00-preparar.sh` (datos limpios); ajusta `03-aprobar.sh <id>` si repites alguno.
