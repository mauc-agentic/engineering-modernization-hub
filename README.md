# Engineering Modernization Hub

Prototipo funcional de un producto interno de autoservicio que acompaña
modernizaciones de repositorios (frameworks, runtimes, dependencias,
imágenes base) mediante IA, con controles deterministas para todo lo que
importa: permisos, comandos, rutas, presupuesto, aprobación humana, secretos
y confirmación de pruebas.

Caso de estudio: Staff AI Platform Engineer (Wenia). La documentación
completa —visión, requisitos, arquitectura, políticas, seguridad, uso de
IA, escenarios y ADRs— vive en [`DOCS/`](DOCS/00-vision.md).

**Principio de diseño:** el modelo propone, el código dispone. Amazon Nova 2
Lite decide qué investigar, qué escribir y cómo corregir; el código decide
qué está permitido, qué se ejecuta y qué cuenta como verificado.

## Requisitos

- Python 3.11+ (probado con 3.12)
- Docker Desktop (o daemon Docker equivalente) corriendo
- `uv` (o `pip`) para instalar dependencias
- Credenciales de AWS con acceso a Bedrock (`aws sts get-caller-identity` debe funcionar) para el nivel B (modelo real)
- `git`

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

```bash
# Todo (nivel A + contratos + Docker real), sin nivel B:
pytest -m "not live" -q

# Solo lo rápido, sin tocar Docker real:
pytest -q --ignore=tests/contract/test_docker_sandbox.py

# Nivel B (Bedrock real, requiere credenciales AWS):
pytest -m live -q

# Verificar la regla de dependencias entre capas (NFR-015/016):
lint-imports
```

## Levantar la API

```bash
export EMH_DATA_DIR=./data          # SQLite + workspaces clonados
# EMH_MODO_SIMULADO=1 usa ScriptedModel en vez de Bedrock (sin credenciales AWS)
uvicorn emh.api.app:app_factory --factory --reload --port 8000
```

La documentación interactiva (OpenAPI) queda en `http://localhost:8000/docs`.

## Reproducir la demo de extremo a extremo

Dos repositorios propios, verificados empíricamente (no solo documentados),
sirven de fixtures — ver `DOCS/11-demo.md`:

- [`ledger-service`](https://github.com/mauc-agentic/ledger-service) — modernización **exitosa con corrección** (PyYAML 5.3.1 → 6.0.2, escenarios 1 y 3).
- [`orders-api`](https://github.com/mauc-agentic/orders-api) — modernización **inviable** (Flask 2.0.3 → 3.0.x sobre Python 3.7, escenario 2).

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
infra/           Terraform (despliegue en AWS, ADR-006/ADR-007)
```

## Lo que está simulado (RN-14, marcado explícitamente)

- `ScriptedModel` (`emh/models/scripted.py`): nivel A de pruebas. Nunca se usa en la demo en vivo.
- La identidad del aprobador en F1 no está autenticada: se acepta el campo `aprobador` declarado por quien llama a la API (ver `DOCS/07-seguridad.md` §2, resuelto en F2 con SSO — `FR-039`).

## Despliegue en AWS (opcional, ADR-006/ADR-007)

```bash
cd infra
terraform init
terraform apply     # revisa el plan antes de confirmar
# ... usar la API en la URL que imprime el output ...
terraform destroy   # IMPORTANTE: ejecutar al terminar (RDS tiene costo por hora)
```
