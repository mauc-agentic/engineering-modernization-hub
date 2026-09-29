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
| **URL** | [`https://github.com/mauc-agentic/ledger-service`](https://github.com/mauc-agentic/ledger-service) (privado) |
| **Commit de partida** | `844f287e5918c11dc28c02eb2dc2d9be749d9975` |
| **Modernización seleccionada** | Actualización de dependencia Python: `PyYAML` |
| **Versión actual → objetivo** | `5.3.1` → `6.0.2` |
| **Razón de la selección** | Es una modernización real y acotada (una sola dependencia, subconjunto claro de archivos afectados), con un *breaking change* documentado oficialmente (PyYAML 6.0 exige `Loader=` explícito en `yaml.load`) que rompe pruebas existentes en el primer intento sin necesidad de forzar nada artificialmente — cumple la condición del caso de que la modernización elegida rompa una prueba al primer intento. |

Contenido del fixture: un paquete `ledger/` con un libro contable mínimo en memoria (`ledger.py`), `config.py` y `fixtures.py` que cargan YAML con `yaml.load` sin `Loader=` (una llamada en cada uno), `requirements.txt` con `PyYAML==5.3.1`, y `tests/` con 7 pruebas.

**Verificado empíricamente el 2026-09-28** (no solo documentado): con `PyYAML==5.3.1`, las 7 pruebas pasan (con advertencia de obsolescencia). Con `PyYAML==6.0.2` sin corregir, **5 fallan y 2 pasan** (`TypeError: load() missing 1 required positional argument: 'Loader'` en `config.py:8` y `fixtures.py:8`). Con la corrección (`Loader=yaml.SafeLoader` en ambos archivos), las 7 vuelven a pasar bajo `6.0.2`.

## Repositorio 2 — `orders-api` (escenario 2)

| Campo | Valor |
|---|---|
| **URL** | [`https://github.com/mauc-agentic/orders-api`](https://github.com/mauc-agentic/orders-api) (privado) |
| **Commit de partida** | `5e60dabbd00074d9da88ae422a8d6d778733e9ec` |
| **Modernización seleccionada** | Actualización de dependencia Python: `Flask` |
| **Versión actual → objetivo** | `2.0.3` → `3.0.x` |
| **Razón de la selección** | Genera una inviabilidad real y verificable contra una fuente oficial (metadatos de PyPI: `Flask==3.0.0` exige `Requires-Python: >=3.8`) en conflicto con una restricción explícita y realista de la solicitud (runtime fijado a Python 3.7), sin necesitar ninguna simulación del veredicto. |

Contenido del fixture: una API mínima de pedidos sobre Flask (`orders_api/app.py`, crear/consultar pedidos), `requirements.txt` con `Flask==2.0.3` y `Werkzeug==2.0.3`, `runtime.txt` con `python-3.7.13`, y 2 pruebas que nunca llegan a ejecutarse en este escenario (la ejecución termina `BLOQUEADO` antes de tocar código, según UC-002 A1).

**Verificado empíricamente el 2026-09-28:** los metadatos reales del paquete `Flask==3.0.0` descargado de PyPI (`METADATA` dentro del `.whl`) declaran `Requires-Python: >=3.8`, confirmando el conflicto con `runtime.txt`. Las 2 pruebas del fixture pasan bajo Python 3.12 con las dependencias ancladas.

---

## Qué se muestra en vivo (90 minutos de sustentación, `C-011`)

1. Nivel A (los cuatro escenarios con `ScriptedModel`) — determinista, rápido, demuestra los controles. Corre en local (`EMH_ENV=local`), sin depender de la nube.
2. Nivel B, Ejemplo A (`ledger-service`) completo con Nova 2 Lite real — demuestra el flujo con el modelo real, incluida la corrección. Se ejecuta en local (Docker + SQLite) contra Bedrock real; el despliegue en AWS quedó como IaC validada con `terraform plan` (ADR-006/007), sin adaptadores de nube implementados.
3. Nivel B, Ejemplo B (`orders-api`) — si el tiempo alcanza; si no, se muestra grabado (parte de la evidencia operativa entregable, `00-vision.md` §5 AC-15).
4. Se muestra `terraform plan` (33 recursos) como evidencia de IaC. No se hizo `apply`, así que no hay recursos facturables que destruir.

## Cómo se reproduce (detalle exacto en el `README.md` del repositorio de implementación)

```bash
git clone <URL de engineering-modernization-hub>
cd engineering-modernization-hub
# ≤ 6 comandos totales, incluidos estos dos, para cumplir NFR-017
```

El `README.md` fija comandos exactos (instalación, variables de entorno para AWS/Bedrock, arranque de la API, ejecución de cada nivel de prueba) una vez exista el código; este documento no los duplica para no tener dos fuentes de verdad sobre cómo levantar el sistema.
