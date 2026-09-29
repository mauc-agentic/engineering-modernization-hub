# Caso de uso: Revisar y aprobar el plan

## Resumen

**ID del caso de uso:** UC-003
**Nombre:** Revisar y aprobar el plan
**Actor principal:** Desarrollador
**Meta:** El desarrollador decide, con toda la información del análisis y el plan a la vista, si autoriza a la plataforma a modificar su repositorio.
**Estado:** Done (implementado y probado; ver `DOCS/TRAZABILIDAD.md`)

## Precondiciones

- Existe un plan propuesto, con su alcance declarado y su hash (UC-002).
- La ejecución está en espera de una decisión de aprobación.

## Escenario de éxito principal

1. El desarrollador consulta el análisis de viabilidad, sus fuentes y el plan propuesto, incluidas las rutas que se modificarían y los comandos de verificación.
2. El desarrollador decide aprobar el plan.
3. El sistema liga la decisión de aprobación al hash exacto del plan revisado.
4. El sistema registra la decisión de forma persistente.
5. El sistema habilita el paso a la generación de cambios (UC-004) sobre ese plan y ningún otro.

## Flujos alternativos

### A1: El desarrollador rechaza el plan

**Disparador:** el desarrollador decide no autorizar el plan (paso 2).
**Flujo:**

1. El sistema registra la decisión de rechazo, ligada al hash del plan revisado.
2. El sistema deja la ejecución con el resultado correspondiente a un plan rechazado; no se genera ningún cambio.
3. Use case ends.

### A2: El plan cambió entre la consulta y la decisión

**Disparador:** el hash del plan vigente al momento de decidir no coincide con el hash que el desarrollador revisó (paso 3).
**Flujo:**

1. El sistema rechaza la decisión por no corresponder al plan vigente.
2. El sistema pide al desarrollador que revise el plan actualizado antes de decidir de nuevo.
3. Use case continues at step 1.

### A3: El desarrollador pide un cambio de alcance

**Disparador:** el desarrollador considera que el plan necesita un alcance distinto antes de decidir (paso 2).
**Flujo:**

1. El sistema deja constancia de la observación del desarrollador.
2. La plataforma construye una nueva versión del plan con un hash propio (retoma UC-002, paso 5).
3. Use case continues at step 1.

## Postcondiciones

### Postcondiciones de éxito

- Existe una decisión de aprobación persistida, ligada de forma inequívoca al plan que autoriza.
- La ejecución puede avanzar a generar cambios únicamente dentro del alcance de ese plan.

### Postcondiciones de fallo

- Si el plan fue rechazado, la ejecución queda con su resultado correspondiente y el repositorio no se modifica.
- Ningún cambio se aplica sobre un plan que no tiene una decisión de aprobación vigente.

## Reglas de negocio

### BR-001: Aprobación ligada al plan exacto

Una decisión de aprobación solo es válida para el plan cuyo hash coincide exactamente con el que se decidió; un plan modificado después requiere una nueva decisión.

### BR-002: Un plan aprobado es inmutable

Una vez aprobado, el contenido del plan no se modifica; cualquier cambio de alcance exige una versión de plan nueva y una aprobación nueva.

### BR-003: Sin aprobación no hay cambios

Ningún cambio de código se genera ni se aplica mientras no exista una decisión de aprobación vigente ligada al plan.
