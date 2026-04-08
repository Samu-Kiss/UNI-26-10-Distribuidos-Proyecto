# Diagramas

## Diagrama de Componentes

```mermaid

```

## Diagrama de Clases

```mermaid

```

## Diagrama de Secuencia

```mermaid

```

## Diagrama de Despliegue

Este diagrama muestra cómo se distribuyen los componentes de software en los cuatro computadores definidos en la arquitectura y cómo se comunican entre sí.

```mermaid
---
config:
  layout: elk
  look: neo
  theme: neutral
---
flowchart LR
 subgraph PC0["🖥️ PC0 (Generacion y Estado Historico)"]
    direction TB
        G["Generador de Vehiculos"]
        M["Gestor de Estado de Mapa"]
        HDB[("Base de Datos Historica")]
  end
 subgraph PC1["🖥️ PC1 (Sensores y Broker ZeroMQ)"]
    direction TB
        SC["Sensor Camara"]
        SE["Sensor Espira"]
        SG["Sensor GPS"]
        BZ(("Broker ZeroMQ"))
  end
 subgraph PC2["🖥️ PC2 (Analitica, Control y Replica Operativa)"]
    direction TB
        A["Servicio de Analitica"]
        T["Control de Semaforos"]
        RDB[("Base de Datos Replica")]
  end
 subgraph PC3["🖥️ PC3 (Monitoreo, Reloj y BD Principal)"]
    direction TB
        F["Frontend / Visualizacion"]
        B["Backend / API de Monitoreo"]
        C(("Reloj de Simulacion"))
        MDB[("Base de Datos Principal")]
  end
    G -- Actualiza posiciones --> M
    M -- Registro diario --> HDB
    M == Estado actual de vehiculos ==> MDB
    M == Estado actual de vehiculos ==> RDB
    SC -- PUB --> BZ
    SE -- PUB --> BZ
    SG -- PUB --> BZ
    BZ == SUB eventos de sensores ==> A
    A -- Control / cambios de fase --> T
    F <-- HTTP/WS --> B
    B <== Ordenes directas de control ==> A
    B == Crea ambulancia por ZeroMQ ==> G
    C -. Referencia de tiempo .-> F
    C -. Referencia de tiempo .-> B
    RDB -. Resincroniza a MDB cuando PC3 vuelve .-> MDB
```

### Explicación de nodos y conexiones

1. **PC0**: maneja la vida de los vehículos en la simulación. Actualiza el mapa, guarda su histórico propio y comunica el estado actual de los vehículos a PC3 y a la réplica operativa de PC2.
2. **PC1**: ejecuta los sensores lógicos sobre las aristas y publica sus eventos vía `PUB/SUB` al broker ZeroMQ. El broker es la puerta de entrada de los eventos hacia el resto del sistema.
3. **PC2**: actúa como el cerebro de control. Escucha los eventos, calcula los scores por vía, revisa los conflictos de cada intersección, controla los semáforos y mantiene la réplica operativa del estado actual. No guarda histórico de largo plazo.
4. **PC3**: expone las interfaces al usuario, contiene la base de datos principal y gestiona el reloj global. Si cae, la operación pasa a PC2. Cuando PC3 vuelve, su base se resincroniza con PC2 y la operación regresa automáticamente a PC3.
