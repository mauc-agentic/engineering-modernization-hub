# 11 — Demostración

| | |
|---|---|
| **Estado** | APROBADO el 2026-09-28 |
| **Decisión** | D-8 de `00-vision.md`: dos repositorios propios, construidos a propósito, en vez de un fork ajeno. |

Ninguno de los dos repositorios lo entrega Wenia (C-013); ambos se crean como parte de este trabajo, con licencia propia, y se registran en GitHub como repositorios del autor antes de la sustentación.

---

## Repositorio 1 — `ledger-service` (escenarios 1 y 3)

| Campo | Valor |
|---|---|
| **URL** | `https://github.com/<owner-a-definir>/ledger-service` (se crea durante la implementación; placeholder hasta entonces) |
| **Commit de partida** | Se fija al terminar de escribir el fixture (primer commit del repositorio) |
| **Modernización seleccionada** | Actualización de dependencia Python: `PyYAML` |
| **Versión actual → objetivo** | `5.3.1` → `6.0.2` |
| **Razón de la selección** | Es una modernización real y acotada (una sola dependencia, subconjunto claro de archivos afectados), con un *breaking change* documentado oficialmente (PyYAML 6.0 exige `Loader=` explícito en `yaml.load`) que rompe una prueba existente en el primer intento sin necesidad de forzar nada artificialmente — cumple la condición del caso de que la modernización elegida rompa una prueba al primer intento. |

Contenido mínimo del fixture: un paquete `ledger/` con una API mínima de asientos contables en memoria, un `ledger/config.py` que carga configuración YAML con `yaml.load` sin `Loader=` (dos ocurrencias, en `config.py` y `fixtures.py`), `requirements.txt` con `PyYAML==5.3.1`, y `tests/test_config.py` con al menos las pruebas que hoy pasan sobre 5.3.1 y fallarían sobre 6.0.2 sin la corrección.

## Repositorio 2 — `orders-api` (escenario 2)

| Campo | Valor |
|---|---|
| **URL** | `https://github.com/<owner-a-definir>/orders-api` (se crea durante la implementación; placeholder hasta entonces) |
| **Commit de partida** | Se fija al terminar de escribir el fixture |
| **Modernización seleccionada** | Actualización de dependencia Python: `Flask` |
| **Versión actual → objetivo** | `2.0.3` → `3.0.x` |
| **Razón de la selección** | Genera una inviabilidad real y verificable contra una fuente oficial (metadatos de PyPI: `Flask==3.0.0` exige `Requires-Python: >=3.8`) en conflicto con una restricción explícita y realista de la solicitud (runtime fijado a Python 3.7), sin necesitar ninguna simulación del veredicto. |

Contenido mínimo del fixture: una API mínima de pedidos sobre Flask, `requirements.txt` con `Flask==2.0.3`, `runtime.txt` con `python-3.7.13`, y pruebas existentes que pasan sobre la versión actual (y que nunca llegan a ejecutarse en este escenario, porque la ejecución termina `BLOQUEADO` antes de tocar código, según UC-002 A1).

---

## Qué se muestra en vivo (90 minutos de sustentación, `C-011`)

1. Nivel A (los cuatro escenarios con `ScriptedModel`) — determinista, rápido, demuestra los controles. Corre en local (`EMH_ENV=local`), sin depender de la nube.
2. Nivel B, Ejemplo A (`ledger-service`) completo con Nova 2 Lite real — demuestra el flujo con el modelo real, incluida la corrección. Se ejecuta contra el despliegue en AWS (`EMH_ENV=aws`, `ADR-006`/`ADR-007`); si algo falla en el ensayo previo, cae al camino local sin cambiar de código, solo de configuración.
3. Nivel B, Ejemplo B (`orders-api`) — si el tiempo alcanza; si no, se muestra grabado (parte de la evidencia operativa entregable, `00-vision.md` §5 AC-15).
4. Al cerrar la sustentación: `terraform destroy` sobre `infra/`, dejando la cuenta de AWS sin recursos facturables (`ADR-006`).

## Cómo se reproduce (detalle exacto en el `README.md` del repositorio de implementación)

```bash
git clone <URL de engineering-modernization-hub>
cd engineering-modernization-hub
# ≤ 6 comandos totales, incluidos estos dos, para cumplir NFR-017
```

El `README.md` fija comandos exactos (instalación, variables de entorno para AWS/Bedrock, arranque de la API, ejecución de cada nivel de prueba) una vez exista el código; este documento no los duplica para no tener dos fuentes de verdad sobre cómo levantar el sistema.
