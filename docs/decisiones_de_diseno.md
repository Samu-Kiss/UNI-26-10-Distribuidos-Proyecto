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
- Tiempos base de alternancia semafórica (por defecto, **15 segundos** en condiciones normales).
- Reglas y umbrales que definen los estados de tráfico (normal, congestión, priorización).
- Pesos de ponderación de cada sensor para el cálculo del score.
- Parámetros del reloj de simulación (hora de inicio, hora de fin, factor de aceleración).
- Parámetros de generación de vehículos en PC0 (tasa de ingreso, velocidades, etc.).

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

### 4.2. Cámara

La cámara mide la acumulación o cola de vehículos y aporta una señal de ocupación inmediata. Sus datos salen de leer la cantidad de vehículos en espera en la arista o acceso observado (`EVENTO_LONGITUD_COLA`, **Lq**).

### 4.3. Espira Inductiva

La espira inductiva mide el flujo de vehículos que pasan por un punto de control en un intervalo de tiempo y aporta una señal de presión de tráfico. Sus datos salen de contar cruces vehiculares en la arista durante una ventana de tiempo configurable (`EVENTO_CONTEO_VEHICULAR`, **Cv**).

### 4.4. GPS

El sensor GPS mide la velocidad promedio de los vehículos presentes en una arista y aporta una señal complementaria de fluidez o lentitud (`EVENTO_DENSIDAD_DE_TRAFICO`, **Dt**). El GPS **no se usa como criterio único** para cambiar semáforos, sino como un componente ponderado dentro del score total.

### 4.5. Relación entre Sensores y Aristas

Los sensores simulados en PC1 están definidos sobre aristas o accesos y consultan el estado de los vehículos mantenido por PC0 para generar eventos realistas. Cada sensor actúa como un getter especializado del estado de una vía: toma atributos del tramo observado, los procesa según su tipo y publica la estadística resultante.

---

## 5. Lógica de Analítica y Semáforos

### 5.1. Score por Vía

La lógica de control semafórico se basa en una **calificación de estado (score)** para cada vía de entrada a una intersección. Ese score solo describe la carga del tráfico antes del semáforo y en el único sentido permitido de la vía. Cada sensor aporta al score con una ponderación configurable. Entre mayor sea el score, mayor será la prioridad para recibir verde. El valor final queda normalizado en **[0, 1]**.

### 5.2. Pesos y Normalización

Cada sensor produce primero una nota normalizada entre 0 y 1. Después, esas tres notas se combinan con pesos configurables para obtener un score final, también entre 0 y 1.

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

### 6.4. Ambulancia

Desde PC3 el usuario puede crear manualmente una ambulancia en un nodo de salida. La ambulancia cuenta como un vehículo más, pero con una representación visual distinta y una velocidad constante configurable. A medida que avanza, el usuario puede intervenir manualmente los semáforos desde PC3 para abrirle paso. La ambulancia sale del sistema al llegar a un nodo de salida.

---

## 7. Distribución por Computadores

### 7.1. PC0

> **Extensión propuesta al grupo de computadores.** PC0 es el generador de vehículos simulados y mantiene el estado base del tráfico.

Responsabilidades:

- Generar vehículos que ingresan a la ciudad por nodos de borde.
- Mantener y actualizar la posición de cada vehículo en el grafo.
- Instanciar ambulancias cuando PC3 lo solicite por ZeroMQ.
- Comunicar el estado de los vehículos en el grafo-mapa a la base de datos principal de PC3, a la réplica de PC2 y a su propia base histórica en PC0.
- Almacenar el historial completo de un día de simulación para estadísticas finales.

> PC0 **no** forma parte del mecanismo principal de respaldo cuando ocurre una falla; su almacenamiento histórico es para análisis posterior.

### 7.2. PC1

Responsabilidades:

- Ejecutar los sensores simulados (cámara, espira inductiva y GPS) como procesos lógicos asociados a aristas que generan eventos periódicos.
- Publicar eventos mediante **PUB/SUB** de ZeroMQ, con tópicos diferenciados por tipo de sensor.
- Operar el **broker ZeroMQ** que recibe los eventos y los reenvía a PC2.

### 7.3. PC2

Responsabilidades:

- Suscribirse a los eventos de sensores vía el broker de PC1.
- Calcular el score por vía y determinar la fase semafórica de cada intersección.
- Ejecutar órdenes de control sobre semáforos e imprimir por pantalla las acciones realizadas.
- Recibir y ejecutar indicaciones de control manual provenientes de PC3.
- Mantener la **réplica de la base de datos**, actualizada de forma asíncrona, para que el sistema pueda seguir operando si PC3 falla.

### 7.4. PC3

Responsabilidades:

- Alojar la **base de datos principal**.
- Proveer monitoreo y consulta del estado actual y del histórico disponible mediante **REQ/REP**.
- Enviar indicaciones directas al servicio de analítica para forzar cambios semafóricos.
- Visualizar la ciudad como grafo sobre cuadrícula, con vías coloreadas según congestión e indicadores de fase activa.
- Gestionar el reloj de simulación (aceleración y ralentización).
- Permitir al usuario crear ambulancias en nodos de salida.

---

## 8. Persistencia y Tiempo de Simulación

### 8.1. Base de Datos en PC3

La base de datos principal reside en PC3. Almacena el estado operativo de la ciudad en tiempo real: estado de semáforos, eventos de sensores, acciones de control y el estado actualizado de los vehículos dentro del grafo-mapa.

### 8.2. Réplica en PC2

La réplica se encuentra en PC2 y se actualiza de forma **asíncrona** (PUSH/PULL u otro patrón similar). Su propósito es mantener el estado operativo actual de la ciudad, incluyendo el estado reportado de los vehículos, para que el sistema pueda seguir funcionando si PC3 falla. PC2 no es un almacén de resultados históricos de largo plazo; es un **respaldo del estado presente**.

Si PC3 cae, la operación cambia a la base de datos de PC2. Cuando PC3 vuelve a estar disponible, su base de datos se sincroniza con el estado de PC2 y, una vez finalizada esa sincronización, el sistema vuelve a operar usando PC3 como base principal.

### 8.3. Histórico Diario en PC0

PC0 almacena el historial completo de un día de simulación para análisis posterior y estadísticas finales. En esta base también queda registrado el estado de los vehículos a lo largo del día simulado. PC0 **no** se utiliza como nodo de resiliencia operativa; su rol es exclusivamente analítico.

### 8.4. Reloj de Simulación

El sistema comparte un **reloj global de simulación** que representa un día de **12:00 a 18:00**. Por defecto:

- **1 segundo real = 1 minuto simulado.**
- Un cambio semafórico normal de 15 segundos en tiempo real equivale a 15 minutos dentro de la ciudad simulada.

Desde PC3 esta relación puede acelerarse o ralentizarse. Todos los eventos (sensores, vehículos, semáforos y persistencia) usan el tiempo de simulación. El histórico en PC0 se indexa con este reloj.

---

## 9. Interacción entre Componentes

### 9.1. Flujo General del Sistema

```
1. PC0  → Genera vehículos y mantiene el estado base del tráfico.
2. PC0  → Comunica el estado de los vehículos a PC3 (BD principal),
           PC2 (réplica operativa) y PC0 (base histórica).
3. PC1  → Ejecuta sensores y publica eventos a través del broker ZeroMQ.
4. PC2  → Se suscribe a los eventos, calcula analítica, revisa conflictos
           de las intersecciones y determina fases semafóricas.
5. PC3  → Permite monitorear, consultar y emitir indicaciones de control manual.
```

### 9.2. Creación de Ambulancias

Cuando el usuario crea una ambulancia desde PC3:

1. PC3 envía la solicitud por ZeroMQ a PC0, indicando el nodo de salida donde debe aparecer la ambulancia.
2. PC0 instancia la ambulancia como una entidad vehicular especial dentro de la simulación.
3. PC3 la visualiza con una representación diferenciada (por ejemplo, icono de sirena) respecto al tráfico normal.

### 9.3. Priorización Manual de Semáforos

Cuando el usuario fuerza un semáforo desde PC3:

1. PC3 envía la orden al servicio de analítica/control en PC2.
2. La orden indica qué intersección y qué dirección o conflicto priorizar, y por cuánto tiempo de simulación mantener el forzado.
3. PC2 ejecuta el forzado, suspendiendo temporalmente la lógica automática en esa intersección.
4. Al finalizar el período indicado, la intersección regresa automáticamente al control por score.

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

---

## 11. Fallos y Continuidad Operativa

### 11.1. Caída de PC3

La falla principal considerada es la **caída de PC3**. Si PC3 falla, se pierden temporalmente:

- Visualización en tiempo real del mapa de la ciudad.
- Monitoreo interactivo y consultas desde la interfaz de usuario.
- Creación de nuevas ambulancias.
- Emisión de órdenes manuales de priorización semafórica.

### 11.2. Continuidad con PC2

Ante la caída de PC3, el sistema sigue operando con la **réplica en PC2**. Los componentes (analítica, sensores y control semafórico) cambian a la réplica y continúan funcionando. La operación es **transparente** para los procesos internos.

Si PC3 se vuelve a levantar, se sincroniza su base de datos con el estado actual de PC2 y, al terminar esa actualización, la operación vuelve automáticamente a PC3 como base principal.

### 11.3. Limitaciones Durante la Falla

Durante la falla de PC3, las siguientes funcionalidades quedan **indisponibles**:

- No se pueden crear nuevas ambulancias desde la interfaz.
- No se pueden emitir nuevas órdenes manuales de priorización semafórica.
- Se pierde la visualización y el monitoreo interactivo.

> **Nota:** PC0 no participa en el cambio a un respaldo cuando ocurre una falla. El escenario de resiliencia es: PC3 cae → el sistema sigue operando con la réplica de PC2.

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
