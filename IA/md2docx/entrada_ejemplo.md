# Manual de proceso — Ejemplo

Este documento de ejemplo contiene texto normal, una tabla y dos diagramas
Mermaid, para comprobar que el pipeline de conversión funciona correctamente.

## 1. Introducción

El siguiente flujo resume el proceso de onboarding de un nuevo empleado:

```mermaid
flowchart TD
    A[Solicitud de alta] --> B{Documentacion completa?}
    B -- Si --> C[Crear cuentas de acceso]
    B -- No --> D[Solicitar documentos faltantes]
    D --> B
    C --> E[Asignar equipo]
    E --> F[Sesion de bienvenida]
    F --> G[Fin del proceso]
```

## 2. Tabla de responsables

| Fase                  | Responsable        | Plazo estimado |
|-----------------------|---------------------|----------------|
| Alta en el sistema    | Recursos Humanos    | 1 día          |
| Asignación de equipo  | IT                  | 2 días         |
| Sesión de bienvenida  | Manager directo     | 1 semana       |

## 3. Diagrama de secuencia

A continuación se muestra la interacción entre los sistemas implicados:

```mermaid
sequenceDiagram
    participant Empleado
    participant RRHH
    participant IT
    Empleado->>RRHH: Envía documentación
    RRHH->>IT: Solicita creación de cuentas
    IT-->>RRHH: Confirma cuentas creadas
    RRHH-->>Empleado: Notifica acceso disponible
```

## 4. Conclusión

Este flujo garantiza una incorporación ordenada y trazable de cada nuevo
empleado, con responsables claramente definidos en cada fase.
