# DIAGRAMAS
## DIAGRAMA DE COMPONENTES

```mermaid

```


## DIAGRAMA DE CLASES

```mermaid

```

## DIAGRAMA DE SECUENCIA

```mermaid

```

## DIAGRAMA DE DESPLIEGUE

Este diagrama ilustra cómo están distribuidos los componentes de software en las cuatro máquinas (Nodos) establecidas en la arquitectura y los protocolos/patrones de comunicación entre ellos.

```mermaid
---
config:
  layout: elk
  look: neo
  theme: neutral
---
flowchart LR
 subgraph PC0["🖥️ PC0 (Generación y Estado Histórico)"]
    direction TB
        G["Generador de Vehículos"]
        M["Gestor de Estado de Mapa"]
        HDB[("Base de Datos Histórica")]
  end
 subgraph PC1["🖥️ PC1 (Sensores y BrokerZMQ)"]
    direction TB
        SC["Sensores: Cámaras"]
        SE["Sensores: Espiras"]
        SG["Sensores: GPS"]
        BZ(("Broker ZeroMQ"))
  end
 subgraph PC2["🖥️ PC2 (Analítica, Control y Respaldo)"]
    direction TB
        A["Servicio de Analítica"]
        T["Control de Semáforos"]
        RDB[("Base de Datos Réplica")]
  end
 subgraph PC3["🖥️ PC3 (Monitoreo, Reloj y BD Principal)"]
    direction TB
        F["Frontend / Visualización GUI"]
        B["Backend / API Monitoreo"]
        C(("Reloj de Simulación"))
        MDB[("Base de Datos Principal")]
  end
    G -- Actualiza posiciones --> M
    M -- Registro Diario --> HDB
    SC -- PUB --> BZ
    SE -- PUB --> BZ
    SG -- PUB --> BZ
    A -- Control / Cambios de Fase --> T
    A -- PUSH Asíncrono --> RDB
    F <-- HTTP/WS --> B
    B <-- REQ/REP --> MDB
    C -. Referencia de tiempo .-> F & B
    BZ == SUB Eventos de Sensores Asíncrono ==> A
    A == PUSH Actualización Asíncrona ==> MDB
    B <== Órdenes directas Forzado de semáforo ==> A
    B -. Monitoreo estado Replicación .-> RDB
    M == Sincronización posiciones ==> MDB & RDB
    B == Crea Ambulancia ZeroMQ ==> G
```

### Explicación de los Nodos y Conexiones

1. **PC0**: Encargado enteramente de la vida de los vehículos en la simulación. Actualiza el mapa y escribe su propio histórico. Actualiza en tiempo real las BDs en PC2 (Réplica) y PC3 (Principal) para que se puedan consultar y mostrar en el Frontend.
2. **PC1**: Genera mediciones y las publica vía `PUB/SUB` al `Broker ZeroMQ` contenido en su misma máquina. Este Broker será la puerta de entrada de todos los eventos hacia el resto del sistema.
3. **PC2**: Actúa como el "Cerebro" de control de tráfico. Escucha los eventos a través de ZeroMQ (con el patrón `SUB`), procesa las reglas matemáticas de priorización (score) e instruye al Control de Semáforos. También guarda todo asíncronamente (patrón `PUSH/PULL`) en la BD Réplica y envía a la principal.
4. **PC3**: Expone las interfaces al usuario (Monitoreo, historial, forzar un semáforo a verde para una ambulancia). Contiene la base de datos oficial en producción y gestiona el Reloj Global (Acelerabilidad de hora de juego de 12:00 a 18:00)