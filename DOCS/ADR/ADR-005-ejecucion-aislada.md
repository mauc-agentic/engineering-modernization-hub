# ADR-005 — Ejecución aislada y red del sandbox

**Estado:** Aceptado — 2026-09-28

## Contexto

El código del repositorio objetivo es, por definición, no confiable (RN-09): un `conftest.py` o un `setup.py` podrían intentar leer variables de entorno o alcanzar la red. `run_tests` es la única herramienta que ejecuta ese código (`03-arquitectura.md` §3.3). El caso exige un entorno aislado, "sin red salvo *allowlist* del registro de paquetes".

## Decisión

**Docker efímero**, un contenedor por ejecución, con **dos fases de red separadas**:

1. **Instalación de dependencias:** se resuelve con un patrón *wheelhouse* — el host descarga las ruedas con `pip download --only-binary=:all:` (sin ejecutar código de `setup.py`) desde el índice de paquetes oficial, y el contenedor instala con `pip install --no-index --find-links=/wheelhouse`.
2. **Ejecución de pruebas:** el contenedor corre **sin red** en absoluto (`--network none`).

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Proxy HTTP con *allowlist* de dominios dentro del contenedor | Funciona, pero añade un componente más que operar y asegurar (el propio proxy es superficie de ataque) para resolver algo que el *wheelhouse* resuelve con cero red en el contenedor. Se documenta como alternativa de F2 si algún paquete sin rueda binaria lo exige. |
| Red abierta con reglas de *firewall* por contenedor (`iptables`) | Depende de capacidades de red del host anfitrión (privilegios elevados) que contradicen NFR-004 (sin privilegios adicionales); fragiliza el aislamiento. |
| Máquina virtual dedicada por ejecución | Aislamiento más fuerte, pero el costo de arranque y operación no se justifica para un prototipo con contenedores efímeros de vida corta; queda como opción de F2 si el modelo de amenazas lo exige. |

## Evaluación

| Dimensión | Evaluación |
|---|---|
| **Seguridad** | Sin red durante la ejecución de pruebas, un intento de exfiltración (por ejemplo, un `conftest.py` que intenta llamar a un *webhook*) no tiene a dónde ir. Sin variables de entorno de credenciales en el contenedor (NFR-004), no hay nada que exfiltrar aunque hubiera red. |
| **Portabilidad** | Docker corre igual en el portátil del autor y en CI; `Sandbox` es un puerto (`03-arquitectura.md` §2), así que F2 puede cambiar a Kubernetes Jobs sin tocar el dominio. |
| **Costo** | Sin costo de infraestructura adicional para F1; Docker Desktop ya está disponible en el entorno de desarrollo. |
| **Operación** | Contenedor efímero, destruido ≤ 10 s tras terminar (NFR-004); no queda estado que limpiar entre ejecuciones. |
| **Escalabilidad** | Un contenedor por ejecución escala horizontalmente sin cambios; el límite de F1 es el host único, no el diseño. |
| **Experiencia del desarrollador** | El *wheelhouse* es determinista y cacheable: instalar las mismas dependencias dos veces no repite la descarga, lo que ayuda a NFR-011 (duración de la demo). |

## Limitación conocida

Un paquete sin rueda binaria para la plataforma objetivo no se puede instalar con este patrón (no se ejecuta su `setup.py`). Cuando esto ocurre, la ejecución termina en `BLOQUEADO` con un motivo explícito, en vez de arriesgar una instalación con red abierta. Es una limitación aceptada para F1, documentada también en `03-arquitectura.md` §6.

## Consecuencias

- `emh/execution` es el único paquete que importa el SDK de Docker.
- `emh/harness` invoca `run_tests` con el perfil de comandos que declara la estrategia (`06-estrategias.md`); el *wheelhouse* se construye antes de crear el contenedor de pruebas.
- El repositorio de la demo (`11-demo.md`) se elige, entre otras razones, porque sus dependencias tienen ruedas binarias disponibles para la plataforma de CI.
