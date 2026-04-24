# Proyecto de Gestión Inteligente de Tráfico Urbano (Sistemas Distribuidos)

Sistema distribuido para simular tráfico urbano, generar eventos de sensores en tiempo real, tomar decisiones de semaforización y exponer un backend con tolerancia a fallas usando **ZeroMQ**.

## Arquitectura

El sistema está dividido en 4 nodos lógicos:

- **PC0**: simulación de ciudad + base histórica.
- **PC1**: sensores (cámara, espira, gps) + broker ZeroMQ.
- **PC2**: analítica, control de semáforos, réplica de BD y backend de respaldo.
- **PC3**: base principal y backend principal para consultas/operaciones.

Código compartido:

- `common/modelos`: modelos de simulación/tráfico.
- `common/mensajes`: contratos de mensajes.
- `common/utilidades`: configuración, persistencia SQLite, failover y utilidades ZMQ.

## Tecnologías

- Python 3
- ZeroMQ (`pyzmq`)
- SQLite

## Estructura del repositorio

- `PC0/`, `PC1/`, `PC2/`, `PC3/`: servicios por nodo.
- `common/`: lógica reutilizable.
- `config/system_config.json`: parámetros de simulación y endpoints.
- `scripts/`: arranque por nodo y limpieza de BDs.
- `docs/`: enunciado, decisiones de diseño y diagramas.

## Requisitos

1. Python 3.10+ (recomendado).
2. Instalar dependencias:

```bash
cd /home/runner/work/UNI-26-10-ProyectoDistribuidos/UNI-26-10-ProyectoDistribuidos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

Toda la configuración está en:

- `/home/runner/work/UNI-26-10-ProyectoDistribuidos/UNI-26-10-ProyectoDistribuidos/config/system_config.json`

Ahí puedes ajustar:

- Tamaño de la cuadrícula de ciudad.
- Parámetros de simulación (tick, probabilidad, velocidades).
- Tipos/frecuencia de sensores.
- Pesos de analítica.
- Endpoints ZeroMQ por cada PC.

## Ejecución rápida (recomendado)

Abre **4 terminales** en la raíz del repo y ejecuta:

### Terminal 1 (PC0)
```bash
bash scripts/start_pc0.sh
```

### Terminal 2 (PC1)
```bash
bash scripts/start_pc1.sh
```

### Terminal 3 (PC2)
```bash
bash scripts/start_pc2.sh
```

### Terminal 4 (PC3)
```bash
bash scripts/start_pc3.sh
```

> Los scripts exportan `PYTHONPATH` automáticamente y levantan los servicios del nodo.

## Ejecución manual (alternativa)

Desde la raíz del repositorio:

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

## Cliente con failover (ejemplo)

`common/utilidades/cliente_backend_failover.py` intenta primero PC3 y, si falla, usa PC2 automáticamente.

Ejemplo rápido:

```bash
python3 - <<'PY'
from common.utilidades.cliente_backend_failover import ClienteBackendFailover

cliente = ClienteBackendFailover()
print(cliente.solicitar({"tipo": "salud"}))
print(cliente.solicitar({"tipo": "resumen_estado"}))
print(cliente.solicitar({"tipo": "estado_interseccion", "interseccion": "INT-A1"}))
print(cliente.solicitar({"tipo": "estado_via", "via_id": "VIA-N1-INT-A1"}))
print(cliente.solicitar({"tipo": "listar_ambulancias"}))
PY
```

Operaciones activas (solo backend principal PC3):

- `{"tipo": "crear_ambulancia", "nodo_origen": "N1", "velocidad": 45}`
- `{"tipo": "control_manual", "interseccion": "INT-A1", "fase_ganadora": "HORIZONTAL", "duracion_ticks": 5}`

## Limpieza de bases de datos

```bash
bash scripts/limpiar_bases.sh
```

El script elimina:

- `PC0/historic_db/bd_historica.sqlite3`
- `PC2/replica_db/bd_replicada.sqlite3`
- `PC3/main_db/bd_principal.sqlite3`

## Documentación adicional

- `docs/enunciado.md`
- `docs/diagramas.md`
- `docs/decisiones_de_diseno.md`

---

Si quieres, también te puedo dejar una versión más corta del README (tipo entrega final) o una versión con capturas y flujo de pruebas de rendimiento.
