# Política de seguridad

Este proyecto es un prototipo (caso de estudio Staff AI Platform Engineer) cuyo objetivo es
demostrar controles de seguridad deterministas alrededor de un agente de IA. Tomamos en serio
los reportes de seguridad.

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usa el reporte privado de GitHub:
<https://github.com/mauc-agentic/engineering-modernization-hub/security/advisories/new>

Incluye qué ocurre, cómo reproducirlo y el impacto que ves. Responderé con mejor esfuerzo en
unos días: es un proyecto mantenido por una sola persona, sin SLA.

## Qué se considera una vulnerabilidad

- Saltarse alguno de los **8 controles deterministas** (permisos, comandos, rutas, presupuesto,
  aprobación, secretos, alcance, confirmación de pruebas) — ver `DOCS/05-politicas-y-controles.md`.
- Que contenido no confiable (un repositorio, una fuente, la solicitud) logre que el agente
  ejecute una acción no aprobada, exponga secretos o marque como exitosa una prueba que no corrió.
- Escapar del sandbox de verificación, o leer/escribir fuera del workspace aprobado.
- Secretos o datos personales en el código, el historial o la infraestructura como código.
- Configuraciones inseguras en `infra/` (Terraform).

## Limitaciones conocidas (no son vulnerabilidades nuevas)

Están documentadas a propósito en `DOCS/ADR/ADR-006-despliegue-en-aws-con-terraform.md`:

- La API no tiene autenticación propia; la instancia desplegada la protege con autenticación
  HTTP básica en CloudFront y restringe el acceso directo por IP.
- El sandbox de nube conserva salida HTTPS (a diferencia de `network=none` en local), mitigada
  con rol IAM vacío y sin secretos en el entorno de los comandos.
- Sin alta disponibilidad (una tarea de la API, RDS de una sola zona).
- La identidad del aprobador es un campo declarado, no autenticado.

## Versiones soportadas

Solo la rama `main`.
