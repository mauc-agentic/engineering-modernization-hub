# Engineering Modernization Hub

Prototipo funcional de un producto interno de autoservicio que acompaña
modernizaciones de repositorios (frameworks, runtimes, dependencias,
imágenes base) mediante IA, con controles deterministas para todo lo que
importa: permisos, comandos, rutas, presupuesto, aprobación humana, secretos
y confirmación de pruebas.

Caso de estudio: Staff AI Platform Engineer (Wenia). La documentación
completa —visión, requisitos, arquitectura, políticas, seguridad, uso de
IA, escenarios y ADRs— vive en [`DOCS/`](DOCS/00-vision.md); el resumen para
lectura ejecutiva es [`DOCS/EJECUTIVO.md`](DOCS/EJECUTIVO.md).

**Principio de diseño:** el modelo propone, el código dispone. Amazon Nova 2
Lite decide qué investigar, qué escribir y cómo corregir; el código decide
qué está permitido, qué se ejecuta y qué cuenta como verificado.

## Requisitos

- Python 3.11+ (probado con 3.12)
- Docker Desktop (o daemon Docker equivalente) corriendo
- `uv` (o `pip`) para instalar dependencias
- Credenciales de AWS con acceso a Bedrock (modelo `us.amazon.nova-2-lite-v1:0`, región `us-east-1`; `aws sts get-caller-identity` debe funcionar). Sin ellas la API no puede ejecutar modernizaciones, porque la IA no es opcional
- `git` y, para clonar los repos privados de la demo, `gh auth login` (o credenciales equivalentes)

## Instalación

```bash
cd engineering-modernization-hub
uv venv --python 3.12
uv pip install -e ".[dev]"
source .venv/bin/activate
```

## Pruebas

El proyecto tiene dos niveles de pruebas (`DOCS/03-arquitectura.md` §8):

- **Nivel A** (`ScriptedModel`, **SIMULATED**): determinista, sin red ni Bedrock. Corre en segundos.
- **Nivel B** (`@pytest.mark.live`): contra Amazon Bedrock real (Nova 2 Lite). Requiere credenciales AWS.

La suite completa son 133 pruebas (más 1 omitida a propósito) e incluye Docker real y Bedrock real.

```bash
# Todo (nivel A + contratos + Docker real + Bedrock real):
pytest -q

# Sin Bedrock (no necesita credenciales AWS):
pytest -m "not live" -q

# Solo lo rápido, sin tocar Docker real:
pytest -q --ignore=tests/contract/test_docker_sandbox.py

# Solo el nivel B (Bedrock real, requiere credenciales AWS):
pytest -m live -q

# Verificar la regla de dependencias entre capas (NFR-015/016):
lint-imports
```

## Levantar la API

```bash
export EMH_DATA_DIR=./data          # SQLite + workspaces clonados (ignorado por git)
uvicorn emh.api.app:app_factory --factory --port 8000
```

Usa Amazon Bedrock y Docker reales. (`EMH_MODO_SIMULADO=1` existe solo para
pruebas: arma un `ScriptedModel` vacío que falla en la primera llamada; los
escenarios simulados se ejecutan con `pytest`, no con la API.)

La documentación interactiva (OpenAPI) queda en `http://localhost:8000/docs`.

## Dashboard de demo (visual, sin Backstage)

Backstage es F2 (`10-evolucion-producto.md`) — una instancia propia, un
*plugin* con su propio sistema de diseño y un proxy de backend son
demasiado para el tiempo disponible. En su lugar, con la API ya arriba:

```bash
open frontend/index.html   # o: python3 -m http.server 5500 -d frontend
```

Es una sola página sin dependencias que habla **directo con la API real**
(no simulada): registra la solicitud, sondea el estado, muestra el análisis
de viabilidad y el plan con botones **Aprobar**/**Rechazar**, y el reporte
final con verificaciones y eventos de seguridad en vivo. El campo de la
esquina superior derecha apunta a `http://localhost:8000` por defecto.

## Reproducir la demo de extremo a extremo

Atajo: la carpeta [`scripts/`](scripts/) automatiza todo lo de abajo
(`00-preparar.sh` levanta la API con datos limpios; `02-enviar.sh 1|2|4`
registra los escenarios; `03-aprobar.sh`, `04-reporte.sh`, `05-cambios-aplicados.sh`
completan el flujo) y [`DOCS/12-guion-video.md`](DOCS/12-guion-video.md) tiene
el guion con tiempos. Cada corrida real cuesta ~USD 0.05–0.10.

Dos repositorios propios, verificados empíricamente (no solo documentados),
sirven de fixtures — ver `DOCS/11-demo.md`:

- [`ledger-service`](https://github.com/mauc-agentic/ledger-service) — modernización **exitosa** (PyYAML 5.3.1 → 6.0.2, escenario 1; rompe 5 de 7 pruebas sin corregir). También sirve para el escenario 4 (solicitud insegura).
- [`orders-api`](https://github.com/mauc-agentic/orders-api) — modernización **inviable** (Flask 2.0.3 → 3.0.x sobre Python 3.7, escenario 2).

Los cuatro escenarios obligatorios del caso están cubiertos así: 1, 2 y 4 en vivo
(Bedrock + Docker + repos reales) y los cuatro como pruebas guionadas
(`tests/scenarios/`). El escenario 3 (prueba fallida → corrección → re-verificación)
se demuestra con la prueba guionada, porque el modelo real suele acertar el
primer parche; y, por la naturaleza del modelo, a veces el plan omite un archivo
y el control de alcance bloquea la ejecución (`BLOQUEADO`), que es el control funcionando.

```bash
curl -X POST http://localhost:8000/solicitudes -H "Content-Type: application/json" -d '{
  "repositorio_url": "https://github.com/mauc-agentic/ledger-service",
  "commit_referencia": "844f287e5918c11dc28c02eb2dc2d9be749d9975",
  "estrategia_id": "python_dependency_upgrade",
  "objetivo": "Actualizar PyYAML de 5.3.1 a 6.0.2",
  "version_esperada": "PyYAML==6.0.2",
  "limite_tiempo_segundos": 720, "limite_iteraciones": 3, "limite_costo_usd": 1.0,
  "solicitante": "dev:tu-correo@example.com"
}'
# -> {"ejecucion_id": 1, "estado": "DESCUBRIMIENTO"}

curl http://localhost:8000/ejecuciones/1                    # sondear estado
curl http://localhost:8000/ejecuciones/1/plan                # revisar el plan propuesto

curl -X POST http://localhost:8000/ejecuciones/1/aprobacion -H "Content-Type: application/json" -d '{
  "plan_id": 1, "plan_hash": "<hash del plan>", "decision": "APROBADO",
  "aprobador": "dev:tu-correo@example.com"
}'

curl http://localhost:8000/ejecuciones/1/reporte              # reporte final
```

El repositorio de `mauc-agentic/ledger-service` es privado; `git clone` real
necesita credenciales configuradas (`gh auth setup-git` si usas `gh`, o una
clave SSH/token con acceso).

## Estructura

```
emh/
  core/          dominio, máquina de estados, presupuestos, puertos
  policy/        PolicyGate y los 8 controles deterministas
  harness/       las 6 herramientas con contrato tipado
  agent/         grafo LangGraph, nodos, prompts
  strategies/    python_dependency_upgrade (+ registro)
  models/        BedrockModel (Nova 2 Lite) · ScriptedModel (SIMULATED)
  execution/     DockerSandbox (local) · wheelhouse
  persistence/   SqliteRunRepository
  reporting/     ReportRenderer
  api/           FastAPI
  bootstrap.py   raíz de composición
tests/
  unit/          núcleo, políticas, harness, agente (con dobles de prueba)
  contract/      SQLite, Docker real, Bedrock real, API
  scenarios/     los 4 escenarios obligatorios del caso, de extremo a extremo
scripts/         kit de demo: preparar, enviar, aprobar, reporte (+ solicitudes/*.json)
frontend/        dashboard de una sola página
infra/           Terraform (IaC validada con plan, sin apply; ADR-006/ADR-007)
DOCS/            especificación, ADRs, documento ejecutivo y guion del video
```

## Lo que está simulado (RN-14, marcado explícitamente)

- `ScriptedModel` (`emh/models/scripted.py`): nivel A de pruebas. Nunca se usa en la demo en vivo.
- Adaptadores de nube (`PostgresRunRepository`, `FargateSandbox`, `EMH_ENV=aws`): diseñados, **no implementados** (ver más abajo).
- La identidad del aprobador en F1 no está autenticada: se acepta el campo `aprobador` declarado por quien llama a la API (ver `DOCS/07-seguridad.md` §2, resuelto en F2 con SSO — `FR-039`).

## Infraestructura en AWS (solo IaC validada, ADR-006/ADR-007)

> **Alcance honesto:** solo la infraestructura como código está entregada y validada (`terraform validate` + `terraform plan`, 33 recursos). Los adaptadores de nube (`PostgresRunRepository`, `FargateSandbox`, `EMH_ENV=aws`) **no están implementados**: hoy la API corre con Docker + SQLite (local). Aplicar `terraform apply` crearía la infraestructura, pero la aplicación no correría sobre ella hasta implementar esos adaptadores (F2). No se ejecutó `apply`; no hay recursos facturables.

```bash
cd infra
terraform init
terraform plan -var="email_alertas_presupuesto=tu-correo@example.com"   # 33 recursos a crear
# Solo si algún día se implementan los adaptadores: terraform apply, y
# terraform destroy al terminar (RDS cobra por hora).
```
