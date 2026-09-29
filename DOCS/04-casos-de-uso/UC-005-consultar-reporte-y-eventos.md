# Caso de uso: Consultar reporte y eventos

## Resumen

**ID del caso de uso:** UC-005
**Nombre:** Consultar reporte y eventos
**Actor principal:** Desarrollador
**Actores secundarios:** Equipo de seguridad
**Meta:** El desarrollador (o el equipo de seguridad) obtiene un reporte completo y auditable de una ejecución, con su resultado, sus cambios, sus verificaciones, sus fuentes y sus eventos de seguridad.
**Estado:** Done (implementado y probado; ver `DOCS/TRAZABILIDAD.md`)

## Precondiciones

- Existe una ejecución registrada, en cualquier estado.
- Quien consulta conoce el identificador de la ejecución o de la solicitud que la originó.

## Escenario de éxito principal

1. El desarrollador solicita el reporte de una ejecución por su identificador.
2. El sistema recupera el estado actual y, si la ejecución terminó, su resultado final.
3. El sistema ensambla los cambios generados, las verificaciones ejecutadas con su salida real, las fuentes consultadas y las decisiones que sustentan, y los eventos de seguridad registrados.
4. El sistema presenta el reporte completo al desarrollador, distinguiendo los hechos verificables de cualquier resumen narrativo.
5. El desarrollador revisa el reporte y confirma que refleja lo que autorizó.

## Flujos alternativos

### A1: La ejecución todavía no ha terminado

**Disparador:** el estado de la ejecución no es un estado final (paso 2).
**Flujo:**

1. El sistema presenta el estado actual y el avance disponible hasta el momento, sin un resultado final.
2. Use case ends.

### A2: El equipo de seguridad consulta solo los eventos

**Disparador:** quien consulta es el equipo de seguridad y pide únicamente los eventos de seguridad de la ejecución (paso 1).
**Flujo:**

1. El sistema presenta los eventos de seguridad registrados, con su regla, la acción intentada, el origen y el momento en que ocurrió cada uno.
2. Use case ends.

### A3: Una afirmación del reporte no tiene fuente que la sustente

**Disparador:** al ensamblar el reporte, una decisión no tiene ninguna fuente citada (paso 3).
**Flujo:**

1. El sistema marca esa afirmación como "sin sustento" en el reporte.
2. Use case continues at step 4.

### A4: El identificador consultado no existe

**Disparador:** el identificador de ejecución o de solicitud no corresponde a ningún registro (paso 1).
**Flujo:**

1. El sistema informa que no encontró la ejecución solicitada.
2. Use case ends.

## Postcondiciones

### Postcondiciones de éxito

- El desarrollador o el equipo de seguridad recibió un reporte cuyas afirmaciones son verificables contra lo persistido en el sistema.
- Ninguna verificación aparece en el reporte como exitosa sin su salida real capturada que la respalde.

### Postcondiciones de fallo

- Si el identificador no existe, no se generó ningún reporte y quien consultó recibió una indicación clara de que no se encontró.

## Reglas de negocio

### BR-001: El reporte separa hechos de narrativa

Los hechos del reporte (resultado, cambios, verificaciones, fuentes, eventos) provienen directamente de lo persistido; cualquier resumen redactado se marca como narrativa aparte.

### BR-002: Toda decisión citada requiere fuente

Una decisión que aparece en el reporte sin ninguna fuente asociada se marca explícitamente como "sin sustento"; nunca se presenta como si estuviera sustentada.

### BR-003: El reporte está disponible en cualquier estado de la ejecución

El desarrollador puede consultar el avance y los eventos de una ejecución aunque todavía no haya terminado, sin esperar a un resultado final.
