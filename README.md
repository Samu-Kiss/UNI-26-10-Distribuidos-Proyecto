# Proyecto de Gestion Inteligente de Trafico Urbano

Sistema distribuido para simular trafico urbano, generar eventos de sensores, calcular prioridad semaforica y exponer una interfaz web operativa con tolerancia a fallas sobre ZeroMQ.

[Link al video](https://www.youtube.com/watch?v=30Cp6jj9Mqo)

[Link al doc](https://github.com/Samu-Kiss/UNI-26-10-Distribuidos-Proyecto/blob/main/docs%2FDocumentosLatex%2FProtocoloDePruebas%2FProtocolo%20De%20Pruebas.pdf)

## Componentes

- `PC0`: simulacion autoritativa del mapa, vehiculos, ambulancias y base historica.
- `PC1`: broker ZeroMQ y simulacion/logica de sensores.
- `PC2`: analitica, decisiones semaforicas, control manual y replica de estado.
- `PC3`: base principal, backend principal y frontend web local.
- `common`: modelos, contratos de mensajes, persistencia, cliente failover y utilidades compartidas.

## Requisitos

- Python 3.10 o superior.
- Dependencias de `requirements.txt`.

Instalacion local:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuracion

La configuracion central esta en:

```text
config/system_config.json
```

Desde ahi se controlan, entre otros:

- tamano de ciudad y semilla del mapa;
- tick real y reloj simulado;
- modo de bucle infinito;
- generacion de vehiculos;
- pesos de analitica;
- host/puerto del frontend de PC3;
- endpoints ZeroMQ.

## Arranque recomendado

Abre 4 terminales en la raiz del repo y ejecuta:

### PC0

```bash
bash scripts/start_pc0.sh
```

### PC1

```bash
bash scripts/start_pc1.sh
```

### PC2

```bash
bash scripts/start_pc2.sh
```

### PC3

```bash
bash scripts/start_pc3.sh
```

`PC3` imprime un `localhost` con la interfaz web.

## Arranque manual

Si no quieres usar scripts:

```bash
export PYTHONPATH=$(pwd)
python3 -m PC0.historic_db.servicio_bd_historica
python3 -m PC0.simulation.servicio_simulacion
python3 -m PC1.broker.broker_mq
python3 -m PC1.sensors.simulador_sensores
python3 -m PC2.replica_db.servicio_bd_replica
python3 -m PC2.backend_respaldo.servicio_backend_respaldo
python3 -m PC2.analytics.servicio_analitica
python3 -m PC3.main_db.servicio_bd_principal
python3 -m PC3.backend.servicio_backend_principal
```

## Interfaz web de PC3

La interfaz vive en:

- `PC3/frontend/servidor.py`
- `PC3/frontend/static/index.html`
- `PC3/frontend/static/styles.css`
- `PC3/frontend/static/app.js`

Permite:

- ver el estado de la ciudad en tiempo real;
- inspeccionar vias, nodos y vehiculos desde el panel derecho;
- abrir el panel de informacion global de simulacion;
- solicitar ambulancias;
- aplicar control manual sobre una interseccion.

### Ambulancias

- Se solicitan desde PC3.
- Se crean realmente en PC0.
- El nodo debe ser un `BORDE-X-X` valido con spawn.
- Mientras una ambulancia ocupa una via, esa via fuerza `score = 1.0`.

### Control manual

- Solo una interseccion puede quedar en manual a la vez.
- Se puede forzar `HORIZONTAL`, `VERTICAL` o volver a `AUTO`.
- El control manual queda activo hasta nueva orden.

## Cliente con failover

`common/utilidades/cliente_backend_failover.py` intenta primero el backend principal de `PC3` y, si falla, consulta el backend de respaldo de `PC2`.

Ejemplo:

```bash
python3 - <<'PY'
from common.utilidades.cliente_backend_failover import ClienteBackendFailover

cliente = ClienteBackendFailover()
print(cliente.solicitar({"tipo": "salud"}))
print(cliente.solicitar({"tipo": "resumen_estado"}))
print(cliente.solicitar({"tipo": "estado_interseccion", "interseccion": "INT-A1"}))
print(cliente.solicitar({"tipo": "estado_via", "via_id": "VIA-BORDE-O-A-A-INT-A1"}))
print(cliente.solicitar({"tipo": "listar_ambulancias"}))
PY
```

Operaciones activas validas contra el backend principal:

```json
{"tipo": "crear_ambulancia", "nodo_origen": "BORDE-N-1"}
{"tipo": "control_manual", "interseccion": "INT-A1", "fase_ganadora": "HORIZONTAL", "duracion_ticks": -1}
{"tipo": "control_manual", "interseccion": "INT-A1", "fase_ganadora": "AUTO", "duracion_ticks": 0}
```

## Limpieza de bases

```bash
bash scripts/limpiar_bases.sh
```

Limpia las SQLite de:

- `PC0/historic_db/`
- `PC2/replica_db/`
- `PC3/main_db/`

## Documentacion

- `docs/enunciado.md`
- `docs/diagramas.md`
- `docs/decisiones_de_diseno.md`
- `docs/bitacora_diseno.txt`
- `docs/DocumentosLatex/decisiones_diseno.pdf`

## Estado del README

Este README queda publicado como Markdown real en `README.md`, que es la opcion correcta para renderizado consistente en GitHub.
