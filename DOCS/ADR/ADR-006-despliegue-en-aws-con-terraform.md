# ADR-006 — Despliegue en AWS con Terraform (cómputo y red)

**Estado:** Aceptado — 2026-09-28. Promueve FR-038 de diseño de F2 a **implementado en F1** (decisión D-9 de `00-vision.md`).

## Contexto

El caso marca el despliegue en la nube con Terraform como un plus ("Si la solución se despliega en la nube, es un plus, entregar la infraestructura como código en Terraform"). El autor decide tomar ese plus: hay USD 100 de crédito en la cuenta de AWS para "montar todo", con una condición explícita — **disciplina de costo (FinOps) en cada decisión, con su justificación**, no gasto por conveniencia.

Esto se suma, no reemplaza, al diseño local ya aprobado (ADR-004 SQLite, ADR-005 Docker efímero): `RunRepository` y `Sandbox` ya son puertos (`03-arquitectura.md` §2), así que un despliegue en la nube es un **adaptador nuevo**, seleccionable por configuración (`EMH_ENV=local|aws`), no una reescritura. Esto es lo que hace seguro aceptar el despliegue completo bajo un plazo de un día: si algo falla en el ensayo de la nube, el camino local sigue disponible para la sustentación en vivo (C-011).

## Decisión

**Amazon ECS en Fargate**, un solo clúster, dos definiciones de tarea, sin balanceador de carga, sin NAT Gateway. Terraform con el *provider* oficial `hashicorp/aws` (última versión estable: **6.66.0**, fijada con `~> 6.66` en `versions.tf`).

```
┌─────────────────────────────────────────────────────────────┐
│  VPC (1 subred pública — sin NAT Gateway)                     │
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────────────┐   │
│  │ emh-api           │  RunTask │ emh-sandbox               │   │
│  │ Servicio ECS       │────────▶│ Tarea efímera (sin        │   │
│  │ Fargate, 1 réplica │  crea/  │ servicio persistente),    │   │
│  │ 0.25 vCPU / 0.5 GB │  destruye│ 0.5 vCPU / 1 GB,          │   │
│  │ IP pública directa │         │ una por ejecución,        │   │
│  │                    │         │ sin rol IAM (sin AWS API) │   │
│  └─────────┬──────────┘         └────────────────────────────┘  │
│            │ Secrets Manager → no; SSM Parameter Store (gratis) │
│            ▼                                                     │
│  ┌──────────────────┐                                           │
│  │ RDS PostgreSQL     │  (ADR-007)                               │
│  │ db.t4g.micro        │                                          │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ (fuera de la VPC, gestionado por AWS)
   Amazon Bedrock — Nova 2 Lite (ADR-002)
```

## Alternativas descartadas (con justificación de costo)

| Alternativa | Costo estimado | Por qué no |
|---|---|---|
| **AWS App Runner** para la API | vCPU-hora USD 0.064 + GB-hora USD 0.007 (confirmado vía AWS Pricing API, `us-east-1`) — **más caro por hora** que Fargate (0.25 vCPU/0.5 GB: USD 0.0195/h en App Runner vs. USD 0.0123/h en Fargate) y, sobre todo, introduce un *segundo* modelo de cómputo distinto del que de todas formas se necesita para la tarea efímera del sandbox (Fargate). Mantener un solo modelo de cómputo (ECS/Fargate) reduce el Terraform a escribir, a probar y a poder olvidar destruir — el verdadero costo bajo un plazo de un día no es el céntimo por hora, es el tiempo de ingeniería. |
| **Application Load Balancer** delante de la API | ALB: cargo fijo por hora (del orden de USD 0.0225/h) + LCU, **corriendo aunque nadie llame a la API** — el patrón de costo exactamente opuesto al de un recurso que se usa unas horas y se destruye. Se descarta: la tarea Fargate de la API recibe una IP pública directa (`assignPublicIp=ENABLED` en una subred pública), suficiente para un solo servicio, sin alta disponibilidad, durante una demo. |
| **NAT Gateway** para que las tareas privadas salgan a internet | ~USD 0.045/h + cargo por GB procesado — el clásico costo "olvidado" de una cuenta de AWS. Se evita por completo: tanto `emh-api` como `emh-sandbox` corren en la **subred pública** con IP pública propia, sin necesidad de NAT. La tarea del sandbox no recibe tráfico entrante (grupo de seguridad sin reglas de entrada), solo sale a PyPI/GitHub para el *wheelhouse* (ADR-005) y a Bedrock. |
| **EKS** (Kubernetes gestionado) | Cargo fijo del plano de control (~USD 0.10/h, ~USD 73/mes) además del cómputo — sin ningún beneficio para dos tareas simples. Nunca estuvo en consideración seria: es una complejidad y un costo fijo que no se recupera en un prototipo de un día. |
| **Secrets Manager** para la contraseña de RDS | USD 0.40/secreto/mes + USD 0.05 por 10 000 llamadas. Se usa en su lugar **SSM Parameter Store, parámetro `SecureString` estándar (sin costo)**: no se necesita rotación automática para un recurso que vive un par de días y se destruye. |

## Evaluación

| Dimensión | Evaluación |
|---|---|
| **Seguridad** | Sin balanceador público innecesario, superficie mínima (dos grupos de seguridad, reglas explícitas); rol IAM del sandbox vacío (sin permisos de AWS, refuerza NFR-004 también a nivel de nube, no solo de variables de entorno); credenciales de base de datos en SSM `SecureString`, nunca en variables de entorno de la tarea. |
| **Portabilidad** | El despliegue en la nube es un adaptador (`FargateSandbox`, `RdsRunRepository`) sobre los mismos puertos que ya usa el driver local; ninguno de los dos toca `emh/core` (NFR-016 se demuestra en producción, no solo en el diseño). |
| **Costo** | Ver estimación completa abajo: costo total proyectado del ejercicio completo ≈ USD 6–7 de los USD 100 disponibles, con NAT Gateway y ALB eliminados como las dos fuentes de costo "olvidado" más comunes en cuentas de AWS. |
| **Operación** | Fargate no exige parchear ni administrar instancias EC2; `terraform destroy` al terminar la sustentación deja la cuenta en cero (salvo ECR, con costo de centavos si se deja). |
| **Escalabilidad** | Un clúster ECS con dos definiciones de tarea escala trivialmente a más réplicas de `emh-api` o a ejecutar varias tareas `emh-sandbox` en paralelo (NFR-020, 2 ejecuciones concurrentes) sin cambio de arquitectura. |
| **Experiencia del desarrollador** | Un solo modelo mental (ECS/Fargate) para los dos componentes; `terraform apply`/`destroy` es el ciclo completo de vida, sin pasos manuales en la consola. |

## Estimación de costo total del ejercicio

Supuesto: ~36 horas de reloj entre el primer `terraform apply`, las iteraciones de desarrollo/pruebas, la sustentación y un margen de contingencia.

| Recurso | Cálculo | Subtotal |
|---|---|---|
| RDS `db.t4g.micro` (ADR-007) | USD 0.016/h × 36 h | ≈ USD 0.58 |
| Fargate `emh-api` (0.25 vCPU/0.5 GB) | (0.25×0.0404784 + 0.5×0.00444)/h × 36 h | ≈ USD 0.44 |
| Fargate `emh-sandbox` (0.5 vCPU/1 GB) | ≈ USD 0.029/h × ~1.5 h efectivas (30 ejecuciones × ~3 min) | ≈ USD 0.04 |
| Inferencia Nova 2 Lite (ADR-002) | ≈ USD 0.12/ejecución completa × ~40 ejecuciones (desarrollo + demo) | ≈ USD 4.80 |
| ECR (almacenamiento de imágenes) | Volumen mínimo | ≈ USD 0.02 |
| SSM Parameter Store, AWS Budgets | Nivel gratuito | USD 0.00 |
| **Total estimado** | | **≈ USD 6.0** |

Margen sobre el crédito disponible: ~94 %. La partida dominante es, con diferencia, la inferencia (ADR-002), no la infraestructura — coherente con haber elegido Nova 2 Lite y con haber eliminado ALB/NAT.

## Guardarraíl de presupuesto

Un `aws_budgets_budget` (Terraform) sobre el costo mensual de la cuenta, con alertas (sin acción automática de apagado, para no arriesgar la demo en vivo) a **USD 20, 50 y 80** de los USD 100 disponibles, notificando por correo vía SNS. Es el control operativo que complementa, sin sustituir, el control 4 de `05-politicas-y-controles.md` (presupuesto por ejecución, aplicado dentro de la plataforma): uno limita el gasto de una solicitud, el otro limita el gasto de toda la cuenta.

## Consecuencias

- Nuevo directorio `infra/` con los módulos de Terraform (`network`, `ecs`, `rds`, `budget`), usando el *provider* `hashicorp/aws ~> 6.66`.
- `emh/execution` gana un segundo adaptador de `Sandbox` (`FargateSandbox`, vía `boto3` ECS `run_task`), seleccionado por configuración.
- `emh/persistence` gana un segundo adaptador de `RunRepository` (`PostgresRunRepository`), seleccionado por configuración; el esquema es el mismo definido en `02-modelo-entidades.md` (ADR-007).
- El camino local (Docker + SQLite) se conserva como *fallback* de la sustentación en vivo y como entorno de pruebas de nivel A/CI, donde no tiene sentido pagar por infraestructura de nube en cada ejecución de pruebas.
- Disciplina de apagado: `terraform destroy` se ejecuta tan pronto termina la sustentación; el `README.md` lo deja como el último paso documentado, no opcional.
