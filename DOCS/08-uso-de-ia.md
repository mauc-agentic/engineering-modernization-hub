# 08 — Uso de IA

| | |
|---|---|
| **Estado** | APROBADO el 2026-09-28 |
| **Depende de** | `03-arquitectura.md` §4 (grafo) · `05-politicas-y-controles.md` |

Esta es la frontera explícita entre lo que decide el modelo y lo que decide el código (RN-02). Es lo que separa este prototipo de un script de actualización, y el caso tiene un criterio de no aprobación exactamente para eso ("no utiliza IA de manera sustancial" / "es solamente un script de actualización").

---

## 1. Dónde decide el modelo (12 actividades)

Cada una está anclada a un nodo del grafo (`03-arquitectura.md` §4).

| # | Actividad (según el caso) | Nodo | Qué produce el modelo | Nivel de esfuerzo de razonamiento (ADR-002) |
|---|---|---|---|---|
| 1 | Interpretar la solicitud | `interpretar_solicitud` | Objetivo normalizado, ambigüedades detectadas | `low` |
| 2 | Explorar el repositorio | `descubrir_repo` | Qué archivos leer a continuación, dada la lista inicial y las señales de la estrategia | `low` |
| 3 | Determinar qué información necesita | `descubrir_repo` → `consultar_fuentes` | Qué buscar en las fuentes oficiales declaradas por la estrategia | `medium` |
| 4 | Consultar documentación | `consultar_fuentes` | Consultas a `search_docs`, síntesis de lo relevante de cada fuente | `medium` |
| 5 | Relacionar documentación con código | `analizar_impacto` | Mapeo entre lo que cambia (según la fuente) y dónde se usa (según el código) | `high` |
| 6 | Determinar viabilidad técnica | `evaluar_viabilidad` | Veredicto viable/inviable con su justificación | `high` |
| 7 | Construir el plan | `proponer_plan` | Pasos, rutas propuestas (dentro de la plantilla de la estrategia), riesgos | `high` |
| 8 | Generar cambios | `generar_cambios` | El parche propuesto | `high` |
| 9 | Generar pruebas | `generar_pruebas` | Pruebas nuevas o adaptadas | `medium` |
| 10 | Analizar errores | `analizar_error` | Diagnóstico de por qué falló una verificación | `high` |
| 11 | Proponer correcciones | `proponer_correccion` | Un parche de corrección, dentro del alcance ya aprobado | `high` |
| 12 | Preparar el reporte | `construir_reporte` (parte narrativa) | Resumen redactado, citando IDs de fuentes y decisiones | `low` |

## 2. Dónde decide el código (8 decisiones, nunca el modelo)

Corresponden exactamente a los ocho controles de `05-politicas-y-controles.md`.

| # | Decisión | Quién decide | Documento |
|---|---|---|---|
| 1 | Permisos: qué herramientas existen y qué argumentos son válidos | `emh/harness` + esquemas pydantic | `05` §1 |
| 2 | Comandos: qué comando concreto se ejecuta | `emh/policy` (*allowlist*) | `05` §2 |
| 3 | Rutas: qué archivos se pueden tocar | `emh/policy` contra `plan_aprobado` | `05` §3 |
| 4 | Presupuestos: cuándo se corta la ejecución | `PresupuestoMeter` (núcleo) | `05` §4 |
| 5 | Aprobaciones: si hay autorización para aplicar un cambio | `emh/policy` contra `DECISION_APROBACION` | `05` §5 |
| 6 | Secretos: qué se redacta antes de llegar al modelo | Redactor de patrones (harness) | `05` §6 |
| 7 | Validación del alcance: si un parche completo respeta el plan | `emh/policy` | `05` §7 |
| 8 | Si una prueba pasó | Parseo de salida real capturada | `05` §8 |

## 3. La regla en una frase

**El modelo propone (qué investigar, qué escribir, qué corregir); el código dispone (qué se permite, qué se ejecuta, qué se cuenta como verificado).** Ninguna de las 8 decisiones de la tabla anterior consulta al modelo en ningún punto del código; ninguna de las 12 actividades de la primera tabla tiene una implementación puramente determinista alternativa en F1 — si el modelo se reemplaza por una función que siempre devuelve vacío, el sistema no produce una modernización (AC-03), lo que demuestra que la IA participa de forma sustancial y no decorativa.

## 4. Por qué esta frontera, y no otra

- **Las 8 decisiones de código son exactamente las que, si fallaran, producen daño irreversible o no auditable:** modificar algo no autorizado, gastar sin límite, exponer un secreto, o mentir sobre si algo funciona. Son las mismas que el caso lista como "controles críticos" que "deberán ser determinísticos".
- **Las 12 actividades del modelo son exactamente las que requieren juicio sobre contenido no estructurado:** texto de documentación, código fuente, mensajes de error. No hay una regla determinista razonable para "¿este *breaking change* del *changelog* afecta a este uso del paquete en el código?" — eso es lo que el caso llama "carga cognitiva alta".
- La frontera se prueba, no se declara: AC-01 a AC-03 y las pruebas de `05-politicas-y-controles.md` la verifican mecánicamente, no solo en este documento.

## 5. Consumo de tokens por actividad — nota de costo (ligado a ADR-002)

Las actividades 5, 6, 7, 8, 10 y 11 (análisis de impacto, viabilidad, plan, cambios, análisis de error, corrección) son las que más se benefician de mayor esfuerzo de razonamiento y, por tanto, las que más tokens consumen. Las actividades 1, 2, 3, 9 y 12 se mantienen en `low`/`medium` para maximizar cuántas ejecuciones completas caben en el presupuesto (D-4 de `00-vision.md`). Este reparto se revisa si el ensayo de la demo muestra que alguna actividad necesita más presupuesto del previsto.
