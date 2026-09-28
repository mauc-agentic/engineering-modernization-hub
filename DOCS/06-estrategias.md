# 06 — Estrategias de modernización

| | |
|---|---|
| **Estado** | APROBADO el 2026-09-28 |
| **Depende de** | `03-arquitectura.md` §5 (resumen de la interfaz) |
| **Paquete** | `emh/strategies` |

Este documento es el contrato completo de `ModernizationStrategy`, la estrategia de referencia que se implementa en F1, y el ejercicio explícito de añadir una segunda estrategia sin tocar el núcleo — el punto que el caso pide demostrar.

---

## 1. La interfaz

```python
class ModernizationStrategy(Protocol):
    id: str

    def supports(self, request: Solicitud) -> Soporte:
        """¿Esta estrategia cubre el objetivo de esta solicitud?"""

    def discovery_signals(self) -> list[Senal]:
        """Qué buscar en el repositorio para entender el punto de partida
        (manifiestos, archivos de versión, lockfiles)."""

    def official_sources(self, request: Solicitud) -> list[DominioFuente]:
        """Dominios válidos para search_docs: documentación oficial,
        release notes, registro de paquetes, avisos de seguridad."""

    def command_profile(self) -> PerfilComandos:
        """Comandos de instalación y verificación que esta estrategia
        necesita, como subconjunto propuesto de la allowlist global."""

    def scope_template(self, plan_hint: PlanHint) -> PlantillaAlcance:
        """Plantilla de rutas y tipos de operación típicos de esta
        modernización, que el nodo proponer_plan concreta por solicitud."""

    def prompt_pack(self) -> PaqueteInstrucciones:
        """Instrucciones específicas para el modelo: qué preguntar, qué
        patrones de riesgo buscar, cómo redactar el plan para este tipo
        de modernización."""
```

Una estrategia **no** ejecuta nada: todos sus métodos devuelven datos (modelos pydantic). Ni `emh/core`, ni `emh/agent`, ni `emh/harness` importan una estrategia concreta — se resuelven por `id` desde un registro poblado en `emh/bootstrap.py` (RN-13).

```python
# emh/bootstrap.py
REGISTRO_ESTRATEGIAS: dict[str, ModernizationStrategy] = {
    "python_dependency_upgrade": PythonDependencyUpgradeStrategy(),
}
```

---

## 2. Estrategia de referencia (F1): `python_dependency_upgrade`

Actualiza una dependencia declarada en `requirements.txt` / `pyproject.toml` a una versión objetivo, de extremo a extremo.

| Método | Devuelve |
|---|---|
| `supports` | `Soporte(aplica=True)` cuando `request.objetivo` referencia un paquete PyPI y `request.version_esperada` es una versión o un rango (`semver`) parseable. |
| `discovery_signals` | Señales: `requirements.txt`, `pyproject.toml` (sección `[project.dependencies]` o `[tool.poetry.dependencies]`), `*.lock`, y las líneas de `import` del paquete objetivo en el código fuente. |
| `official_sources` | `pypi.org` (metadatos y versiones), `docs para el paquete` (si el paquete publica una URL de documentación en sus metadatos de PyPI), `github.com/<owner>/<repo>/releases` del repositorio del paquete (release notes), `github.com/<owner>/<repo>/security/advisories` (avisos de seguridad). |
| `command_profile` | Instalación: `pip download --only-binary=:all: -d /wheelhouse <paquete>==<version>` (host) + `pip install --no-index --find-links=/wheelhouse -r requirements.txt` (contenedor). Verificación: `pytest -q --tb=short`. |
| `scope_template` | Rutas: el manifiesto de dependencias (`requirements.txt` o `pyproject.toml`), el/los módulo(s) que importan el paquete objetivo (detectados en el descubrimiento), y el directorio de pruebas existente. Operaciones: modificar (nunca crear ni borrar el manifiesto). |
| `prompt_pack` | Instrucciones: extraer el *changelog* entre la versión actual y la objetivo; identificar *breaking changes* declarados; relacionar cada *breaking change* con usos del paquete en el código fuente antes de decidir viabilidad; nunca actualizar transitivamente otras dependencias no solicitadas. |

Es la estrategia usada en los dos ejemplos de demo (`09-escenarios.md`, `11-demo.md`).

---

## 3. Cómo se agrega una segunda estrategia, sin tocar el núcleo

Ejercicio completo con la estrategia de **imagen base** (diseño de F2, **no se implementa**), para demostrar que el mecanismo funciona en un tipo de modernización estructuralmente distinto (no es "una dependencia más", es un artefacto de infraestructura).

### 3.1 Qué se escribe

Un archivo nuevo, `emh/strategies/base_image.py`:

```python
class BaseImageUpgradeStrategy:
    id = "base_image_upgrade"

    def supports(self, request: Solicitud) -> Soporte:
        # aplica si el repositorio tiene un Dockerfile y el objetivo
        # referencia una imagen base (p. ej. "python:3.11-slim -> python:3.12-slim")
        ...

    def discovery_signals(self) -> list[Senal]:
        return [Senal(patron="Dockerfile"), Senal(patron="**/Dockerfile*"),
                Senal(patron=".dockerignore")]

    def official_sources(self, request):
        return [DominioFuente("hub.docker.com"),          # registro de imágenes
                DominioFuente("github.com/docker-library")] # release notes de la imagen oficial

    def command_profile(self):
        return PerfilComandos(
            instalacion=[],  # no aplica: no hay dependencias que descargar
            verificacion=[["docker", "build", "-f", "Dockerfile", "."],
                          ["pytest", "-q"]],  # build + suite existente sobre la nueva imagen
        )

    def scope_template(self, plan_hint):
        return PlantillaAlcance(rutas=["Dockerfile"], operaciones=["modificar"])

    def prompt_pack(self):
        return PaqueteInstrucciones(
            instrucciones="Compara las notas de versión de la imagen base…",
        )
```

### 3.2 Qué se toca fuera de ese archivo

| Cambio | Dónde | Cuántas líneas |
|---|---|---|
| Registrar la estrategia | `emh/bootstrap.py` | 1 línea (`REGISTRO_ESTRATEGIAS["base_image_upgrade"] = BaseImageUpgradeStrategy()`) |
| Añadir `docker build` a la *allowlist* global, si aún no está | `emh/policy` (control 2, `05-politicas-y-controles.md`) | 1 línea, como decisión explícita y revisable — no la añade la estrategia por sí misma |

### 3.3 Qué **no** se toca

`emh/core` (dominio, máquina de estados, presupuestos), `emh/agent` (el grafo y sus nodos), `emh/harness` (las seis herramientas ya existentes le bastan: `read_file` para leer el `Dockerfile`, `apply_patch` para modificarlo, `run_tests` para correr `docker build` + `pytest` dentro del perfil de comandos que la estrategia declaró).

### 3.4 Por qué funciona

El grafo (`03-arquitectura.md` §4) no pregunta "¿es una dependencia o una imagen?" en ningún nodo: pregunta "¿qué dice la estrategia activa que debo buscar, dónde y con qué verificar?", y ejecuta el mismo flujo — descubrir con las señales declaradas, consultar las fuentes declaradas, proponer un plan dentro de la plantilla de alcance declarada, aplicar, verificar con el perfil de comandos declarado. La política decide qué de eso está permitido, independientemente de qué estrategia lo pidió.

### 3.5 Prueba que lo demuestra

NFR-015 se verifica con una **tercera** estrategia, ficticia, definida solo en `tests/`: `EchoUpgradeStrategy` (declara una señal trivial, una fuente ficticia y un comando de verificación `["true"]`). La prueba la registra en un `REGISTRO_ESTRATEGIAS` de prueba, ejecuta el flujo completo contra un repositorio de prueba, y confirma con `import-linter` que ningún archivo de `emh/core` cambió ni fue tocado por el *diff* de la prueba.

---

## 4. Tercera estrategia (mención, F2)

`framework_migration` (migración de framework a una versión mayor) sigue el mismo patrón: señales serían archivos de configuración específicos del framework, fuentes serían la guía de migración oficial y el *changelog* del framework, perfil de comandos correría el conjunto de pruebas más un *linter* de compatibilidad si el framework lo ofrece. No se detalla más porque el punto (extensibilidad sin tocar el núcleo) ya queda demostrado con la de imagen base; ver `10-evolucion-producto.md`.
