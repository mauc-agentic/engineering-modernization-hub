# 05 — Políticas y controles

| | |
|---|---|
| **Estado** | APROBADO el 2026-09-28 |
| **Depende de** | `00-vision.md` (RN-01 a RN-10) · `03-arquitectura.md` §3.2 |
| **Paquete** | `emh/policy` |

Este documento detalla, control por control, lo que el caso exige como "determinístico": nada aquí consulta al modelo. Cada control es una función pura `evaluar(accion, contexto) -> Decision`, y `PolicyGate` es su composición. *Deny by default*: una acción que ninguna regla permite explícitamente se rechaza.

```python
class Decision(BaseModel):
    permitido: bool
    regla: str                 # qué regla decidió
    motivo: str                # explicación legible
```

`PolicyGate.evaluar()` se llama **dentro** de cada herramienta (`emh/harness`), nunca como un paso previo del grafo que un nodo pudiera saltarse (RN-03, respaldado por la guía AWS pág. 10: "integre las barreras de protección directamente en sus soluciones, no como pasos de aprobación independientes").

---

## Contexto de política

Todo control recibe el mismo contexto, construido por el núcleo a partir de lo persistido — nunca de lo que el modelo afirme:

```python
class ContextoPolitica(BaseModel):
    ejecucion_id: int
    plan_aprobado: Plan | None          # None si aún no hay aprobación
    presupuesto: EstadoPresupuesto      # tokens, tiempo, iteraciones consumidos y límites
    linea_base_pruebas: int             # número de pruebas antes de cualquier cambio
    workspace_root: Path                # raíz confinada del clon
```

---

## Los ocho controles

### 1. Permisos

**Garantiza:** el agente solo invoca las seis herramientas registradas (`clone_repo`, `list_files`, `read_file`, `search_docs`, `apply_patch`, `run_tests`), con argumentos que cumplen su contrato pydantic.

- El registro de herramientas expuesto al modelo es una lista cerrada; no existe una herramienta genérica de "ejecutar función" o "shell".
- Un argumento que no valida contra el esquema de la herramienta se rechaza antes de construir ninguna acción — nunca se coacciona ni se completa con valores por defecto silenciosos.

**Prueba:** invocar una herramienta con un campo de tipo incorrecto o un campo extra no declarado; se espera rechazo sin efecto.

### 2. Comandos permitidos

**Garantiza:** solo se ejecutan comandos de una *allowlist* estricta dentro del contenedor.

- La *allowlist* es la intersección entre una lista global fija en `emh/policy` (p. ej. `pip`, `pytest`, `python -m build`) y el perfil de comandos que declara la estrategia activa (`06-estrategias.md`). Una estrategia puede *restringir* ese conjunto para su caso, nunca *ampliarlo*.
- Los comandos se invocan como **lista de argumentos** (`subprocess`-estilo `exec`, sin `shell=True`), nunca como una cadena interpretada por una shell. Esto elimina el vector de "`; rm -rf /`" incluso si el modelo lo propusiera.
- Un comando fuera de la lista se rechaza y genera un `EVENTO_SEGURIDAD` con severidad `CRITICA`.

**Prueba:** proponer `bash -c "..."`, `curl`, `rm` o cualquier comando ausente de la lista; se espera rechazo y evento registrado (NFR-005, escenario 4).

### 3. Rutas modificables

**Garantiza:** solo se tocan las rutas declaradas en el plan aprobado.

- Toda ruta se resuelve a un path absoluto y se verifica que quede **dentro** de `workspace_root` (protección contra `..`, enlaces simbólicos que escapen, o rutas absolutas fuera del clon).
- El conjunto de rutas del parche propuesto debe ser subconjunto de `plan_aprobado.rutas_declaradas`. Una sola ruta fuera de ese conjunto rechaza el parche completo (no se aplica parcialmente un parche parcialmente válido).

**Prueba:** un parche que modifica un archivo no declarado en el plan (p. ej. `.github/workflows/ci.yml` cuando el plan solo declaró `requirements.txt`) se rechaza (AC-06).

### 4. Presupuestos

**Garantiza:** corte duro de tokens, tiempo de pared e iteraciones.

- `PresupuestoMeter` (núcleo) se consulta **antes** de cada llamada al modelo y de cada ejecución de herramienta costosa (`run_tests`, `search_docs`), y compara tres magnitudes acumuladas contra los tres límites que declara `SOLICITUD` (`02-modelo-entidades.md`): `limite_tiempo_segundos`, `limite_iteraciones` y `limite_costo_usd`. No existe un cuarto límite de tokens en bruto — los tokens son la unidad con la que se calcula el costo, no un límite independiente.
- Fórmula de costo: `costo = Σ (tokens_entrada × precio_entrada + tokens_salida × precio_salida)` de cada `LLAMADA_MODELO` (NFR-014), con una tabla de precios configurable por modelo (NFR-010); los valores viven en la configuración de despliegue, no en este documento. Ese costo acumulado es lo que se compara contra `limite_costo_usd`.
- Al superar cualquier límite, la llamada en curso se deja terminar (no se aborta a medio proceso) y la siguiente se bloquea; el resultado final es `PRESUPUESTO_AGOTADO` salvo que ya hubiera un resultado más específico en curso (p. ej. `COMPLETADO_PARCIALMENTE`).

**Prueba:** con un reloj y un contador de tokens inyectados, la ejecución corta exactamente en el límite configurado, con a lo sumo una llamada en vuelo por encima (NFR-009).

### 5. Aprobaciones

**Garantiza:** ningún cambio se aplica sin una decisión humana explícita, ligada al plan exacto.

- `apply_patch` exige `contexto.plan_aprobado is not None` y que el hash del parche referencie exactamente `plan_aprobado.hash`.
- Una `DECISION_APROBACION` solo es válida si su `plan_hash` coincide con el `hash` vigente del plan al momento de la decisión (UC-003, BR-001). Un plan modificado después de mostrarse invalida cualquier aprobación anterior.

**Prueba:** intentar `apply_patch` sin una decisión de aprobación persistida, o con una aprobación que referencia un hash de plan distinto al vigente; ambos se rechazan (NFR-003).

### 6. Manejo de secretos

**Garantiza:** los secretos nunca entran al contexto del modelo.

- El contenedor de ejecución no recibe **ninguna** variable de entorno de credenciales (NFR-004): se construye con una lista blanca de variables no sensibles (`PATH`, `PYTHONPATH`, `LANG`), nunca heredando el entorno del host.
- Toda salida de herramienta (`read_file`, `search_docs`, `run_tests`) pasa por un redactor de patrones **antes** de añadirse al contexto del modelo: claves de AWS (`AKIA[0-9A-Z]{16}`), tokens tipo *bearer*, cadenas de conexión con credenciales embebidas, bloques `-----BEGIN ... PRIVATE KEY-----`, y variables de entorno con nombres que contienen `SECRET`, `TOKEN`, `PASSWORD`, `KEY` seguidas de un valor.
- La redacción ocurre en el harness, no en el prompt: el modelo nunca ve el valor original, ni siquiera para "tener cuidado con él".

**Prueba (AC-04):** un secreto canario en una variable de entorno del host y en un archivo del repositorio no aparece en ninguna solicitud al modelo (verificado inspeccionando el registro de `LLAMADA_MODELO`), ninguna salida de herramienta persistida, ninguna fila de la base de datos, ni el reporte.

### 7. Validación del alcance

**Garantiza:** el diff completo se valida contra el plan aprobado antes de aplicarse, no archivo por archivo de forma aislada.

- El validador recibe el parche completo (formato diff unificado) y, antes de tocar disco: (a) verifica que cada ruta tocada esté en `rutas_declaradas` (control 3); (b) verifica que el tipo de operación (crear, modificar, borrar) esté entre las operaciones que el plan autoriza; (c) verifica que ningún archivo de pruebas existente se borre o se vacíe (protección específica contra "desactivar los tests", ver control 8).
- Una violación devuelve el **conjunto completo** de violaciones encontradas (no solo la primera), para que el modelo pueda corregir todas en un solo ciclo de reparación (patrón de la guía AWS, cap. 9, pág. 55: el verificador determinista certifica o devuelve el conjunto de conflictos).

**Prueba:** un parche con una violación de ruta y una de tipo de operación a la vez devuelve ambas en la respuesta de rechazo.

### 8. Confirmación de pruebas

**Garantiza:** el resultado de una verificación se toma de la salida real capturada, nunca de lo que el modelo afirme.

- `run_tests` devuelve al harness: código de salida del proceso, y stdout/stderr capturados. El harness parsea el reporte de pruebas (formato del *test runner* de la estrategia, p. ej. `pytest --tb=short` con recuento de `passed`/`failed`) de esa salida capturada, no de un resumen que el modelo genere.
- `resultado = EXITOSA` únicamente si `codigo_salida == 0` **y** `pruebas_exitosas == pruebas_totales` **y** `pruebas_totales >= linea_base_pruebas` (el conteo de pruebas no puede bajar respecto a la línea base tomada en el descubrimiento).
- Si el parche modifica un archivo de pruebas de forma que el conteo baja, o introduce marcas de `skip`/`xfail` nuevas sobre pruebas que antes corrían, el control 7 ya lo bloquea antes de llegar a ejecutar nada.
- El modelo puede **leer** el resultado persistido para diagnosticar (control de solo lectura), pero no puede **escribirlo**: no existe ninguna herramienta que permita al agente marcar una verificación como exitosa.

**Prueba (AC-08, escenario 3):** una verificación cuya salida capturada tiene `codigo_salida != 0` nunca aparece como `EXITOSA` en el reporte, sin importar lo que contenga cualquier mensaje generado por el modelo en el mismo turno.

---

## Redacción de secretos — decisión de alcance (pregunta abierta de `03-arquitectura.md`)

Se usa una **lista propia de patrones** (regex compiladas, listadas arriba en el control 6) en vez de una librería de detección de secretos de terceros (p. ej. `detect-secrets`, `trufflehog`).

**Razón:** para F1, la superficie a cubrir es acotada y conocida (salidas de `git`, `pip`, `pytest`, y contenido de archivos de un repositorio pequeño); una lista propia es auditable en una sola lectura del código — importa más poder decir con certeza qué patrones cubre el control 6 que maximizar recall genérico. Una librería de terceros queda anotada como mejora de F2 si el catálogo de fuentes crece.

## Eventos de seguridad — estructura común

Todo control que rechaza escribe un `EVENTO_SEGURIDAD` (`02-modelo-entidades.md`) en la **misma transacción** que la respuesta de rechazo (NFR-013):

```python
EventoSeguridad(
    ejecucion_id=...,
    regla="control_03_rutas_modificables",
    accion_intentada="apply_patch: modificar .github/workflows/ci.yml",
    origen="MODELO",              # MODELO | HERRAMIENTA | REPOSITORIO
    severidad="CRITICA",          # INFO | ADVERTENCIA | CRITICA
)
```

`origen` distingue si la acción bloqueada la propuso el modelo directamente, una herramienta al ejecutar algo el modelo pidió, o si se detectó en contenido leído del repositorio (p. ej. una instrucción incrustada en un `README`) — relevante para el escenario 4 y para `07-seguridad.md`.

## Matriz de trazabilidad

| Control | RN | AC | NFR |
|---|---|---|---|
| 1. Permisos | RN-03 | AC-05 | NFR-002 |
| 2. Comandos permitidos | RN-04 | AC-05 | NFR-005 |
| 3. Rutas modificables | RN-05 | AC-06 | — |
| 4. Presupuestos | RN-06 | — | NFR-009 |
| 5. Aprobaciones | RN-01 | — | NFR-003 |
| 6. Manejo de secretos | RN-07 | AC-04 | NFR-001 |
| 7. Validación del alcance | RN-05 | AC-06 | — |
| 8. Confirmación de pruebas | RN-08 | AC-08 | — |
