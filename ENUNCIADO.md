# Proyecto Introducción Sistemas Distribuidos 2026-30
## Gestión Inteligente de Tráfico Urbano

**Facultad de Ingeniería**  
**Departamento de Ingeniería de Sistemas**  
**Introducción a los Sistemas Distribuidos**  
Febrero 2026

---

## 1. Objetivos principales

a. Desarrollar una solución a un problema de estructura distribuida.  
b. Utilizar patrones de comunicación síncronos y asíncronos.  
c. Resolver problemas que se presentan en sistemas distribuidos, tales como fallas en los componentes y persistencia de datos.  
d. Reconocer atributos de calidad (ej. desempeño, resiliencia) asociados a la implementación de un sistema distribuido.

---

## 2. Descripción general

El objetivo del proyecto es diseñar e implementar una plataforma distribuida para la gestión inteligente del tráfico urbano, cuyo propósito es monitorear, analizar y reaccionar ante condiciones de tráfico utilizando múltiples componentes distribuidos que se comunican mediante la biblioteca [ZeroMQ](https://zeromq.org).

El sistema simula una ciudad con intersecciones controladas por semáforos inteligentes y una red de sensores de tráfico (espiras inductivas, cámaras de tráfico y sensores GPS simulados) que generan eventos en tiempo real, relacionados con volumen vehicular, velocidad promedio y nivel de ocupación de las vías. La ciudad se representa con una matriz o cuadrícula de **NxM**, donde N es la fila representada por una letra y M es la columna representada por un número, y usaremos la notación `INT_CK` para representar la intersección de la fila C con la columna K. Por ejemplo, `INT_C5` representa la intersección de la fila C columna 5. Los sensores están ubicados en cada una de las intersecciones.

Los eventos generados son procesados por el servicio de analítica para:

- Recopilar y almacenar información de tráfico.
- Analizar condiciones de congestión vehicular.
- Tomar decisiones de control sobre semáforos.
- Consultar situaciones de tráfico en un determinado momento.
- Emitir acciones de cambio de luz en los semáforos en momentos particulares.

---

## 3. Funcionamiento del sistema y supuestos

Los sensores, eventos generados y servicios serán ubicados en tres máquinas (**PC1**, **PC2** y **PC3**), tal y como se describe a continuación.

**Supuestos:**

- Todas las vías van en un único sentido.
- El cambio de semáforo será únicamente de Verde a Rojo y de Rojo a Verde (no se utiliza el amarillo).

### Componentes PC1

Los sensores de tráfico generan eventos periódicos y los envían de forma asíncrona. Los sensores de tráfico se implementan como procesos simulados que generan eventos a partir de variables aleatorias. Dichos eventos se envían al broker ZeroMQ mediante el patrón **PUB/SUB**, garantizando comunicación asíncrona y desacoplada incluso cuando los componentes se ejecutan en el mismo PC. El broker ZeroMQ actúa como un intermediario de mensajería que desacopla a los productores y consumidores de datos dentro del sistema distribuido. El broker se suscribe a los tres tópicos asociados a los tres tipos de sensores, recibe los eventos generados por los sensores y los envía al nodo de procesamiento y control (**PC2**) en donde se almacenan y analizan.

Existen 3 tipos de sensores: **Espiras inductivas**, **Cámaras de tráfico** y **GPS**; cada uno se encarga de medir un evento en particular:

#### Evento: Sensor tipo Cámara — `EVENTO_LONGITUD_COLA (Lq)`

```json
{
  "sensor_id": "CAM-C5",
  "tipo_sensor": "camara",
  "interseccion": "INT-C5",
  "volumen": 10,
  "velocidad_promedio": 25,
  "timestamp": "2026-02-09T15:10:00Z"
}
```

> `volumen`: Núm. vehículos en espera de cambio de semáforo. `velocidad_promedio`: Velocidad máxima 50 km/h.

#### Evento: Sensor tipo Espira Inductiva — `EVENTO_CONTEO_VEHICULAR (Cv)`

```json
{
  "sensor_id": "ESP-C5",
  "tipo_sensor": "espira_inductiva",
  "interseccion": "INT-C5",
  "vehiculos_contados": 12,
  "intervalo_segundos": 30,
  "timestamp_inicio": "2026-02-09T15:20:00Z",
  "timestamp_fin": "2026-02-09T15:20:30Z"
}
```

> `vehiculos_contados`: Núm. de vehículos que han pasado sobre la espira. `intervalo_segundos`: Cada 30 segundos, coincidiendo con el cambio de semáforo.

#### Evento: Sensor tipo GPS — `EVENTO_DENSIDAD_DE_TRAFICO (Dt)`

```json
{
  "sensor_id": "GPS-C5",
  "nivel_congestion": "ALTA",
  "velocidad_promedio": 18,
  "timestamp": "2026-02-09T15:20:10Z"
}
```

> `nivel_congestion`: Cambia el valor dependiendo de la velocidad promedio: **ALTA** (< 10 km/h), **NORMAL** (entre 11 y 39 km/h), **BAJA** (> 40 km/h).

El grupo del proyecto debe determinar los datos de inicialización de estos procesos, por ejemplo: posición en la ciudad, cuadrículas que se abarcan, tiempo entre generación de un evento y otro, etc.

### Componentes PC2

El **servicio de analítica** se suscribe a los eventos generados por los sensores (PUB/SUB) vía el bróker ZMQ, recibe y procesa los datos para detectar congestión o anomalías a partir de reglas simples y envía la información directamente a la Base de Datos usando el patrón **PUSH/PULL**. Si se detecta una condición relevante (por ejemplo, dar prioridad al paso de una ambulancia), se generan eventos de control y se toman decisiones, como extender la fase verde de un semáforo. Para comunicar cambios en los semáforos, el servicio de analítica se comunica de forma asíncrona con el servicio de control de semáforos, enviando comandos de control que son ejecutados sin bloquear el procesamiento de otros eventos. Eventualmente el servicio de analítica puede recibir indicaciones directas del módulo de Monitoreo y consulta ubicado en el PC3, emitidas por un usuario para obligar a un cambio de estado de los semáforos, independiente de los datos generados por los sensores. Este servicio imprimirá por pantalla mensajes que indiquen si, de acuerdo con reglas, el tráfico es normal, hay congestión, etc. y qué acciones se van a tomar si es el caso.

El **servicio de control de semáforos** ajusta el estado de los semáforos simulados cambiando de luz roja a verde y viceversa, de acuerdo con las órdenes recibidas del servicio de analítica. El servicio debe imprimir por pantalla las operaciones que va realizando.

La **base de datos réplica**, localizada en el PC2, es actualizada constantemente de forma asíncrona, con el fin de servir de backup en caso de que ocurra un fallo en el PC3.

### Componentes PC3

El **servicio de monitoreo y consulta** permite a un usuario consultar el estado del sistema o enviar indicaciones directas al módulo de analítica. Con estas indicaciones directas se puede forzar el cambio de estado del sistema, por ejemplo, para priorizar el paso de una ambulancia. Se pueden hacer consultas históricas entre periodos de tiempo (ej. horas pico) y consultas puntuales de información en una intersección en particular utilizando el patrón de comunicación **REQ/REP**. Como en el caso de todos los servicios anteriores, el servicio de monitoreo y consulta debe imprimir todas las operaciones que va realizando.

---

## 4. Arquitectura general del sistema

Teniendo en cuenta las variables que miden los sensores:

- **Espiras inductivas** → conteo vehicular V (veh/min)
- **Cámara** → longitud de cola Q (Núm. Vehículos)
- **GPS** → densidad y velocidad promedio D, Vp (veh/km, km/h)

Se deben definir rangos de condiciones normales de tráfico para establecer reglas simples. Por ejemplo, para tráfico normal se podría establecer:

```
Q < 5  AND  Vp > 35  AND  D < 20
```

Cada grupo puede generar diferentes reglas, siempre y cuando cumplan con los parámetros establecidos y tengan un sentido lógico dentro del sistema.

El tiempo de espera para que la luz roja cambie a verde en condiciones normales es de **15 segundos**. Se deben establecer estados de circulación para:

- Tráfico normal
- Detección de congestión
- Priorización de una vía (ola verde)

El servicio de analítica recibe la información y dependiendo de las reglas, realiza los cambios de luz verde o de la luz roja (no hay transición con luz amarilla) o aumenta los tiempos de permanencia del semáforo en un determinado estado, dependiendo de la condición.

Los usuarios también pueden solicitar al servidor de consulta y monitoreo el cambio a luz verde de los semáforos de una vía en casos especiales, por ejemplo, el paso de una ambulancia.

> **Nota:** El grupo puede escoger de la biblioteca ZeroMQ el patrón asíncrono que más se adapte al problema planteado.

### Almacenamiento y Persistencia

La base de datos principal se encuentra en el **PC3** y la réplica en el **PC2**. El servicio de analítica reenvía toda la información a las dos bases de datos utilizando un patrón de comunicación asíncrono, con el fin de mantener la persistencia y permitir consultas de estado de la red de semaforización.

### Procesos y número de computadores

- La implementación debe corresponder a la arquitectura planteada con los correspondientes patrones de comunicación entre componentes.
- Es obligatorio usar la biblioteca **ZeroMQ** para las comunicaciones entre los diferentes procesos del proyecto.
- Cada grupo debe definir las reglas para los 3 estados (Tráfico normal, congestión, priorización) y sincronizar el sistema de semaforización, así como las consultas de los usuarios al servicio de monitoreo y las posibles operaciones para cambios de estado, con sus parámetros.

### Fallas

En la implementación se debe considerar una posible **falla del PC3**. Si esto ocurre, todos los procesos deben comenzar a usar inmediatamente la réplica de la base de datos que se encuentra en el PC2. La operación será transparente para el cliente; el sistema debe continuar operando de forma ininterrumpida.

### Evaluación

El día de la sustentación es importante que se pueda observar:

- Estado de la BD (original y réplica) y cómo va quedando a medida que se dan los cambios de estado.
- Operaciones que se van realizando sobre la semaforización de acuerdo con las diferentes reglas.
- Se debe poder consultar los estados de congestión históricos y las situaciones puntuales de priorización de semaforización.

---

## 5. Medidas de rendimiento

Una vez implementado el proyecto, el equipo realizará pruebas para comparar el diseño original con un diseño modificado que utiliza **hilos en el servicio BrokerZMQ**.

### Tabla 1 — Escenarios de prueba y variables a medir

| Escenario | Diseño original | Diseño multihilos |
|---|---|---|
| **Variables independientes** | Número de sensores generando información y tiempo entre generación de mediciones | Igual |
| **Variables dependientes** | - Cantidad de solicitudes almacenadas en la BD en un intervalo de 2 min. <br> - Tiempo desde que el usuario solicita una acción hasta que el semáforo cambia. | Igual |
| 1 sensor de cada tipo, datos cada 10 seg | ✓ | ✓ |
| 2 sensores de cada tipo, datos cada 5 seg | ✓ | ✓ |

Rellene la Tabla 1 y realice gráficos de las variables dependientes en función de los factores o variables independientes. Comente los resultados obtenidos. ¿Qué diseño es más escalable? Justifique su respuesta en función de los resultados.

---

## 6. Primera Entrega (15%)

**Fecha de sustentación:** Viernes 10 de abril de 2026 (horario de la clase). **Semana 10.**

La primera entrega consta de un informe donde se debe especificar:

- **Modelos del sistema** (Arquitectónico, interacción, fallos y seguridad). Cómo se aplican los conceptos de estos modelos al proyecto.
- **Diseño de TODO el sistema:** Diagrama de despliegue, Diagrama de componentes, Diagrama de clases y Diagrama de secuencia. Este diseño debe incluir el o los componentes para enmascarar las fallas del sistema.
- En el informe debe explicar:
  - **A.** Cómo los procesos obtendrán la definición inicial de los recursos: número y tipo de sensores, tamaño de la matriz, número de semáforos, etc.
  - **B.** Reglas, tipos de consulta que harán los usuarios y ejemplos de indicaciones directas que le hará el servicio de Monitoreo al servicio de analítica.
- El **protocolo de pruebas** que utilizará para la entrega final (considere todos los tipos de prueba que deben realizarse a un sistema), haciendo énfasis en las pruebas de desempeño.
- **Estrategias** para obtener las métricas de desempeño de la Tabla 1.
- **Implementación** de los servicios del PC1 y PC2 y actualizaciones a la BD principal en el PC3.
- Cada equipo dispone de **15 minutos** para mostrar sus resultados y responder preguntas del profesor.

---

## 7. Segunda Entrega (15%)

**Fecha de sustentación:** Viernes 29 de mayo (horario de clases). **Semana 17.** Presencial, con todos los integrantes del grupo.

La entrega se compone de:

- **Código fuente** en archivo comprimido `.zip` con un archivo `README` indicando cómo ejecutarlo. No debe haber objetos ni ejecutables.
- **Documentación** complementaria a la primera entrega. Los archivos fuente deben estar documentados.
- **Video de máximo 10 minutos** que explique:
  - Distribución de componentes en máquinas.
  - Parámetros de todos los tipos de procesos.
  - Cómo se distribuye la cuadrícula de la ciudad entre los diferentes sensores.
  - Cómo se asignan los semáforos.
  - Bibliotecas y patrones usados.
  - Tratamiento de los fallos.
- **Informe de máximo 5 páginas** con los experimentos realizados y resultados obtenidos, incluyendo especificaciones de HW/SW, herramientas de medición, tablas, gráficos y análisis de resultados.

> **Equipos de trabajo:** Máximo **3 personas**. No puede existir replicación de documentos ni de código fuente entre grupos (se consideraría plagio).

---

## 8. Calificación Primera Entrega (15%)

### Tabla 2 — Guía de valoración Primera Entrega

| Indicador | Pts. | Excelente | Competente | Deficiente |
|---|---|---|---|---|
| Informe (presentación, ortografía, completitud) | 1.00 | 1.00 | < 1.00, ≥ 0.50 | < 0.50 |
| Diseño del proyecto | 1.50 | [1.00, 1.50] | [0.25, 1.00] | < 0.25 |
| Protocolo de pruebas | 0.50 | 0.50 | 0.25 | < 0.25 |
| Modelos del sistema (fallas, interacción, seguridad) | 0.25 | 0.25 | 0.15 | < 0.15 |
| Obtención de las métricas de rendimiento | 0.25 | 0.25 | 0.15 | < 0.15 |
| Implementación inicial | 1.50 | [1.00, 1.50] | [0.75, 1.00] | < 0.75 |
| **Total** | **5.00** | | | |

### Tabla 3 — Descripción de rúbricas, Primera Entrega

| Indicador | Excelente | Competente | Deficiente |
|---|---|---|---|
| **Informe** | Presentación impecable, sin problemas de ortografía o redacción. Contiene todos los aspectos solicitados. | Fallas menores en presentación, ortografía y/o redacción. Contiene todos los aspectos. | Fallas importantes en presentación y/o redacción. No contiene todos los aspectos solicitados. |
| **Diseño del Proyecto** | Todos los artefactos exigidos: diagrama de componentes, clases, secuencia y despliegue. Incluye tolerancia a fallas y persistencia. Diagramas correctos. | Diagramas incompletos o algunos incorrectos. | No se realizan los diagramas exigidos o están incorrectos. No se considera todo el sistema. |
| **Protocolo de pruebas** | Las pruebas son suficientes para evaluar la funcionalidad con y sin presencia de fallas. | No se contemplan todas las pruebas importantes. Está incompleto. | No se presenta protocolo de pruebas funcionales. |
| **Modelos de sistema** | Descripción de los modelos fundamentales adaptados al proyecto. | Se describen parcialmente los modelos fundamentales. | No se presentan los modelos o la descripción no está relacionada con el proyecto. |
| **Métricas de rendimiento** | Se describen de forma clara y completa las herramientas y/o metodología para obtener las métricas. | No está suficientemente claro el procedimiento para obtener los valores de las métricas. | No se menciona ni el procedimiento ni las herramientas para obtener las métricas. |
| **Implementación inicial** | Todas las funcionalidades requeridas están implementadas correctamente. El sistema funciona en más de un computador (físico o virtual). | Solo 2 de los siguientes aspectos implementados correctamente: solicitud de operaciones, mecanismo para generar requerimientos, ejecución en 2 máquinas. | Falencias en 2 o más de los puntos mencionados. |

---

## 9. Calificación Segunda Entrega (25%)

- **Informe de rendimiento:** 10% (evaluado sobre 5 pts)
- **Resto de la entrega** (ejecución, sustentación, etc.): 15%

### Tabla 4 — Guía de valoración Segunda Entrega (Informe)

| Indicador | Pts. | Excelente | Competente | Deficiente |
|---|---|---|---|---|
| Informe (presentación, ortografía, completitud) | 1.00 | 0.75 | 0.50 | < 0.50 |
| Presentación de datos en tablas y gráficos correctamente construidos | 2.00 | [1.00, 2.00] | [0.50, 1.00] | < 0.50 |
| Análisis de resultados y conclusiones cónsonas | 2.00 | [1.00, 2.00] | [0.50, 1.00] | < 0.50 |
| **Total** | **5.00** | | | |

### Tabla 5 — Guía de valoración Sustentación

| Indicador | Pts. | Excelente | Competente | Deficiente |
|---|---|---|---|---|
| Todos los sensores implementados correctamente | 0.50 | 0.50 | [0.25, 0.50] | < 0.25 |
| Servicios en PC1: ZeroMQ | 0.75 | [0.50, 0.75] | [0.25, 0.50] | < 0.25 |
| Servicios en PC2: Analítica y control de semáforos | 0.75 | [0.50, 0.75] | [0.25, 0.50] | < 0.25 |
| Servicios en PC3: Consulta y monitoreo | 0.50 | 0.50 | [0.25, 0.50] | < 0.25 |
| Persistencia y actualización de réplicas | 0.25 | 0.25 | 0.15 | < 0.15 |
| Ejecución remota desde 3 computadores | 0.75 | [0.50, 0.75] | [0.25, 0.50] | < 0.25 |
| Tratamiento de fallas | 0.75 | [0.50, 0.75] | [0.25, 0.50] | < 0.25 |
| Repositorio, código y documentación | 0.50 | 0.50 | [0.25, 0.50] | < 0.25 |
| Presentación/Video | 0.25 | 0.25 | 0.15 | < 0.15 |
| **Total** | **5.00** | | | |

### Tabla 6 — Descripción de rúbricas, Segunda Entrega

| Indicador | Excelente | Competente | Deficiente |
|---|---|---|---|
| **Implementación de procesos/sensores** | Procesos implementados correctamente según las especificaciones. Fácil parametrización (tamaño de la matriz, tiempo de generación, etc.). | Deficiencias en: comportamiento del proceso, patrón de comunicación o parametrización. La mayoría (no todos) implementados correctamente. | Dos o más de los tres aspectos funcionan incorrectamente o incompleto. |
| **Persistencia / actualización de réplicas** | Campos de BD adecuados. Todas las actualizaciones correctas. La réplica se actualiza según el enunciado. | Pequeños problemas en la actualización de datos o réplicas. | No se implementa la persistencia o no se implementa la réplica. |
| **Ejecución remota desde 3 CPUs** | Sistema funciona en al menos tres computadoras (o máquinas virtuales) según la arquitectura del enunciado. | Sistema funciona solo en dos computadoras y/o máquinas virtuales. | Todos los componentes se instalan y funcionan en una sola computadora. |
| **Tratamiento de fallas del PC3** | Ante la falla del PC3, todos los procesos se reconectan con la réplica automáticamente (health check). Los estudiantes explican los patrones de resiliencia. | El sistema queda funcionando parcialmente. La falla no se detecta automáticamente. No se explican claramente los patrones de resiliencia. | No se implementa la tolerancia a fallas del servicio en PC3. |
| **Código** | Bien estructurado, indentación correcta y documentado (archivos, funciones, métodos, algoritmos). | Funcional pero con alguno de estos problemas: documentación, estructura o sangrado. | Deficiente, sin orden ni documentación. |
| **Sustentación / video** | Se siguen todas las reglas, se presentan todos los elementos importantes y se responden adecuadamente las preguntas. El video evidencia claramente la arquitectura, funcionamiento y tolerancia a fallas. | Falla menor en uno o dos de: reglas de sustentación, funcionalidades, respuesta a preguntas, o video insuficiente. | Fallas importantes en tres o más de los elementos evaluados. El video es deficiente o no se adjunta. |
