# Caso de uso: Descubrir y analizar viabilidad

## Resumen

**ID del caso de uso:** UC-002
**Nombre:** Descubrir y analizar viabilidad
**Actor principal:** Plataforma
**Meta:** La plataforma determina, con evidencia trazable, si la modernización solicitada es viable y, si lo es, construye un plan de cambios con su alcance.
**Estado:** Aprobado

## Precondiciones

- Existe una ejecución registrada en su estado inicial (UC-001).
- El repositorio es accesible y la estrategia identificada está disponible.
- El presupuesto de la ejecución (tiempo, iteraciones, costo) no está agotado.

## Escenario de éxito principal

1. La plataforma clona el repositorio en un entorno aislado y explora su estructura, manifiestos y pruebas existentes.
2. La plataforma consulta las fuentes oficiales que la estrategia declara como válidas (documentación, release notes, guías de migración, registros de paquetes, avisos de seguridad) y registra cada fuente consultada.
3. La plataforma relaciona lo encontrado en las fuentes con el código del repositorio para identificar el impacto del cambio.
4. La plataforma determina la viabilidad técnica de la modernización y registra el veredicto con su evidencia.
5. La plataforma construye un plan con los pasos propuestos, las rutas que se modificarían y los comandos de verificación, y lo deja listo para revisión del desarrollador.

## Flujos alternativos

### A1: Modernización inviable

**Disparador:** el veredicto de viabilidad es negativo (paso 4).
**Flujo:**

1. La plataforma registra el veredicto de inviabilidad junto con la evidencia que lo sustenta.
2. La plataforma notifica al desarrollador la inviabilidad, sin generar ningún plan ni tocar el repositorio.
3. Use case ends.

### A2: Se agota el presupuesto durante el análisis

**Disparador:** el tiempo, los tokens o las iteraciones asignados se agotan antes de terminar el análisis (cualquier paso).
**Flujo:**

1. La plataforma detiene el análisis y registra lo investigado hasta ese momento.
2. La plataforma notifica al desarrollador que el presupuesto se agotó durante el análisis.
3. Use case ends.

### A3: Ninguna fuente oficial responde

**Disparador:** las fuentes declaradas por la estrategia no están disponibles o no devuelven información utilizable (paso 2).
**Flujo:**

1. La plataforma registra el intento de consulta y su resultado.
2. La plataforma continúa el análisis con la información disponible en el repositorio.
3. Use case continues at step 3.

## Postcondiciones

### Postcondiciones de éxito

- Existe un veredicto de viabilidad con su evidencia, persistido y consultable.
- Cada fuente consultada queda registrada con su identificador y el momento de la consulta.
- Existe un plan con alcance declarado, pendiente de aprobación (listo para UC-003).

### Postcondiciones de fallo

- Si la modernización es inviable, no se generó ningún plan y el repositorio no fue modificado.
- Si el presupuesto se agotó, la ejecución queda con el resultado correspondiente y con evidencia de lo investigado hasta el corte.

## Reglas de negocio

### BR-001: El repositorio original no se toca en esta etapa

El descubrimiento y el análisis solo leen el repositorio; ningún archivo se modifica antes de que exista un plan aprobado.

### BR-002: Toda decisión de viabilidad cita su evidencia

El veredicto de viabilidad siempre está acompañado de al menos una fuente o hallazgo del repositorio que lo sustenta.

### BR-003: El plan declara su propio alcance

El plan que resulta de este caso de uso enumera explícitamente las rutas modificables y los comandos de verificación que usará; nada fuera de esa declaración se considera parte del plan.
