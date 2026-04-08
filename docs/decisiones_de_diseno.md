# Decisiones de Diseño
## Gestión Inteligente de Tráfico Urbano

**Pontificia Universidad Javeriana**  
**Facultad de Ingeniería**  
**Departamento de Ingeniería de Sistemas**  
**Introducción a Sistemas Distribuidos**

| | |
|---|---|
| **Integrantes** | Integrante 1, Integrante 2, Integrante 3, Integrante 4, Integrante 5 |
| **Docente** | John Jairo Corredor |
| **Fecha** | 4 de abril de 2026 |

---

## Índice

1. [Resumen del Diseño Acordado](#1-resumen-del-diseño-acordado)
2. [Decisiones Base del Proyecto](#2-decisiones-base-del-proyecto)
3. [Modelo de la Ciudad](#3-modelo-de-la-ciudad)
4. [Sensores y Estado del Tráfico](#4-sensores-y-estado-del-tráfico)
5. [Lógica de Analítica y Semáforos](#5-lógica-de-analítica-y-semáforos)
6. [Vehículos y Simulación](#6-vehículos-y-simulación)
7. [Distribución por Computadores](#7-distribución-por-computadores)
8. [Persistencia y Tiempo de Simulación](#8-persistencia-y-tiempo-de-simulación)
9. [Interacción entre Componentes](#9-interacción-entre-componentes)
10. [Inicialización del Sistema](#10-inicialización-del-sistema)
11. [Fallos y Continuidad Operativa](#11-fallos-y-continuidad-operativa)
12. [Comparación de Rendimiento del Broker](#12-comparación-de-rendimiento-del-broker)

---

## 1. Resumen del Diseño Acordado

El sistema se organiza sobre cuatro computadores (**PC0**, **PC1**, **PC2** y **PC3**) que se comunican con ZeroMQ. La ciudad se representa como una cuadrícula N×M, pero internamente se maneja como un **grafo dirigido** donde las intersecciones son nodos y las vías son aristas con datos de tráfico. Sobre las aristas o accesos de entrada se ubican sensores lógicos de tipo cámara, espira inductiva y GPS. Sus eventos alimentan un *score* por vía de entrada antes del semáforo, y ese valor se usa para decidir cuál conflicto del cruce debe recibir prioridad. Un reloj global de simulación (12:00 a 18:00) da la referencia temporal de todos los eventos.

- **PC1** aloja los sensores y el broker ZeroMQ.
- **PC2** ejecuta la analítica, el control semafórico y la réplica de la base de datos.
- **PC3** ofrece monitoreo, consulta, visualización, base de datos principal y control manual.
- **PC0** (extensión del grupo de computadores) genera los vehículos simulados y guarda el histórico del día; no reemplaza a otro computador en caso de falla.

La estrategia de resiliencia se enfoca en la caída de PC3, usando la réplica de PC2 para que el sistema siga funcionando. También se plantea un experimento de rendimiento para comparar una versión base del broker con otra mejorada con hilos.

Todo el diseño es **parametrizable**: el tamaño de la cuadrícula, las intersecciones activas, las frecuencias de sensores, los pesos de la analítica, los tiempos semafóricos y las reglas de tráfico se definen en archivos de configuración compartidos.

---

## 2. Decisiones Base del Proyecto

### 2.1. Supuestos Generales

- Se asume exactamente un sensor lógico de cada tipo (cámara, espira inductiva y GPS) por cada arista o acceso observado en el sistema.
- Todas las vías son de **sentido único**.
- El cambio de semáforo ocurre únicamente entre **verde y rojo**, sin fase amarilla.
- Todo el sistema se diseña de forma parametrizada, de modo que la escala pueda aumentarse o reducirse sin modificar la lógica central.
- La cantidad total de sensores se deriva de las aristas o accesos observados: si hay *k* aristas instrumentadas, existirán **3k sensores lógicos**.

### 2.2. Parámetros Configurables

Los siguientes parámetros deben poder ajustarse con archivos de configuración, sin recompilar el sistema:

- Tamaño de la cuadrícula de la ciudad (N×M).
- Conjunto de intersecciones activas dentro de la cuadrícula.
- Frecuencia de generación de eventos por tipo de sensor.
- Endpoints de comunicación ZeroMQ (IP o hostname y puerto) para permitir tanto ejecución local como despliegue en múltiples PCs.
- Tiempos base de alternancia semafórica (por defecto, **15 segundos** en condiciones normales).
- Reglas y umbrales que definen los estados de tráfico (normal, congestión, priorización).
- Pesos de ponderación de cada sensor para el cálculo del score.
- Parámetros del reloj de simulación (hora de inicio, hora de fin, factor de aceleración).
- Parámetros de generación de vehículos en PC0 (tasa de ingreso, velocidades, etc.).

#### Convención de Documentación del Archivo de Configuración

El archivo principal de configuración es `config/system_config.json`. Como el proyecto lo carga con `json.load`, no es posible usar comentarios nativos tipo `//` o `/* ... */` sin romper el parseo. Por esa razón, se adopta una convención explícita: agregar claves `_comentario` o `_comentarios` dentro del mismo JSON para explicar el propósito de cada bloque y de cada parámetro sin afectar la ejecución.

En la implementación actual, ese archivo agrupa sus parámetros en cinco bloques:

- `ciudad`: define la geometría de la cuadrícula, el rango de longitud de las vías y la semilla usada para construir el mapa reproducible.
- `sensores`: define qué tipos de sensores están activos y con qué frecuencia publica `PC1` sus eventos derivados del snapshot.
- `analitica`: define el umbral general de congestión y los pesos usados para combinar cámara, espira y GPS en el score por vía.
- `simulacion`: define la duración del tick real, el tiempo simulado por tick, la frecuencia de envío de snapshots, la tasa de generación de vehículos, el máximo de vehículos por tick, el rango de velocidades iniciales y la velocidad por defecto de ambulancias.
- `zmq`: define todos los endpoints de comunicación entre `PC0`, `PC1`, `PC2` y `PC3`, incluyendo ingestas de bases de datos, broker, snapshots, backend principal, backend de respaldo, control manual y solicitudes de ambulancia.

Dentro del bloque `simulacion` también quedan parametrizadas de forma explícita `hora_inicio_simulada` y `hora_fin_simulada`, para que el reloj lógico del sistema no dependa solo de lo escrito en el informe sino de valores reales del archivo de configuración.

Esta convención tiene dos ventajas para el informe final: el archivo sigue siendo ejecutable tal como está, y al mismo tiempo queda autoexplicado para cualquier integrante que necesite modificar parámetros sin rastrear el código fuente.

### 2.3. Organización del Código Compartido

El proyecto incluye un directorio compartido llamado `common`, cuyo propósito es centralizar el código que debe ser reutilizado por varios procesos distribuidos del sistema. Esta organización reduce duplicación, evita inconsistencias entre nodos y hace más claro el mantenimiento del proyecto.

Dentro de `common` se distinguen tres responsabilidades:

- `common/mensajes`: contiene los contratos de comunicación entre procesos. Aquí se definen las estructuras de eventos, comandos y solicitudes compartidas para que productores y consumidores manejen el mismo formato.
- `common/modelos`: contiene las entidades del dominio y del mundo simulado, por ejemplo el grafo de la ciudad, las vías, las intersecciones, los vehículos y los resultados de simulación.
- `common/utilidades`: contiene funciones auxiliares reutilizables que **no representan entidades del dominio**, pero son necesarias para operar el sistema de manera consistente.

Es importante aclarar que ubicar una pieza en `common` **no significa** que cualquier computador tenga autoridad para ejecutar la acción asociada. `common` solo centraliza contratos, modelos y lógica reutilizable. La autoridad operativa sigue definida por la arquitectura: por ejemplo, `PC0` es el único dueño del mapa y de los vehículos, aunque la solicitud de ambulancia y la lógica compartida del backend vivan en código común.

La carpeta `common/utilidades` se usa para centralizar tareas transversales como:

- carga de configuración compartida,
- generación de logs,
- normalización de sensores,
- y otros *helpers* reutilizables por múltiples computadores.

Esta separación permite que la lógica principal del sistema quede en los modelos y en los procesos de cada PC, mientras que `common/utilidades` funciona como una caja de herramientas compartida que mantiene una única fuente de verdad para operaciones auxiliares repetidas.

En la implementación actual, el contenido principal de `common` se entiende así:

- `common/mensajes/eventos.py`: eventos de sensores emitidos por `PC1`, incluyendo la vía observada y el `tick_origen`.
- `common/mensajes/comandos.py`: comandos semafóricos emitidos por `PC2` hacia `PC0`.
- `common/mensajes/estado_operativo.py`: contrato del `snapshot_operativo` que representa la foto actual del sistema.
- `common/mensajes/ambulancias.py`: solicitud compartida para crear ambulancias en `PC0`.
- `common/modelos/trafico.py`: grafo de la ciudad, intersecciones, nodos de borde y vías.
- `common/modelos/vehiculos.py`: entidades vehiculares del sistema.
- `common/modelos/simulacion.py`: motor de simulación por ticks y reglas de movimiento.
- `common/utilidades/configuracion.py`: carga y acceso a configuración compartida.
- `common/utilidades/logs.py`: formato uniforme de logs.
- `common/utilidades/normalizacion_sensores.py`: fórmulas y clasificación de sensores.
- `common/utilidades/persistencia_sqlite.py`: persistencia compartida en SQLite.
- `common/utilidades/mensajeria_zmq.py`: helpers ZeroMQ de mejor esfuerzo.

### 2.4. Organización del Repositorio por Computador

Además de `common`, el repositorio se organiza por el rol de cada computador:

- `PC0/simulation`: simulación autoritativa del mapa, tick, vehículos y ambulancias.
- `PC0/historic_db`: persistencia histórica amplia del día simulado.
- `PC1/sensors`: sensores lógicos que leen snapshots y publican eventos.
- `PC1/broker`: broker ZeroMQ base que reenvía eventos.
- `PC2/analytics`: servicio de analítica y decisión semafórica por tick.
- `PC2/traffic_ctrl`: envío de comandos semafóricos hacia `PC0`.
- `PC2/replica_db`: réplica operativa y canal de resincronización para `PC3`.
- `PC2/backend_respaldo`: backend de respaldo limitado a continuidad y consulta de estado actual cuando `PC3` no está disponible.
- `PC3/main_db`: base principal y servicio de persistencia/resincronización.
- `PC3/backend`: backend principal de consultas de estado, creación de ambulancias y control manual.

Como criterio de mantenimiento del repositorio, se evita conservar directorios vacíos o de andamio que todavía no cumplen una función real en la implementación. Si en una fase posterior vuelve a ser necesario separar responsabilidades como generadores, variantes de broker, reloj explícito o frontend, esas carpetas pueden recrearse en ese momento para dejar un esqueleto del proyecto claro, limpio y alineado con el estado real del código.

---

## 3. Modelo de la Ciudad

### 3.1. Cuadrícula y Grafo Dirigido

La ciudad se describe como una cuadrícula N×M (filas por letras y columnas por números). Internamente se modela como un **grafo dirigido** sobre esa cuadrícula: las intersecciones son nodos y las vías de sentido único son aristas dirigidas con atributos. Este modelo permite representar la dirección del flujo, la congestión y el estado de cada vía.

En la visualización se puede mostrar información sobre las vías como si hubiera puntos intermedios, pero en la lógica del sistema cada vía sigue siendo una arista con atributos.

### 3.2. Intersecciones

Cada intersección es un nodo del grafo con los siguientes atributos:

- **Identificador único:** por ejemplo `INT-C5` (fila C, columna 5).
- **Coordenada** (fila, columna).
- **Sensores relacionados:** las aristas o accesos conectados a la intersección cuentan con sensores lógicos de cámara, espira inductiva y GPS.
- **Dos semáforos lógicos:** eje horizontal y eje vertical.
- **Fase activa:** `HORIZONTAL` o `VERTICAL`; nunca hay dos fases en verde simultáneamente.

### 3.3. Vías

Cada vía se modela como una **arista dirigida** del grafo con los siguientes atributos. Como todas las vías son unidireccionales, cada arista representa un solo sentido de circulación:

- Intersección origen.
- Intersección destino (o nodo de salida destino).
- Longitud o costo de la vía.
- Dirección cardinal del movimiento (`NORTE`, `SUR`, `ESTE` u `OESTE`).
- Vehículos en circulación dentro de la arista.
- Vehículos en espera (detenidos por semáforo en rojo al final de la arista).
- Velocidad promedio observada.
- Score de congestión (valor normalizado en [0, 1]).
- Estado de congestión derivado del score: tráfico normal, congestión o priorización.

### 3.4. Nodos de Salida

Los bordes de la cuadrícula se modelan mediante **nodos especiales de tipo Salida**, que permiten representar la entrada y salida de vehículos de la ciudad. Sus atributos son:

- Identificador único.
- Intersección del borde a la que está conectado.
- Lado de salida: `NORTE`, `SUR`, `ESTE` u `OESTE`.

Estos nodos habilitan el ingreso de vehículos generados por PC0 y el egreso cuando un vehículo llega al borde.

---

## 4. Sensores y Estado del Tráfico

### 4.1. Sensores por Arista

Cada arista o acceso instrumentado cuenta con sensores lógicos de cada tipo: cámara, espira inductiva y GPS. Los sensores funcionan como **getters del estado de la arista**: consultan de forma periódica los atributos del tramo observado y procesan esos datos para producir las estadísticas y eventos que necesita la analítica. Como la vía tiene un único sentido, el sensor solo mide el flujo que viene en ese sentido hacia el semáforo.

En la implementación, los eventos de sensores se emiten **por arista instrumentada**, no como un único resumen agregado por intersección completa. Por ello, cada evento identifica explícitamente la vía observada y la intersección destino asociada a esa vía.

### 4.2. Cámara

La cámara mide la acumulación o cola de vehículos y aporta una señal de ocupación inmediata. Sus datos salen de leer la cantidad de vehículos en espera al final de la arista o acceso observado (`EVENTO_LONGITUD_COLA`, **Lq**), es decir, los vehículos que ya completaron la longitud de la vía y se encuentran esperando paso antes de la intersección.

La nota de prioridad aportada por la cámara se calcula como:

$$n_c = \min\left(\frac{\text{vehículos en espera}}{10}, 1\right)$$

Esto implica, por ejemplo:

- 1 vehículo en espera → 0.1
- 5 vehículos en espera → 0.5
- 10 o más vehículos en espera → 1.0

### 4.3. Espira Inductiva

La espira inductiva mide la cantidad de vehículos que están en tránsito dentro de la arista antes de llegar a la intersección, y aporta una señal de presión de tráfico sobre la vía (`EVENTO_CONTEO_VEHICULAR`, **Cv**). En esta versión del diseño, la espira **no mide la cola** sino únicamente los vehículos que aún recorren la arista y no han llegado al punto de espera final.

La nota de prioridad aportada por la espira se calcula como:

$$n_e = \min\left(\frac{\text{vehículos en tránsito}}{10}, 1\right)$$

Esto implica, por ejemplo:

- 1 vehículo en tránsito → 0.1
- 5 vehículos en tránsito → 0.5
- 10 o más vehículos en tránsito → 1.0

### 4.4. GPS

El sensor GPS mide la velocidad promedio de los vehículos **en tránsito** en una arista y aporta una señal complementaria de fluidez o lentitud (`EVENTO_DENSIDAD_DE_TRAFICO`, **Dt**). El GPS **no se usa como criterio único** para cambiar semáforos, sino como un componente ponderado dentro del score total.

El cálculo del GPS solo considera vehículos que se encuentran circulando actualmente por la arista. Si no hay vehículos en tránsito, el promedio de velocidad es 0 y la nota aportada por el GPS también es 0. Si sí hay vehículos en tránsito, el promedio siempre queda entre 10 y 50, porque cada vehículo mantiene una velocidad propia dentro de ese rango mientras circula.

La nota del GPS se calcula por tramos así:

- Si $$x = 0$$, entonces $$n_g = 0$$
- Si $$10 \le x \le 50$$, entonces:

$$n_g = 1 - 0.9 \cdot \frac{x - 10}{40}$$

Con esta normalización:

- 10 se mapea a 1.0
- 50 se mapea a 0.1

En otras palabras, a menor velocidad promedio de tránsito, mayor prioridad aporta el GPS.

### 4.5. Relación entre Sensores y Aristas

Los sensores simulados en PC1 están definidos sobre aristas o accesos y consultan el estado de los vehículos mantenido por PC0 para generar eventos realistas. Cada sensor actúa como un getter especializado del estado de una vía: toma atributos del tramo observado, los procesa según su tipo y publica la estadística resultante.

Cada evento de sensor incluye también el identificador de la vía y el **tick de origen** de la simulación. Esto permite que PC2 agrupe lecturas consistentes del mismo instante lógico antes de calcular una decisión semafórica.

### 4.6. Clasificación Cualitativa de Notas

Las notas normalizadas de los sensores se interpretan también cualitativamente con la misma escala:

- **Bajo:** $$0.0 \le x < 0.4$$
- **Moderado:** $$0.4 \le x \le 0.7$$
- **Intenso:** $$0.7 < x \le 1.0$$

---

## 5. Lógica de Analítica y Semáforos

### 5.1. Score por Vía

La lógica de control semafórico se basa en una **calificación de estado (score)** para cada vía de entrada a una intersección. Ese score solo describe la carga del tráfico antes del semáforo y en el único sentido permitido de la vía. Cada sensor aporta al score con una ponderación configurable. Entre mayor sea el score, mayor será la prioridad para recibir verde. El valor final queda normalizado en **[0, 1]**.

### 5.2. Pesos y Normalización

Cada sensor produce primero una nota normalizada entre 0 y 1. Después, esas tres notas se combinan con pesos configurables para obtener un score final, también entre 0 y 1. En esta versión del diseño, la cámara pondera la cola efectiva al final de la vía, la espira pondera la ocupación en tránsito dentro de la vía y el GPS pondera la lentitud del flujo que todavía se encuentra circulando.

Denotando las notas de cámara, espira y GPS como *n_c*, *n_e* y *n_g*:

$$n_c, n_e, n_g \in [0, 1]$$

$$w_c + w_e + w_g = 1$$

**Pesos definidos para esta versión del diseño:**

| Sensor | Peso | Justificación |
|---|---|---|
| Cámara (*w_c*) | **0.50** | La cola de vehículos es la señal más importante para decidir prioridad. |
| Espira inductiva (*w_e*) | **0.35** | Muestra presión de flujo. |
| GPS (*w_g*) | **0.15** | Solo complementa la lectura de congestión. |

El score de la vía se calcula como:

$$\text{score}_{vía} = w_c \cdot n_c + w_e \cdot n_e + w_g \cdot n_g$$

Como los pesos suman 1 y cada nota está en [0, 1], el resultado final también queda en el rango **[0, 1]**. Estos valores pueden ajustarse si el grupo decide recalibrar el sistema.

### 5.3. Comparación entre Direcciones en Conflicto

Cada intersección se controla comparando las vías de entrada que están en conflicto antes del semáforo. El score se calcula por cada vía de entrada. Por ejemplo, una intersección puede tener:

- Una vía que llega desde el norte con su propio score.
- Una vía que llega desde el sur con su propio score.
- Una vía que llega desde el este con su propio score.
- Una vía que llega desde el oeste con su propio score.

El servicio de analítica en PC2 compara las direcciones que compiten por el paso en el cruce. **La dirección con mayor score recibe prioridad.** Si los puntajes son parecidos, se mantiene la alternancia normal o se aplica una regla de desempate configurable.

Como el control semafórico final se realiza por ejes lógicos (`HORIZONTAL` y `VERTICAL`), en la implementación el score por eje de una intersección se obtiene como el **promedio de los scores de las vías de entrada** asociadas a ese eje. De esta forma se conserva la idea de score por vía, pero se obtiene una medida comparable entre los dos conflictos principales del cruce.

### 5.4. Temporización Semafórica

La duración del verde se ajusta según la diferencia entre los scores de las direcciones en conflicto. Se toma como base un **ciclo total de 30 segundos** (15 segundos por dirección en condiciones normales). En la simulación, 1 segundo real = 1 minuto simulado, por lo que 15 segundos reales equivalen a 15 minutos dentro de la ciudad simulada.

Se define:

$$\text{gap} = |\text{score}_1 - \text{score}_2| \in [0, 1]$$

| Valor de gap | Resultado |
|---|---|
| `gap = 0` | No hay diferencia de prioridad; cada dirección recibe 15 s (ciclo de 30 s). |
| `0 < gap < 1` | La dirección con mayor score recibe una porción mayor del ciclo de 30 s. |
| `gap = 1` | Una dirección tiene score 0; la ganadora recibe los 30 s completos. |

De forma general, el tiempo de verde de la dirección prioritaria es:

$$T_{verde} = 15 + 15 \cdot \text{gap}$$

El tiempo restante del ciclo queda asignado a la dirección opuesta:

$$T_{opuesto} = 30 - T_{verde}$$

### 5.5. Control Manual

Desde PC3 el usuario puede forzar manualmente el estado de un semáforo:

1. Selecciona una intersección y define qué dirección o conflicto quiere priorizar.
2. Indica por cuánto **tiempo de simulación** mantener el forzado.
3. Mientras dure, la lógica automática basada en score queda suspendida en esa intersección.
4. Al finalizar, la intersección regresa al control automático.

---

## 6. Vehículos y Simulación

### 6.1. PC0 como Generador de Vehículos

PC0 es el generador de vehículos simulados y mantiene el estado base del tráfico. Es una extensión del grupo de computadores y **no reemplaza** a PC1, PC2 ni PC3. Desde PC0 se generan vehículos que entran a la ciudad por nodos de borde. Además, PC0 almacena el histórico completo de un día de simulación para el análisis final de estadísticas y comunica el estado de los vehículos a la base principal de PC3, a la réplica operativa de PC2 y a su propia base histórica.

### 6.2. Modelo de Vehículo

Cada vehículo es una entidad simulada con identificador único. Un vehículo solo puede estar en una arista a la vez. Sus atributos mínimos son:

- Identificador del vehículo.
- Arista actual en la que se encuentra.
- Posición relativa o progreso dentro de la arista.
- Velocidad simulada.
- Dirección actual de movimiento.
- Timestamp de última actualización (en tiempo de simulación).

### 6.3. Movimiento dentro de la Cuadrícula

Los vehículos entran al sistema por un nodo de borde y recorren aristas dirigidas entre intersecciones. Al llegar a una intersección, el vehículo decide **aleatoriamente** entre seguir derecho o tomar la alternativa permitida. No puede moverse en contra del sentido de una vía. Sale del sistema cuando llega a un nodo de salida configurado como egreso.

La presencia y el movimiento de los vehículos cambian el estado de las vías: cada vehículo aporta al conteo en circulación dentro de su arista. Si el semáforo está en rojo y el vehículo llega al final de la arista, aporta al conteo de vehículos en espera.

La velocidad de tránsito se asigna al vehículo cuando se instancia y permanece como atributo propio del vehículo. Cuando el carro logra pasar por una intersección con semáforo en verde y entra a una nueva vía, continúa recorriendo esa nueva arista con la misma velocidad que ya tenía asignada.

### 6.4. Ambulancia

Desde PC3 el usuario puede crear manualmente una ambulancia en un nodo de salida. La ambulancia cuenta como un vehículo más, pero con una representación visual distinta y una velocidad constante configurable. A medida que avanza, el usuario puede intervenir manualmente los semáforos desde PC3 para abrirle paso. La ambulancia sale del sistema al llegar a un nodo de salida.

En la implementación actual, la ambulancia se modela como un vehículo de tipo **AMBULANCIA** dentro del mismo motor de simulación. No se agregan todavía atributos visuales extra, porque para una futura visualización basta con conservar su `tipo`, su `via_actual` y su `posicion_en_via` en cada tick; con eso puede distinguirse del tráfico normal y verse moverse por el mapa.

---

## 7. Distribución por Computadores

### 7.1. PC0

> **Extensión propuesta al grupo de computadores.** PC0 es el generador de vehículos simulados y mantiene el estado base del tráfico.

Responsabilidades:

- Generar vehículos que ingresan a la ciudad por nodos de borde.
- Mantener y actualizar la posición de cada vehículo en el grafo.
- Mantener el estado autoritativo del mapa, las vías y los semáforos dentro de la simulación.
- Instanciar ambulancias cuando PC3 lo solicite por ZeroMQ.
- Recibir desde PC2 los comandos semafóricos automáticos y aplicarlos sobre la simulación.
- Publicar snapshots operativos del estado actual hacia PC1 para que los sensores consulten ese estado sin duplicar la simulación.
- Comunicar el estado de los vehículos en el grafo-mapa a la base de datos principal de PC3, a la réplica de PC2 y a su propia base histórica en PC0.
- Almacenar el historial completo de un día de simulación para estadísticas finales.

> PC0 **no** forma parte del mecanismo principal de respaldo cuando ocurre una falla; su almacenamiento histórico es para análisis posterior.

### 7.2. PC1

Responsabilidades:

- Ejecutar los sensores simulados (cámara, espira inductiva y GPS) como procesos lógicos asociados a aristas que generan eventos periódicos.
- Recibir snapshots operativos producidos por PC0 y usarlos como fuente de verdad para calcular sus mediciones.
- Publicar eventos mediante **PUB/SUB** de ZeroMQ, con tópicos diferenciados por tipo de sensor.
- Operar el **broker ZeroMQ** que recibe los eventos y los reenvía a PC2.

### 7.3. PC2

Responsabilidades:

- Suscribirse a los eventos de sensores vía el broker de PC1.
- Calcular el score por vía y determinar la fase semafórica de cada intersección.
- Emitir como máximo **un comando por intersección y por tick de simulación**, usando el `tick_origen` de los eventos para agrupar las mediciones del mismo instante lógico.
- Ejecutar órdenes de control sobre semáforos e imprimir por pantalla las acciones realizadas.
- Recibir y ejecutar indicaciones de control manual provenientes de PC3.
- Mantener la **réplica de la base de datos**, actualizada de forma asíncrona, para que el sistema pueda seguir operando si PC3 falla.
- Exponer un **backend de respaldo** limitado a salud y consultas de estado actual, sin crear ambulancias ni emitir control manual durante el failover.

### 7.4. PC3

Responsabilidades:

- Alojar la **base de datos principal**.
- Proveer monitoreo y consulta del estado actual mediante **REQ/REP**.
- Enviar indicaciones directas al servicio de analítica para forzar cambios semafóricos.
- Exponer el **backend primario** que el cliente consulta normalmente antes de considerar el respaldo de `PC2`.
- Visualizar la ciudad como grafo sobre cuadrícula, con vías coloreadas según congestión e indicadores de fase activa.
- Gestionar el reloj de simulación (aceleración y ralentización).
- Permitir al usuario crear ambulancias en nodos de salida.

---

## 8. Persistencia y Tiempo de Simulación

La primera implementación de persistencia del proyecto se realiza con **SQLite**, ya que permite mantener una base local por computador sin depender de un servidor adicional y facilita el despliegue distribuido inicial del sistema.

### 8.1. Base de Datos en PC3

La base de datos principal reside en PC3. Su responsabilidad principal es almacenar el **estado operativo actual** de la ciudad en tiempo real, por ejemplo:

- estado actual de intersecciones,
- estado actual de las vías,
- estado actualizado de los vehículos dentro del grafo-mapa,
- y el estado vigente del sistema de semaforización.

PC3 **no** se concibe como el repositorio de histórico de eventos de sensores ni de comandos semafóricos. Ese tipo de información se reserva para la base histórica de **PC0**. La base principal de `PC3` se concentra en el estado presente del sistema.

### 8.2. Réplica en PC2

La réplica se encuentra en PC2 y se actualiza de forma **asíncrona** (PUSH/PULL u otro patrón similar). Su propósito es mantener el estado operativo actual de la ciudad, incluyendo el estado reportado de los vehículos, para que el sistema pueda seguir funcionando si PC3 falla. PC2 no es un almacén de resultados históricos de largo plazo; es un **respaldo operativo del estado presente**.

Si PC3 cae, la operación cambia a la base de datos de PC2. Para evitar bloquear el núcleo operativo, los envíos hacia PC3 se manejan en modo de **mejor esfuerzo**: si la base principal no está disponible, PC0, PC1 y PC2 continúan funcionando y la réplica de PC2 sigue recibiendo el estado.

Cuando PC3 vuelve a estar disponible, su base de datos se resincroniza con el estado de PC2 mediante un canal dedicado de sincronización. En el arranque, PC3 solicita a la réplica únicamente el **snapshot operativo actual**, reconstruye su estado presente a partir de esa respuesta y luego vuelve a recibir normalmente las nuevas actualizaciones.

Desde el punto de vista operativo, esto implica que:

- `PC0` sigue simulando y publicando snapshots aunque `PC3` no responda.
- `PC1` sigue publicando sensores aunque no pueda persistir momentáneamente en `PC3`.
- `PC2` sigue analizando, controlando semáforos y manteniendo su réplica operativa.
- Los envíos hacia `PC3` no frenan el ciclo principal; si la base principal no está disponible, esos mensajes se descartan y la operación continúa.
- `PC2` conserva la mejor foto operativa disponible del sistema hasta que `PC3` regrese.
- La periodicidad con la que `PC0` emite esa foto también es configurable en `config/system_config.json` mediante `simulacion.intervalo_snapshot_ticks`, lo que permite controlar cada cuántos ticks se propaga el estado del mapa al resto del sistema.

### 8.3. Histórico Diario en PC0

PC0 almacena el historial completo de un día de simulación para análisis posterior y estadísticas finales. En esta base se concentran especialmente los datos de carácter histórico amplio, como:

- eventos de sensores,
- comandos semafóricos,
- histórico de vehículos a lo largo del día,
- y otros registros útiles para análisis estadístico posterior.

PC0 **no** se utiliza como nodo de resiliencia operativa; su rol es exclusivamente analítico. En consecuencia, la separación adoptada es:

- **PC3 y PC2**: foco en estado operativo actual y continuidad del servicio.
- **PC0**: foco en histórico amplio, métricas y análisis posterior.

### 8.3.1. Comportamiento de las Bases entre Ejecuciones

Si el usuario detiene una ejecución y luego vuelve a arrancar el sistema sin borrar las bases SQLite, no todos los computadores se comportan igual:

- La simulación **no se reanuda** desde base de datos. Cada vez que `PC0` arranca, construye un mapa nuevo y un motor de simulación nuevo en memoria, por lo que vehículos, posiciones y ticks comienzan de nuevo desde cero en el proceso activo.
- La base histórica de `PC0` **sí acumula** datos entre corridas. Si no se limpia, seguirá agregando nuevos eventos de sensores, comandos semafóricos y snapshots históricos de vehículos sobre los registros que ya existían.
- Las bases de `PC2` y `PC3` conservan el último **estado actual persistido** que hubiera quedado de una ejecución anterior. Sin embargo, ese estado no gobierna la simulación nueva: se reemplaza con los snapshots operativos frescos que empiece a emitir `PC0`.
- Mientras no llegue el primer snapshot nuevo, una consulta temprana a `PC2` o `PC3` todavía podría mostrar estado viejo persistido de la corrida anterior.
- Si `PC3` arranca antes de que la nueva simulación produzca snapshots, puede resincronizarse temporalmente con el último snapshot viejo almacenado en `PC2`; esa situación se corrige en cuanto `PC0` vuelve a emitir estado nuevo.

Por esta razón, si se quiere una prueba completamente limpia y sin mezclar corridas anteriores, deben borrarse previamente las SQLite de `PC0`, `PC2` y `PC3`.

### 8.4. Reloj de Simulación

El sistema comparte un **reloj global de simulación** que representa un día de **12:00 a 18:00**. Por defecto:

- **1 segundo real = 1 minuto simulado.**
- Un cambio semafórico normal de 15 segundos en tiempo real equivale a 15 minutos dentro de la ciudad simulada.

Desde PC3 esta relación puede acelerarse o ralentizarse. Todos los eventos (sensores, vehículos, semáforos y persistencia) usan el tiempo de simulación. El histórico en PC0 se indexa con este reloj.

En la implementación actual, ese rango horario también aparece de forma explícita en `config/system_config.json` mediante `simulacion.hora_inicio_simulada` y `simulacion.hora_fin_simulada`. Por ahora estos parámetros se usan como referencia visible del reloj lógico y para enriquecer los logs de `PC0`; todavía no se usa `hora_fin_simulada` para detener automáticamente la simulación al final del día.

---

## 9. Interacción entre Componentes

### 9.1. Flujo General del Sistema

```
1. PC0  → Genera vehículos y mantiene el estado base del tráfico.
2. PC0  → Comunica el estado de los vehículos a PC3 (BD principal),
           PC2 (réplica operativa) y PC0 (base histórica).
3. PC1  → Ejecuta sensores y publica eventos a través del broker ZeroMQ.
4. PC2  → Se suscribe a los eventos, calcula analítica por vía, agrupa
           scores por eje en cada intersección, revisa conflictos
           y determina fases semafóricas.
5. PC3  → Permite monitorear, consultar y emitir indicaciones de control manual.
```

En la implementación actual, **PC0 es el dueño real del mapa y de los vehículos**. Por ello, PC2 envía comandos semafóricos de regreso a PC0 mediante ZeroMQ usando un canal asíncrono **PUSH/PULL**, y PC0 aplica esos cambios sobre la simulación antes de generar el siguiente tick. A su vez, PC0 transmite snapshots operativos del estado actual hacia PC1, para que los sensores consulten ese estado y emitan sus eventos sin ser propietarios de la simulación.

Para facilitar pruebas sin interfaz gráfica, `PC0` registra en logs la creación de cada vehículo normal con sus atributos principales: identificador, tipo, vía, origen, destino, dirección, velocidad, estado, tick y hora simulada.

Un **snapshot operativo** puede entenderse como una foto del estado actual del sistema en un tick determinado. En términos prácticos, este snapshot sirve para que:

- **PC0 le diga a PC1:** "así está el mundo ahorita".
- **PC1** use esa foto para calcular sensores.
- **PC2** y **PC3** guarden estado actual.
- **PC3** pueda resincronizarse desde **PC2** si volvió a levantarse.

La cadencia de envío del snapshot también se controla por configuración. En la implementación actual, `PC0` emite un primer snapshot en el primer tick de simulación y, a partir de ahí, vuelve a emitirlo cada `N` ticks según el valor configurado en `simulacion.intervalo_snapshot_ticks`.

Los endpoints ZeroMQ se definen por configuración. Durante el desarrollo local pueden usarse direcciones como `tcp://127.0.0.1:puerto`, pero en pruebas sobre varios computadores esos valores deben reemplazarse por las IP o nombres de host reales de cada máquina, sin necesidad de modificar el código fuente.

Adicionalmente, el servicio de analítica aplica una estrategia de **deduplicación de comandos semafóricos**: si para una intersección la fase y los tiempos calculados no cambian respecto a la última orden emitida, el sistema no reenvía exactamente el mismo comando. Esto reduce ruido, evita saturar el canal de control y permite que la temporización de los semáforos evolucione con mayor estabilidad.

Sobre esa deduplicación se agrega una segunda restricción: la analítica solo puede emitir **una decisión por intersección en cada tick de origen**. Aunque los eventos lleguen de manera secuencial, PC2 espera a tener completas las mediciones requeridas de ese tick y solo entonces calcula una única decisión para esa intersección.

### 9.2. Creación de Ambulancias

Cuando el usuario crea una ambulancia desde PC3:

1. PC3 envía la solicitud por ZeroMQ a PC0, indicando el nodo de salida donde debe aparecer la ambulancia.
2. PC0 instancia la ambulancia como una entidad vehicular especial dentro de la simulación.
3. PC3 la visualiza con una representación diferenciada (por ejemplo, icono de sirena) respecto al tráfico normal.

En el estado actual del proyecto, este flujo se implementa con un canal ZeroMQ dedicado de tipo **PUSH/PULL**:

- El backend principal de `PC3` actúa como emisor de una `SolicitudAmbulancia`.
- `PC0` mantiene un receptor específico para solicitudes de ambulancia.
- La solicitud contiene al menos el `nodo_origen` y puede incluir una velocidad explícita.
- Si el nodo recibido no corresponde a una entrada válida del sistema, `PC0` descarta la solicitud y la registra en logs.
- Si la solicitud es válida, `PC0` crea la ambulancia y la incorpora al siguiente ciclo operativo del motor de simulación.
- Si `PC3` está caído, la creación de ambulancias queda temporalmente indisponible para el usuario, aunque el núcleo operativo del sistema sigue funcionando.

Operativamente, el flujo exacto queda así:

- `PC3/backend` corre el **backend principal** y es el único backend autorizado para aceptar operaciones activas de usuario como `crear_ambulancia`.
- `PC2/backend_respaldo` corre un **backend de respaldo** con el mismo protocolo de solicitudes, pero con alcance restringido a salud y consulta de estado actual.
- El cliente de failover intenta primero hablar con `PC3`; si no recibe respuesta, reintenta automáticamente la **misma solicitud** contra `PC2`.
- Por eso `PC2` puede llegar a **recibir** una solicitud de creación de ambulancia, pero no a ejecutarla.
- Cuando eso ocurre, `PC2` responde con el error `operacion_no_disponible_en_respaldo`, dejando claro que el respaldo sigue vivo, pero no está autorizado para operaciones activas.
- La ambulancia **nunca se crea en el backend**: el backend solo construye y emite la `SolicitudAmbulancia`; la creación real ocurre exclusivamente en `PC0`, cuando el motor de simulación la inyecta en el mapa.

### 9.3. Priorización Manual de Semáforos

Cuando el usuario fuerza un semáforo desde PC3:

1. El backend principal de `PC3` envía la orden al servicio de analítica/control en PC2.
2. La orden indica qué intersección y qué dirección o conflicto priorizar, y por cuánto tiempo de simulación mantener el forzado.
3. PC2 ejecuta el forzado, suspendiendo temporalmente la lógica automática en esa intersección.
4. Al finalizar el período indicado, la intersección regresa automáticamente al control por score.

En la implementación actual este forzado se realiza así:

- el backend principal emite una `SolicitudControlManual` por ZeroMQ hacia un receptor específico en `PC2`;
- `PC2` valida la intersección, genera un `ComandoSemaforo` manual y lo envía inmediatamente a `PC0`;
- el comando manual se refleja en el estado operativo por medio de los snapshots sucesivos generados por `PC0`;
- mientras dura el forzado, la analítica automática no emite decisiones nuevas para esa intersección.
- Si `PC3` no está disponible, no se aceptan nuevos controles manuales desde el respaldo.

---

## 10. Inicialización del Sistema

### 10.1. Configuración Inicial

Se define un archivo (o conjunto de archivos) de configuración compartidos que todos los componentes leen al arrancar. Esta configuración incluye al menos:

- Tamaño de la cuadrícula (N×M).
- Intersecciones activas y nodos de salida.
- Número y tipo de sensores por arista o acceso instrumentado.
- Parámetros de semáforos (tiempo base y duración del ciclo).
- Pesos de ponderación de sensores y umbrales de analítica.
- Parámetros del reloj de simulación (hora inicio, hora fin, factor de velocidad).
- Parámetros de generación de vehículos (tasa de ingreso, velocidades).

Esta configuración centralizada permite que el arranque sea reproducible y que los parámetros se ajusten sin cambiar código.

### 10.2. Orden de Arranque

| Orden | Componente | Qué levanta |
|---|---|---|
| 1 | **PC3** | Base de datos principal, servicio de monitoreo y reloj de simulación. |
| 2 | **PC2** | Servicio de analítica, control semafórico y réplica operativa de la BD. |
| 3 | **PC1** | Sensores simulados y broker ZeroMQ. |
| 4 | **PC0** | Generación de vehículos y almacenamiento histórico diario. |

Este orden garantiza que los componentes consumidores y de persistencia estén disponibles antes de empezar a emitir eventos y a mover vehículos.

### 10.3. Prioridad de Implementación

Para la implementación incremental del proyecto se prioriza primero el núcleo operativo formado por **PC0, PC1 y PC2**. En esta etapa se busca completar:

- simulación vehicular y estado base del mapa en PC0,
- sensado y broker en PC1,
- analítica, control semafórico y réplica operativa en PC2.

Durante la primera fase, **PC3** se mantuvo con un alcance mínimo de persistencia. Una vez estabilizado el flujo central `PC0-PC1-PC2`, se añadió un backend mínimo en `PC3` y un backend de respaldo reducido en `PC2`, enfocado solamente en continuidad y consulta del estado presente, dejando para una etapa posterior la visualización rica del mapa y el servicio explícito de reloj.

---

## 11. Fallos y Continuidad Operativa

### 11.1. Caída de PC3

La falla principal considerada es la **caída de PC3**. Si PC3 falla, el backend principal deja de responder, pero el sistema no pierde el control operativo porque `PC0`, `PC1` y `PC2` continúan ejecutando la simulación, el sensado, la analítica y la réplica de estado.

### 11.2. Continuidad con PC2

Ante la caída de PC3, el sistema sigue operando con la **réplica en PC2**. Los componentes internos (`PC0`, `PC1` y `PC2`) nunca dejan de trabajar, y el respaldo puede exponer consultas de estado actual para observación mínima si se necesita.

Si PC3 se vuelve a levantar, se sincroniza su base de datos con el estado actual de PC2. Al terminar esa actualización, el cliente vuelve automáticamente a `PC3` como backend principal.

La operación mínima de continuidad incluye también una consulta de **salud**. Esta consulta funciona como un *ping* del backend y permite saber qué servidor atendió la solicitud. Si responde `PC3`, el cliente sigue en el camino normal; si `PC3` no responde y la petición cae a `PC2`, la respuesta de salud identifica explícitamente al respaldo como backend activo.

### 11.3. Limitaciones Durante la Falla

Durante la falla de PC3, las siguientes funcionalidades quedan **indisponibles**:

- creación de nuevas ambulancias desde la capa de usuario;
- emisión de nuevas órdenes manuales de priorización semafórica;
- cualquier consulta basada en histórico de eventos o comandos;
- la parte visual que dependa estrictamente de procesos alojados solo en `PC3`, como un frontend futuro o un reloj explícito aún no replicado.

Durante la falla solo se mantiene, como máximo, consulta básica de estado actual desde el respaldo.

En consecuencia, el cliente de failover puede reenviar al respaldo solicitudes activas como `crear_ambulancia` o `control_manual`, pero el respaldo no las ejecuta: responde de forma explícita que la operación no está disponible en modo respaldo. Este rechazo es deliberado y forma parte del diseño, para evitar que la continuidad operativa de `PC2` se convierta en una capa completa de control de usuario.

> **Nota:** PC0 no participa en el cambio a un respaldo cuando ocurre una falla. El escenario de resiliencia queda así: `PC3` cae → el núcleo `PC0-PC1-PC2` sigue funcionando → opcionalmente `PC2` expone solo estado actual → `PC3` vuelve → se resincroniza desde `PC2` con el snapshot operativo → el cliente regresa automáticamente al primario.

Durante el proceso de resincronización de PC3 pueden seguir ocurriendo cambios en el sistema mientras se copia el estado desde PC2. Por esta razón, se acepta que al volver a operar con PC3 pueda aparecer una **pequeña inconsistencia temporal** o una leve sensación de retroceso en el tiempo dentro de la simulación. Esta limitación se considera aceptable dentro del alcance del proyecto.

---

## 12. Comparación de Rendimiento del Broker

### 12.1. Versión Base

Primera versión del broker en PC1 con una lógica simple y **sin concurrencia interna**. Recibe eventos y los reenvía a PC2 de manera secuencial. Esta es la línea base del experimento de rendimiento.

### 12.2. Versión Modificada con Hilos

Segunda versión del broker que introduce **hilos** para separar la recepción, el encolado y el reenvío de eventos en paralelo.

**Métricas de comparación entre ambas versiones:**

| Métrica | Descripción |
|---|---|
| Cantidad de eventos en BD | Eventos almacenados en la BD en una ventana de **2 minutos**. |
| Latencia de control | Tiempo desde que el usuario solicita una acción hasta que el semáforo cambia. |

Los escenarios de prueba varían el número de sensores y el tiempo entre generación de mediciones (ver Tabla 1 del enunciado del proyecto).
