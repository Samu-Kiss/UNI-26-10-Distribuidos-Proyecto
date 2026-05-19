# Diagramas Mermaid

## 1. Diagrama de clases

```mermaid
classDiagram
direction LR

namespace common.modelos {
    class Vehiculo:::modelos {
        +id_vehiculo: str
        +via_actual: str
        +velocidad: float
        +estado: str
        +tipo: str
    }

    class Interseccion:::modelos {
        +id_interseccion: str
        +fase_activa: str
        +fase_alterna: str
        +ticks_restantes_fase: int
    }

    class NodoBorde:::modelos {
        +id_nodo: str
        +lado: str
    }

    class Via:::modelos {
        +id_via: str
        +origen: str
        +destino: str
        +direccion: str
        +eje: str
        +longitud: float
        +vehiculos_en_circulacion: int
        +vehiculos_en_espera: int
        +velocidad_promedio: float
        +score: float
        +estado_congestion: str
    }

    class CiudadMapa:::modelos {
        +intersecciones: dict[str, Interseccion]
        +nodos_borde: dict[str, NodoBorde]
        +vias: dict[str, Via]
        +tick_actual: int
        +desde_config(config_ciudad) CiudadMapa
        +iterar_vias() Iterable[Via]
        +obtener_vias_de_entrada(interseccion) list[Via]
        +obtener_vias_instrumentadas() list[Via]
        +obtener_vias_salida(nodo) list[Via]
        +es_interseccion(nodo) bool
        +es_nodo_borde(nodo) bool
        +aplicar_programacion_semaforo(interseccion_id, fase_ganadora, tiempo_verde, tiempo_opuesto) None
    }

    class ResultadoTick:::modelos {
        +tick: int
        +creados: int
        +eliminados: int
        +movidos: int
        +vehiculos_creados: list[Vehiculo]
    }

    class MotorSimulacion:::servicios {
        +ciudad_mapa: CiudadMapa
        +vehiculos: dict[str, Vehiculo]
        +avanzar_tick() ResultadoTick
        +aplicar_comando_semaforo(comando: ComandoSemaforo) None
        +generar_snapshot_operativo() SnapshotOperativo
        +inyectar_ambulancia(nodo_origen, velocidad) Vehiculo | None
    }
}

namespace common.mensajes {
    class SolicitudAmbulancia:::modelos {
        +nodo_origen: str
        +velocidad: float | None
        +timestamp: str
        +a_dict() dict
        +crear(nodo_origen, velocidad) SolicitudAmbulancia
        +desde_dict(datos) SolicitudAmbulancia
    }

    class SolicitudControlManual:::modelos {
        +interseccion: str
        +fase_ganadora: str
        +duracion_ticks: int
        +timestamp: str
        +a_dict() dict
        +crear(interseccion, fase_ganadora, duracion_ticks) SolicitudControlManual
        +desde_dict(datos) SolicitudControlManual
    }

    class ComandoSemaforo:::modelos {
        +interseccion: str
        +fase_ganadora: str
        +tiempo_verde: float
        +tiempo_opuesto: float
        +razon: str
        +tick_origen: int
        +timestamp: str
        +a_dict() dict
        +crear(interseccion, fase_ganadora, tiempo_verde, tiempo_opuesto, razon, tick_origen) ComandoSemaforo
        +desde_dict(datos) ComandoSemaforo
    }

    class SnapshotOperativo:::modelos {
        +timestamp: str
        +tick_actual: int
        +fuente: str
        +version_contrato: int
        +intersecciones: list[dict]
        +vias: list[dict]
        +vehiculos: list[dict]
        +metricas_tick: dict
        +a_dict() dict
        +crear(timestamp, tick_actual, intersecciones, vias, vehiculos, metricas_tick, fuente, version_contrato) SnapshotOperativo
        +desde_dict(datos) SnapshotOperativo
    }

    class EventoSensor:::modelos {
        +sensor_id: str
        +tipo_sensor: str
        +interseccion: str
        +via_id: str
        +tick_origen: int
        +datos: dict
        +timestamp: str
        +a_dict() dict
        +crear(sensor_id, tipo_sensor, interseccion, via_id, tick_origen, datos) EventoSensor
        +desde_dict(datos) EventoSensor
    }
}

namespace common.utilidades {
    class RepositorioSQLite:::repositorios {
        +inicializar_pc0() None
        +inicializar_pc2() None
        +inicializar_pc3() None
        +guardar_snapshot_operativo(snapshot) None
        +guardar_evento_sensor(evento) None
        +guardar_comando_semaforo(comando) None
        +guardar_snapshot_vehiculos_historico(snapshot) None
        +reconstruir_snapshot_operativo_actual() dict | None
        +obtener_resumen_estado() dict
        +obtener_estado_interseccion(interseccion_id) dict | None
        +obtener_estado_via(via_id) dict | None
        +listar_ambulancias_actuales() list[dict]
    }

    class BackendOperativo:::servicios {
        +rol_backend: str
        +permitir_operaciones_activas: bool
        +atender_solicitud(solicitud) dict
    }

    class ClienteBackendFailover:::servicios {
        +endpoint_primario: str
        +endpoint_respaldo: str
        +solicitar(solicitud) dict
    }
}

namespace PC2 {
    class ControladorSemaforos:::controladores {
        +aplicar_comando(comando: ComandoSemaforo) None
    }

    class ServicioAnalitica:::servicios {
        +controlador: ControladorSemaforos
        +ciudad_mapa: CiudadMapa
        +persistir_comando(comando: ComandoSemaforo) None
        +aplicar_control_manual(solicitud: SolicitudControlManual) None
        +calcular_score_via(interseccion, tick_origen, via_id) tuple
        +calcular_scores_por_eje(interseccion, tick_origen) tuple
        +decidir_fase(interseccion, score_horizontal, score_vertical) tuple
        +procesar_evento(evento: EventoSensor) None
    }
}

CiudadMapa *-- Interseccion : intersecciones
CiudadMapa *-- NodoBorde : nodos_borde
CiudadMapa *-- Via : vias
MotorSimulacion o-- CiudadMapa : ciudad_mapa
MotorSimulacion *-- Vehiculo : vehiculos
ResultadoTick --> Vehiculo : vehiculos_creados
MotorSimulacion ..> ComandoSemaforo : aplicar_comando_semaforo
MotorSimulacion ..> SnapshotOperativo : generar_snapshot_operativo
ServicioAnalitica *-- ControladorSemaforos : controlador
ServicioAnalitica *-- CiudadMapa : ciudad_mapa
ServicioAnalitica ..> EventoSensor : procesar_evento
ServicioAnalitica ..> SolicitudControlManual : aplicar_control_manual
ServicioAnalitica ..> ComandoSemaforo : persistir_comando
ControladorSemaforos ..> ComandoSemaforo : aplicar_comando
BackendOperativo o-- RepositorioSQLite : repositorio
BackendOperativo ..> SolicitudAmbulancia : crear_ambulancia
BackendOperativo ..> SolicitudControlManual : control_manual
ClienteBackendFailover ..> BackendOperativo : solicitar

classDef modelos fill:#E3F2FD,stroke:#1E88E5,color:#0D47A1,stroke-width:1px;
classDef servicios fill:#E8F5E9,stroke:#43A047,color:#1B5E20,stroke-width:1px;
classDef controladores fill:#FFF3E0,stroke:#FB8C00,color:#E65100,stroke-width:1px;
classDef repositorios fill:#F3E5F5,stroke:#8E24AA,color:#4A148C,stroke-width:1px;

```

### Explicación del diagrama de clases

El diagrama de clases resume las principales estructuras de datos compartidas del sistema, incluyendo los modelos de la ciudad, los mensajes intercambiados entre procesos y las utilidades de soporte. Permite visualizar qué información mantiene cada entidad y cómo se relacionan entre sí para soportar la simulación, la analítica y el backend operativo.

## 2. Diagrama de secuencia

```mermaid
sequenceDiagram
autonumber

participant PC0Sim as PC0.simulation.servicio_simulacion
participant Motor as MotorSimulacion
participant PC1Sens as PC1.sensors.simulador_sensores
participant Broker as PC1.broker.broker_mq
participant Analitica as ServicioAnalitica
participant Semaforos as ControladorSemaforos
participant PC0Hist as PC0.historic_db.servicio_bd_historica
participant PC2Replica as PC2.replica_db.servicio_bd_replica
participant PC3MainDB as PC3.main_db.servicio_bd_principal

loop cada tick
    PC0Sim->>PC0Sim: procesar_comandos_pendientes(receptor_comandos, motor)
    PC0Sim->>Motor: avanzar_tick()
    Motor-->>PC0Sim: ResultadoTick
    PC0Sim->>Motor: generar_snapshot_operativo()
    Motor-->>PC0Sim: SnapshotOperativo

    PC0Sim->>PC1Sens: send_json({"tipo":"snapshot_operativo","datos": snapshot_dict})
    PC0Sim->>PC2Replica: send_json({"tipo":"snapshot_operativo","datos": snapshot_dict})
    PC0Sim->>PC3MainDB: send_json({"tipo":"snapshot_operativo","datos": snapshot_dict})
    PC0Sim->>PC0Hist: send_json({"tipo":"snapshot_operativo","datos": snapshot_dict})
end

PC2Replica->>PC2Replica: guardar_snapshot_operativo(datos)
PC3MainDB->>PC3MainDB: guardar_snapshot_operativo(datos)
PC0Hist->>PC0Hist: guardar_snapshot_vehiculos_historico(datos)

PC1Sens->>PC1Sens: SnapshotOperativo.desde_dict(mensaje["datos"])
loop por cada via instrumentada y tipo_sensor
    PC1Sens->>PC1Sens: construir_datos(tipo_sensor, via)
    PC1Sens->>PC1Sens: EventoSensor.crear(sensor_id, tipo_sensor, interseccion, via_id, tick_actual, datos)
    PC1Sens->>Broker: send_multipart([tipo_sensor, evento])
    PC1Sens->>PC0Hist: send_json({"tipo":"evento_sensor","datos": evento.a_dict()})
end

Broker->>Analitica: recv_multipart()
Analitica->>Analitica: EventoSensor.desde_dict(...)
Analitica->>Analitica: procesar_evento(evento)

opt tick_listo_para_interseccion(...) y sin control manual activo
    Analitica->>Analitica: calcular_scores_por_eje(interseccion, tick_origen)
    Analitica->>Analitica: decidir_fase(interseccion, score_horizontal, score_vertical)
    Analitica->>Analitica: ComandoSemaforo.crear(...)
    Analitica->>Semaforos: aplicar_comando(comando)
    Semaforos->>PC0Sim: send_json(comando.a_dict())
    Analitica->>PC0Hist: send_json({"tipo":"comando_semaforo","datos": comando.a_dict()})
end

PC0Sim->>PC0Sim: ComandoSemaforo.desde_dict(carga)
PC0Sim->>Motor: aplicar_comando_semaforo(comando)
Motor->>Motor: ciudad_mapa.aplicar_programacion_semaforo(...)
PC0Hist->>PC0Hist: guardar_evento_sensor(datos)
PC0Hist->>PC0Hist: guardar_comando_semaforo(datos)
```

### Explicación del diagrama de secuencia

El diagrama de secuencia muestra el flujo temporal de mensajes entre los procesos distribuidos durante un ciclo de simulación: desde la generación de snapshots en PC0, pasando por la publicación de eventos de sensores y su procesamiento en analítica, hasta la emisión de comandos de semáforos y la persistencia de datos en las distintas bases.

## 3. Diagrama de despliegue

```mermaid
flowchart LR
    classDef modelos fill:#E3F2FD,stroke:#1E88E5,color:#0D47A1,stroke-width:1px;
    classDef servicios fill:#E8F5E9,stroke:#43A047,color:#1B5E20,stroke-width:1px;
    classDef controladores fill:#FFF3E0,stroke:#FB8C00,color:#E65100,stroke-width:1px;
    classDef repositorios fill:#F3E5F5,stroke:#8E24AA,color:#4A148C,stroke-width:1px;

    subgraph Cliente
        C[ClienteBackendFailover]
    end

    subgraph PC0
        S0[servicio_simulacion]
        M0[MotorSimulacion]
        H0[servicio_bd_historica]
        DB0[(bd_historica.sqlite3)]
    end

    subgraph PC1
        S1[simulador_sensores]
        B1[broker_mq]
    end

    subgraph PC2
        A2[servicio_analitica]
        T2[ControladorSemaforos]
        R2[servicio_bd_replica]
        BR2[servicio_backend_respaldo]
        DB2[(bd_replicada.sqlite3)]
    end

    subgraph PC3
        P3[servicio_bd_principal]
        B3[servicio_backend_principal]
        DB3[(bd_principal.sqlite3)]
    end

    M0 --- S0
    H0 --- DB0
    R2 --- DB2
    BR2 --- DB2
    P3 --- DB3
    B3 --- DB3
    A2 --- T2

    S0 -- "snapshot_operativo\n5558" --> S1
    S1 -- "eventos sensores\n5555" --> B1
    B1 -- "eventos sensores\n5556" --> A2
    T2 -- "ComandoSemaforo\n5557" --> S0

    S0 -- "snapshot_operativo\n5560" --> H0
    S1 -- "evento_sensor\n5560" --> H0
    A2 -- "comando_semaforo\n5560" --> H0

    S0 -- "snapshot_operativo\n5561" --> R2
    S0 -- "snapshot_operativo\n5562" --> P3
    P3 -- "solicitar_snapshot_operativo\n5563" --> R2

    C -- "backend_principal\n5567" --> B3
    C -. "failover" .-> BR2
    C -- "backend_respaldo\n5566" --> BR2

    B3 -- "SolicitudAmbulancia\n5564" --> S0
    B3 -- "SolicitudControlManual\n5565" --> A2

    class C servicios;
    class S0,S1,B1,A2,BR2,B3,P3,M0 servicios;
    class T2 controladores;
    class H0,R2,DB0,DB2,DB3 repositorios;
```

### Explicación de nodos y conexiones

1. **PC0**: maneja la vida de los vehículos en la simulación. Actualiza el mapa, guarda su histórico propio y comunica el estado actual de los vehículos a PC3 y a la réplica operativa de PC2.
2. **PC1**: ejecuta los sensores lógicos sobre las aristas y publica sus eventos vía `PUB/SUB` al broker ZeroMQ. El broker es la puerta de entrada de los eventos hacia el resto del sistema.
3. **PC2**: actúa como el cerebro de control. Escucha los eventos, calcula los scores por vía, revisa los conflictos de cada intersección, controla los semáforos y mantiene la réplica operativa del estado actual. No guarda histórico de largo plazo.
4. **PC3**: expone las interfaces al usuario, contiene la base de datos principal y gestiona el reloj global. Si cae, la operación pasa a PC2. Cuando PC3 vuelve, su base se resincroniza con PC2 y la operación regresa automáticamente a PC3.

## 4. Diagrama de componentes

```mermaid
flowchart TB
    classDef simulacion fill:#E3F2FD,stroke:#1E88E5,color:#0D47A1,stroke-width:2px;
    classDef sensores fill:#E8F5E9,stroke:#43A047,color:#1B5E20,stroke-width:2px;
    classDef control fill:#FFF3E0,stroke:#FB8C00,color:#E65100,stroke-width:2px;
    classDef datos fill:#F3E5F5,stroke:#8E24AA,color:#4A148C,stroke-width:2px;
    classDef cliente fill:#FCE4EC,stroke:#E53935,color:#B71C1C,stroke-width:2px;
    classDef failover stroke-dasharray: 5 5;

    subgraph PC0 ["🖥️ PC0 — Simulación"]
        SIM["Motor de\nSimulación"]
        HIST[("BD\nHistórica")]
    end

    subgraph PC1 ["🖥️ PC1 — Sensores y Mensajería"]
        SENS["Sensores\n(Cámara · Espira · GPS)"]
        BROKER["Broker\nZeroMQ"]
    end

    subgraph PC2 ["🖥️ PC2 — Analítica y Control"]
        ANALITICA["Servicio de\nAnalítica"]
        SEMAFOROS["Control de\nSemáforos"]
        REPLICA[("BD\nRéplica")]
        RESPALDO["Backend\nde Respaldo"]
    end

    subgraph PC3 ["🖥️ PC3 — Monitoreo y Persistencia"]
        BACKEND["Backend\nPrincipal"]
        PRINCIPAL[("BD\nPrincipal")]
    end

    CLIENTE(["👤 Cliente\n(Monitoreo y Consulta)"])

    %% --- Flujo principal de simulación ---
    SIM -- "Snapshot\noperativo" --> SENS
    SIM -- "Snapshot\noperativo" --> REPLICA
    SIM -- "Snapshot\noperativo" --> PRINCIPAL
    SIM -- "Snapshot\noperativo" --> HIST

    %% --- Flujo de sensores ---
    SENS -- "Eventos de\nsensores\n(PUB/SUB)" --> BROKER
    SENS -- "Eventos" --> HIST
    BROKER -- "Eventos\nfiltrados" --> ANALITICA

    %% --- Flujo de analítica y control ---
    ANALITICA -- "Comandos" --> SEMAFOROS
    ANALITICA -- "Comandos" --> HIST
    SEMAFOROS -- "Comando\nsemafórico" --> SIM

    %% --- Flujo de persistencia y resincronización ---
    PRINCIPAL -. "Resincronización\n(si PC3 se recupera)" .-> REPLICA

    %% --- Flujo de usuario ---
    CLIENTE -- "Consultas y\noperaciones\n(REQ/REP)" --> BACKEND
    CLIENTE -. "Failover\nautomático" .-> RESPALDO
    BACKEND -- "Ambulancia" --> SIM
    BACKEND -- "Control\nmanual" --> ANALITICA

    %% --- Acceso a BD ---
    BACKEND --- PRINCIPAL
    RESPALDO --- REPLICA

    %% --- Estilos ---
    class SIM,SENS simulacion;
    class BROKER,SEMAFOROS control;
    class ANALITICA sensores;
    class HIST,REPLICA,PRINCIPAL datos;
    class BACKEND,RESPALDO sensores;
    class CLIENTE cliente;
```

### Explicación del diagrama de componentes

El diagrama de componentes ofrece una vista conceptual de alto nivel del sistema, sin referencias a código ni clases. Cada nodo representa un componente lógico y cada flecha una interacción clave:

1. **PC0 (Simulación)**: el motor de simulación es la fuente autoritativa del estado del mundo. Cada tick genera un *snapshot operativo* que propaga a los demás computadores, y recibe comandos semafóricos de vuelta desde PC2.
2. **PC1 (Sensores y Mensajería)**: los sensores observan el estado de las vías a partir del snapshot y publican eventos al broker ZeroMQ mediante PUB/SUB. El broker desacopla productores y consumidores.
3. **PC2 (Analítica y Control)**: la analítica consume los eventos filtrados por el broker, calcula scores de congestión por vía y emite comandos al controlador de semáforos. Además, mantiene la base de datos réplica y un backend de respaldo que se activa automáticamente si PC3 cae.
4. **PC3 (Monitoreo y Persistencia)**: el backend principal atiende las consultas y operaciones del usuario (ambulancias, control manual, consultas históricas) mediante REQ/REP. Accede a la base de datos principal, que se resincroniza con la réplica de PC2 cuando PC3 se recupera de una caída.
5. **Cliente**: el usuario interactúa exclusivamente a través del backend. Un mecanismo de *failover* transparente redirige las peticiones al backend de respaldo en PC2 si el primario no responde.
