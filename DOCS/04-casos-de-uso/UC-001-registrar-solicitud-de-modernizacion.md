# Caso de uso: Registrar solicitud de modernización

## Resumen

**ID del caso de uso:** UC-001
**Nombre:** Registrar solicitud de modernización
**Actor principal:** Desarrollador
**Meta:** El desarrollador deja registrada una solicitud completa y válida, y recibe un identificador para seguirla, sin coordinar con un equipo de plataforma.
**Estado:** Aprobado

## Precondiciones

- El desarrollador tiene acceso a la API del Hub.
- El repositorio indicado es accesible por HTTPS (privado propio o fork público con licencia open source).
- Existe una estrategia de modernización registrada que cubre el objetivo declarado.

## Escenario de éxito principal

1. El desarrollador envía una solicitud con repositorio, referencia de partida, objetivo de modernización, versión o estado esperado, restricciones, y límites de tiempo, iteraciones y costo.
2. El sistema valida que la solicitud tiene todos los campos requeridos y que los límites son valores positivos dentro de los rangos permitidos.
3. El sistema identifica la estrategia de modernización que cubre el objetivo declarado.
4. El sistema registra la solicitud y crea una ejecución en estado inicial.
5. El sistema devuelve al desarrollador el identificador de la ejecución y su estado.

## Flujos alternativos

### A1: Campos faltantes o límites inválidos

**Disparador:** la solicitud no trae un campo requerido o un límite está fuera de rango (paso 2).
**Flujo:**

1. El sistema rechaza la solicitud y devuelve el motivo del rechazo, campo por campo.
2. Use case ends.

### A2: Ninguna estrategia cubre el objetivo

**Disparador:** ninguna estrategia registrada declara soporte para el objetivo declarado (paso 3).
**Flujo:**

1. El sistema rechaza la solicitud e informa que el objetivo no está soportado.
2. Use case ends.

### A3: El repositorio no es accesible

**Disparador:** el sistema intenta verificar la accesibilidad del repositorio declarado y no lo logra (paso 4).
**Flujo:**

1. El sistema registra la solicitud como rechazada, con el motivo de la falla de acceso.
2. Use case ends.

## Postcondiciones

### Postcondiciones de éxito

- La solicitud queda registrada de forma persistente.
- Existe una ejecución asociada a la solicitud, en su estado inicial, lista para que la plataforma continúe con el descubrimiento (UC-002).
- El desarrollador tiene un identificador con el que puede consultar el estado en cualquier momento.

### Postcondiciones de fallo

- Ninguna solicitud ni ejecución queda registrada.
- El desarrollador recibe un motivo específico y accionable del rechazo.

## Reglas de negocio

### BR-001: Validación antes de persistir

Ninguna solicitud se registra sin que sus campos obligatorios y sus límites hayan sido validados primero.

### BR-002: Objetivo sin estrategia soportada

Una solicitud cuyo objetivo no cubre ninguna estrategia registrada no genera una ejecución.

### BR-003: Límites obligatorios y positivos

Toda solicitud declara límites de tiempo, iteraciones y costo; ninguno puede ser cero, negativo o estar ausente.
