"""Adaptador SQLite de `RunRepository` (ADR-004). SQL parametrizado en cada
consulta, nunca interpolación de cadenas -- auditable línea por línea."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from emh.core.models import (
    CitaFuente,
    DecisionAprobacion,
    DecisionTecnica,
    Ejecucion,
    EventoSeguridad,
    Fuente,
    LlamadaModelo,
    Plan,
    Solicitud,
    Traza,
    Verificacion,
)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SqliteRunRepository:
    """Implementa `emh.core.ports.RunRepository`. Un archivo, modo WAL,
    claves foráneas activas (ADR-004)."""

    def __init__(self, db_path: str | Path = "emh.db") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- Solicitud -----------------------------------------------------

    def guardar_solicitud(self, solicitud: Solicitud) -> Solicitud:
        cur = self._conn.execute(
            """INSERT INTO solicitud
               (repositorio_url, commit_referencia, estrategia_id, objetivo,
                version_esperada, restricciones, limite_tiempo_segundos,
                limite_iteraciones, limite_costo_usd, solicitante, creado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                solicitud.repositorio_url, solicitud.commit_referencia,
                solicitud.estrategia_id, solicitud.objetivo,
                solicitud.version_esperada, solicitud.restricciones,
                solicitud.limite_tiempo_segundos, solicitud.limite_iteraciones,
                solicitud.limite_costo_usd, solicitud.solicitante,
                _dt(solicitud.creado_en),
            ),
        )
        self._conn.commit()
        return solicitud.model_copy(update={"id": cur.lastrowid})

    def obtener_solicitud(self, solicitud_id: int) -> Solicitud | None:
        row = self._conn.execute(
            "SELECT * FROM solicitud WHERE id = ?", (solicitud_id,)
        ).fetchone()
        if row is None:
            return None
        return Solicitud(
            id=row["id"], repositorio_url=row["repositorio_url"],
            commit_referencia=row["commit_referencia"], estrategia_id=row["estrategia_id"],
            objetivo=row["objetivo"], version_esperada=row["version_esperada"],
            restricciones=row["restricciones"],
            limite_tiempo_segundos=row["limite_tiempo_segundos"],
            limite_iteraciones=row["limite_iteraciones"],
            limite_costo_usd=row["limite_costo_usd"], solicitante=row["solicitante"],
            creado_en=_parse_dt(row["creado_en"]),
        )

    # -- Ejecucion -------------------------------------------------------

    def guardar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion:
        cur = self._conn.execute(
            """INSERT INTO ejecucion
               (solicitud_id, estado, resultado, motivo_bloqueo, tokens_consumidos,
                costo_estimado_usd, iteraciones_usadas, iniciado_en, finalizado_en)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                ejecucion.solicitud_id, ejecucion.estado.value,
                ejecucion.resultado.value if ejecucion.resultado else None,
                ejecucion.motivo_bloqueo.value if ejecucion.motivo_bloqueo else None,
                ejecucion.tokens_consumidos, ejecucion.costo_estimado_usd,
                ejecucion.iteraciones_usadas, _dt(ejecucion.iniciado_en),
                _dt(ejecucion.finalizado_en),
            ),
        )
        self._conn.commit()
        return ejecucion.model_copy(update={"id": cur.lastrowid})

    def actualizar_ejecucion(self, ejecucion: Ejecucion) -> Ejecucion:
        self._conn.execute(
            """UPDATE ejecucion SET estado=?, resultado=?, motivo_bloqueo=?,
               tokens_consumidos=?, costo_estimado_usd=?, iteraciones_usadas=?,
               finalizado_en=? WHERE id=?""",
            (
                ejecucion.estado.value,
                ejecucion.resultado.value if ejecucion.resultado else None,
                ejecucion.motivo_bloqueo.value if ejecucion.motivo_bloqueo else None,
                ejecucion.tokens_consumidos, ejecucion.costo_estimado_usd,
                ejecucion.iteraciones_usadas, _dt(ejecucion.finalizado_en),
                ejecucion.id,
            ),
        )
        self._conn.commit()
        return ejecucion

    def obtener_ejecucion(self, ejecucion_id: int) -> Ejecucion | None:
        row = self._conn.execute(
            "SELECT * FROM ejecucion WHERE id = ?", (ejecucion_id,)
        ).fetchone()
        if row is None:
            return None
        return Ejecucion(
            id=row["id"], solicitud_id=row["solicitud_id"], estado=row["estado"],
            resultado=row["resultado"], motivo_bloqueo=row["motivo_bloqueo"],
            tokens_consumidos=row["tokens_consumidos"],
            costo_estimado_usd=row["costo_estimado_usd"],
            iteraciones_usadas=row["iteraciones_usadas"],
            iniciado_en=_parse_dt(row["iniciado_en"]),
            finalizado_en=_parse_dt(row["finalizado_en"]),
        )

    # -- Plan --------------------------------------------------------------

    def guardar_plan(self, plan: Plan) -> Plan:
        cur = self._conn.execute(
            """INSERT INTO plan (ejecucion_id, version, hash, pasos, rutas_declaradas,
               comandos_verificacion, riesgos, estado, creado_en)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                plan.ejecucion_id, plan.version, plan.hash,
                json.dumps(plan.pasos), json.dumps(plan.rutas_declaradas),
                json.dumps(plan.comandos_verificacion), plan.riesgos,
                plan.estado.value, _dt(plan.creado_en),
            ),
        )
        self._conn.commit()
        return plan.model_copy(update={"id": cur.lastrowid})

    def _fila_a_plan(self, row: sqlite3.Row) -> Plan:
        return Plan(
            id=row["id"], ejecucion_id=row["ejecucion_id"], version=row["version"],
            hash=row["hash"], pasos=json.loads(row["pasos"]),
            rutas_declaradas=json.loads(row["rutas_declaradas"]),
            comandos_verificacion=json.loads(row["comandos_verificacion"]),
            riesgos=row["riesgos"], estado=row["estado"],
            creado_en=_parse_dt(row["creado_en"]),
        )

    def actualizar_estado_plan(self, plan_id: int, estado: str) -> None:
        self._conn.execute("UPDATE plan SET estado = ? WHERE id = ?", (estado, plan_id))
        self._conn.commit()

    def obtener_plan_vigente(self, ejecucion_id: int) -> Plan | None:
        row = self._conn.execute(
            """SELECT * FROM plan WHERE ejecucion_id = ? AND estado != 'SUPERSEDIDO'
               ORDER BY version DESC LIMIT 1""",
            (ejecucion_id,),
        ).fetchone()
        return self._fila_a_plan(row) if row else None

    def listar_planes(self, ejecucion_id: int) -> list[Plan]:
        rows = self._conn.execute(
            "SELECT * FROM plan WHERE ejecucion_id = ? ORDER BY version", (ejecucion_id,)
        ).fetchall()
        return [self._fila_a_plan(r) for r in rows]

    # -- DecisionAprobacion --------------------------------------------------

    def guardar_decision_aprobacion(self, decision: DecisionAprobacion) -> DecisionAprobacion:
        cur = self._conn.execute(
            """INSERT INTO decision_aprobacion
               (plan_id, plan_hash, decision, aprobador, comentario, decidido_en)
               VALUES (?,?,?,?,?,?)""",
            (
                decision.plan_id, decision.plan_hash, decision.decision.value,
                decision.aprobador, decision.comentario, _dt(decision.decidido_en),
            ),
        )
        self._conn.commit()
        return decision.model_copy(update={"id": cur.lastrowid})

    def obtener_decision_aprobacion_vigente(self, plan_id: int) -> DecisionAprobacion | None:
        row = self._conn.execute(
            "SELECT * FROM decision_aprobacion WHERE plan_id = ? ORDER BY id DESC LIMIT 1",
            (plan_id,),
        ).fetchone()
        if row is None:
            return None
        return DecisionAprobacion(
            id=row["id"], plan_id=row["plan_id"], plan_hash=row["plan_hash"],
            decision=row["decision"], aprobador=row["aprobador"], comentario=row["comentario"],
            decidido_en=_parse_dt(row["decidido_en"]),
        )

    # -- DecisionTecnica -----------------------------------------------------

    def guardar_decision_tecnica(self, decision: DecisionTecnica) -> DecisionTecnica:
        cur = self._conn.execute(
            """INSERT INTO decision_tecnica (ejecucion_id, tipo, descripcion, sustentada, creado_en)
               VALUES (?,?,?,?,?)""",
            (
                decision.ejecucion_id, decision.tipo.value, decision.descripcion,
                int(decision.sustentada), _dt(decision.creado_en),
            ),
        )
        self._conn.commit()
        return decision.model_copy(update={"id": cur.lastrowid})

    def listar_decisiones_tecnicas(self, ejecucion_id: int) -> list[DecisionTecnica]:
        rows = self._conn.execute(
            "SELECT * FROM decision_tecnica WHERE ejecucion_id = ? ORDER BY id",
            (ejecucion_id,),
        ).fetchall()
        return [
            DecisionTecnica(
                id=r["id"], ejecucion_id=r["ejecucion_id"], tipo=r["tipo"],
                descripcion=r["descripcion"], sustentada=bool(r["sustentada"]),
                creado_en=_parse_dt(r["creado_en"]),
            )
            for r in rows
        ]

    # -- Fuente / CitaFuente --------------------------------------------------

    def guardar_fuente(self, fuente: Fuente) -> Fuente:
        cur = self._conn.execute(
            """INSERT INTO fuente (ejecucion_id, tipo, url, hash_contenido, resumen, consultada_en)
               VALUES (?,?,?,?,?,?)""",
            (
                fuente.ejecucion_id, fuente.tipo.value, fuente.url,
                fuente.hash_contenido, fuente.resumen, _dt(fuente.consultada_en),
            ),
        )
        self._conn.commit()
        return fuente.model_copy(update={"id": cur.lastrowid})

    def listar_fuentes(self, ejecucion_id: int) -> list[Fuente]:
        rows = self._conn.execute(
            "SELECT * FROM fuente WHERE ejecucion_id = ? ORDER BY id", (ejecucion_id,)
        ).fetchall()
        return [
            Fuente(
                id=r["id"], ejecucion_id=r["ejecucion_id"], tipo=r["tipo"], url=r["url"],
                hash_contenido=r["hash_contenido"], resumen=r["resumen"],
                consultada_en=_parse_dt(r["consultada_en"]),
            )
            for r in rows
        ]

    def guardar_cita_fuente(self, cita: CitaFuente) -> CitaFuente:
        cur = self._conn.execute(
            "INSERT INTO cita_fuente (decision_tecnica_id, fuente_id, extracto) VALUES (?,?,?)",
            (cita.decision_tecnica_id, cita.fuente_id, cita.extracto),
        )
        self._conn.commit()
        return cita.model_copy(update={"id": cur.lastrowid})

    def listar_citas(self, decision_tecnica_id: int) -> list[CitaFuente]:
        rows = self._conn.execute(
            "SELECT * FROM cita_fuente WHERE decision_tecnica_id = ?",
            (decision_tecnica_id,),
        ).fetchall()
        return [
            CitaFuente(
                id=r["id"], decision_tecnica_id=r["decision_tecnica_id"],
                fuente_id=r["fuente_id"], extracto=r["extracto"],
            )
            for r in rows
        ]

    # -- Verificacion --------------------------------------------------------

    def guardar_verificacion(self, verificacion: Verificacion) -> Verificacion:
        cur = self._conn.execute(
            """INSERT INTO verificacion (ejecucion_id, comando, codigo_salida,
               salida_capturada, pruebas_totales, pruebas_exitosas, resultado, ejecutado_en)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                verificacion.ejecucion_id, verificacion.comando, verificacion.codigo_salida,
                verificacion.salida_capturada, verificacion.pruebas_totales,
                verificacion.pruebas_exitosas, verificacion.resultado.value,
                _dt(verificacion.ejecutado_en),
            ),
        )
        self._conn.commit()
        return verificacion.model_copy(update={"id": cur.lastrowid})

    def listar_verificaciones(self, ejecucion_id: int) -> list[Verificacion]:
        rows = self._conn.execute(
            "SELECT * FROM verificacion WHERE ejecucion_id = ? ORDER BY id",
            (ejecucion_id,),
        ).fetchall()
        return [
            Verificacion(
                id=r["id"], ejecucion_id=r["ejecucion_id"], comando=r["comando"],
                codigo_salida=r["codigo_salida"], salida_capturada=r["salida_capturada"],
                pruebas_totales=r["pruebas_totales"], pruebas_exitosas=r["pruebas_exitosas"],
                resultado=r["resultado"], ejecutado_en=_parse_dt(r["ejecutado_en"]),
            )
            for r in rows
        ]

    # -- EventoSeguridad -------------------------------------------------------

    def guardar_evento_seguridad(self, evento: EventoSeguridad) -> EventoSeguridad:
        cur = self._conn.execute(
            """INSERT INTO evento_seguridad (ejecucion_id, regla, accion_intentada,
               origen, severidad, registrado_en) VALUES (?,?,?,?,?,?)""",
            (
                evento.ejecucion_id, evento.regla, evento.accion_intentada,
                evento.origen.value, evento.severidad.value, _dt(evento.registrado_en),
            ),
        )
        self._conn.commit()
        return evento.model_copy(update={"id": cur.lastrowid})

    def listar_eventos_seguridad(self, ejecucion_id: int) -> list[EventoSeguridad]:
        rows = self._conn.execute(
            "SELECT * FROM evento_seguridad WHERE ejecucion_id = ? ORDER BY id",
            (ejecucion_id,),
        ).fetchall()
        return [
            EventoSeguridad(
                id=r["id"], ejecucion_id=r["ejecucion_id"], regla=r["regla"],
                accion_intentada=r["accion_intentada"], origen=r["origen"],
                severidad=r["severidad"], registrado_en=_parse_dt(r["registrado_en"]),
            )
            for r in rows
        ]

    # -- LlamadaModelo -------------------------------------------------------

    def guardar_llamada_modelo(self, llamada: LlamadaModelo) -> LlamadaModelo:
        cur = self._conn.execute(
            """INSERT INTO llamada_modelo (ejecucion_id, nodo, tokens_entrada,
               tokens_salida, duracion_ms, creado_en) VALUES (?,?,?,?,?,?)""",
            (
                llamada.ejecucion_id, llamada.nodo, llamada.tokens_entrada,
                llamada.tokens_salida, llamada.duracion_ms, _dt(llamada.creado_en),
            ),
        )
        self._conn.commit()
        return llamada.model_copy(update={"id": cur.lastrowid})

    def listar_llamadas_modelo(self, ejecucion_id: int) -> list[LlamadaModelo]:
        rows = self._conn.execute(
            "SELECT * FROM llamada_modelo WHERE ejecucion_id = ? ORDER BY id",
            (ejecucion_id,),
        ).fetchall()
        return [
            LlamadaModelo(
                id=r["id"], ejecucion_id=r["ejecucion_id"], nodo=r["nodo"],
                tokens_entrada=r["tokens_entrada"], tokens_salida=r["tokens_salida"],
                duracion_ms=r["duracion_ms"], creado_en=_parse_dt(r["creado_en"]),
            )
            for r in rows
        ]

    # -- Traza (observabilidad) --------------------------------------------------

    def guardar_traza(self, traza: Traza) -> Traza:
        cur = self._conn.execute(
            """INSERT INTO traza (ejecucion_id, tipo, nombre, inicio, duracion_ms, ok,
               tokens_entrada, tokens_salida, detalle) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                traza.ejecucion_id, traza.tipo, traza.nombre, _dt(traza.inicio),
                traza.duracion_ms, int(traza.ok), traza.tokens_entrada, traza.tokens_salida, traza.detalle,
            ),
        )
        self._conn.commit()
        return traza.model_copy(update={"id": cur.lastrowid})

    def listar_trazas(self, ejecucion_id: int) -> list[Traza]:
        rows = self._conn.execute(
            "SELECT * FROM traza WHERE ejecucion_id = ? ORDER BY inicio, id", (ejecucion_id,)
        ).fetchall()
        return [
            Traza(
                id=r["id"], ejecucion_id=r["ejecucion_id"], tipo=r["tipo"], nombre=r["nombre"],
                inicio=_parse_dt(r["inicio"]), duracion_ms=r["duracion_ms"], ok=bool(r["ok"]),
                tokens_entrada=r["tokens_entrada"], tokens_salida=r["tokens_salida"], detalle=r["detalle"],
            )
            for r in rows
        ]

    # -- AnalisisViabilidad (no forma parte del puerto RunRepository mínimo,
    # pero se guarda con el mismo patrón; usado por el nodo evaluar_viabilidad) --

    def guardar_analisis_viabilidad(self, analisis) -> None:
        from emh.core.models import AnalisisViabilidad  # evita import circular arriba

        assert isinstance(analisis, AnalisisViabilidad)
        cur = self._conn.execute(
            """INSERT INTO analisis_viabilidad (ejecucion_id, veredicto,
               impacto_detectado, evidencia, creado_en) VALUES (?,?,?,?,?)""",
            (
                analisis.ejecucion_id, analisis.veredicto.value,
                analisis.impacto_detectado, analisis.evidencia, _dt(analisis.creado_en),
            ),
        )
        self._conn.commit()
        return analisis.model_copy(update={"id": cur.lastrowid})

    def obtener_analisis_viabilidad(self, ejecucion_id: int):
        from emh.core.models import AnalisisViabilidad

        row = self._conn.execute(
            "SELECT * FROM analisis_viabilidad WHERE ejecucion_id = ? ORDER BY id DESC LIMIT 1",
            (ejecucion_id,),
        ).fetchone()
        if row is None:
            return None
        return AnalisisViabilidad(
            id=row["id"], ejecucion_id=row["ejecucion_id"], veredicto=row["veredicto"],
            impacto_detectado=row["impacto_detectado"], evidencia=row["evidencia"],
            creado_en=_parse_dt(row["creado_en"]),
        )
