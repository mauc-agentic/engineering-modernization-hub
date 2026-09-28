# ADR-007 — Persistencia en la nube: RDS Postgres frente a DynamoDB y Aurora Serverless v2

**Estado:** Aceptado — 2026-09-28. Complementa ADR-004 (SQLite local) con el adaptador de nube de `RunRepository`.

## Contexto

Una tarea Fargate no tiene disco persistente compartido entre reinicios ni entre réplicas: SQLite (ADR-004) deja de ser viable en cuanto `emh-api` corre en la nube. Hace falta un almacén gestionado, alcanzable desde la VPC (`ADR-006`), y el usuario pidió explícitamente que la elección entre motores relacionales y no relacionales quedara justificada, no asumida.

## Decisión

**Amazon RDS para PostgreSQL, instancia `db.t4g.micro`, un solo AZ, sin réplica, `gp3` de 20 GB, sin protección de borrado.**

## Comparación

### 1. RDS Postgres frente a DynamoDB

| | RDS Postgres `db.t4g.micro` | DynamoDB (bajo demanda) |
|---|---|---|
| **Precio confirmado** (`us-east-1`, AWS Pricing API) | USD 0.016/hora, fijo, corra o no haya tráfico | USD 1.25 / millón de unidades de escritura, USD 0.25 / millón de lectura, USD 0.25/GB-mes de almacenamiento |
| **Costo real en esta demo** | ≈ USD 0.58 en 36 horas (ADR-006) | Del orden de centésimas de centavo para el volumen de esta demo (decenas de escrituras) |
| **Ajuste al modelo de datos** | Encaja de forma directa: `02-modelo-entidades.md` son 11 entidades relacionales con claves foráneas (`EJECUCION → PLAN → DECISION_APROBACION`, `DECISION_TECNICA ↔ CITA_FUENTE ↔ FUENTE`) y el reporte (UC-005) los combina con *joins* SQL directos. | Sin *joins* nativos: exige diseño de tabla única (*single-table design*) con claves de partición/ordenamiento e índices secundarios pensados por patrón de acceso — trabajo de modelado nuevo, no una migración mecánica del esquema ya aprobado. |
| **Riesgo de reescribir el modelo aprobado a un día del plazo** | Ninguno: es el mismo esquema de `02-modelo-entidades.md`, el mismo SQL que ya usa SQLite (ADR-004), solo cambia el adaptador de conexión. | Alto: los invariantes ya probados (p. ej. RN-12 — "sin sustento" cuando una decisión no tiene fuente citada) tendrían que reverificarse contra un modelo de acceso distinto, bajo el mismo plazo. |

**Veredicto:** en términos puramente de precio por operación, DynamoDB es más barato — pero la diferencia absoluta es de centavos, no de dólares, contra un presupuesto de USD 100. El criterio de FinOps que de verdad aplica aquí no es "elegir siempre lo más barato por unidad", es **no gastar horas de ingeniería reescribiendo un modelo de datos ya aprobado para ahorrar una fracción de dólar**. RDS gana porque el ahorro de DynamoDB es real pero irrelevante a esta escala, y su costo de adopción (rediseño, nueva superficie de prueba) no lo es.

### 2. RDS Postgres (instancia simple) frente a Aurora Serverless v2

| | RDS `db.t4g.micro` | Aurora Serverless v2 |
|---|---|---|
| **Capacidad mínima práctica** | Fija, 2 vCPU/1 GB compartidos (t4g), siempre disponible | 0.5 ACU mínimo típico (≈ USD 0.06–0.08/hora, ~4–5× más que `db.t4g.micro`) salvo que se configure escalado a 0 ACU |
| **Arranque en frío** | Ninguno: la instancia está arriba desde el primer `terraform apply` | Si se configura escalado a 0 ACU para ahorrar, reanudar desde 0 toma del orden de 15–30 segundos — inaceptable si ocurre durante la demo en vivo de 90 minutos frente al evaluador |
| **Complejidad en Terraform** | Un recurso (`aws_db_instance`) | Clúster + instancia + configuración de escalado (`aws_rds_cluster` + `aws_rds_cluster_instance` + `serverlessv2_scaling_configuration`) — más superficie que escribir, revisar y poder romper bajo el mismo plazo |
| **Cuándo tiene sentido** | Carga pequeña, predecible, de corta duración — exactamente este caso | Carga de producción con picos impredecibles y beneficio real de escalar automáticamente — no el perfil de una demo de un día |

**Veredicto:** Aurora Serverless v2 está diseñado para un problema (carga variable de producción) que esta demo no tiene. A esta escala es simultáneamente más caro en la práctica (mínimo de capacidad mayor que una instancia pequeña siempre activa) y más arriesgado (latencia de arranque en frío durante una demostración en vivo).

## Decisión final y por qué es también la opción FinOps correcta

`db.t4g.micro`, Single-AZ, sin réplica de lectura, sin *Multi-AZ* (que duplicaría el costo para una redundancia que un prototipo de un día no necesita), backups automáticos con retención mínima (1 día, no 7, para no acumular almacenamiento de *snapshots* que sobreviva al `terraform destroy` de la instancia), sin protección de borrado (para que `terraform destroy` limpie todo sin pasos manuales).

## Consecuencias

- `emh/persistence` implementa `PostgresRunRepository` sobre el mismo esquema de `02-modelo-entidades.md`, usando `psycopg` (driver directo, sin ORM, igual que la decisión de ADR-004 para SQLite: SQL parametrizado auditable línea por línea).
- La credencial de conexión se lee de SSM Parameter Store (`SecureString`), inyectada a la tarea Fargate como variable de entorno **en el momento del arranque**, no incrustada en la imagen ni en el estado de Terraform en texto plano (se usa `random_password` + `aws_ssm_parameter` con `type = "SecureString"`, nunca un valor fijo en el `.tf`).
- Recordatorio operativo explícito en `README.md`: `terraform destroy` incluye RDS; dejarla corriendo más allá de la sustentación es el único recurso de esta arquitectura con un costo por hora que vale la pena vigilar (los demás son de uso efímero o gratuitos).
