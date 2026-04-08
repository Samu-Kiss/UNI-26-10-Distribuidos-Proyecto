from __future__ import annotations

from pathlib import Path

import zmq

from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log
from common.utilidades.persistencia_sqlite import RepositorioSQLite


def sincronizar_desde_replica(
    contexto: zmq.Context,
    config: dict[str, object],
    repositorio: RepositorioSQLite,
) -> None:
    solicitante = contexto.socket(zmq.REQ)
    solicitante.setsockopt(zmq.LINGER, 0)
    solicitante.setsockopt(zmq.RCVTIMEO, 1500)
    solicitante.setsockopt(zmq.SNDTIMEO, 1500)
    solicitante.connect(config["zmq"]["pc2"]["sincronizacion_estado"])
    try:
        solicitante.send_json({"tipo": "solicitar_snapshot_operativo"})
        respuesta = solicitante.recv_json()
    except zmq.ZMQError:
        log("PC3-MainDB", "No fue posible sincronizar desde la replica al arrancar.")
        solicitante.close()
        return
    solicitante.close()

    snapshot = respuesta.get("snapshot_operativo")
    if not respuesta.get("ok") or snapshot is None:
        log("PC3-MainDB", "La replica no entrego un snapshot para resincronizacion.")
        return

    repositorio.guardar_snapshot_operativo(snapshot)
    log(
        "PC3-MainDB",
        f"Base principal resincronizada desde replica con tick {snapshot['tick_actual']}.",
    )


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    repositorio = RepositorioSQLite(raiz / "PC3/main_db/bd_principal.sqlite3")
    repositorio.inicializar_pc3()

    contexto = zmq.Context()
    sincronizar_desde_replica(contexto, config, repositorio)
    receptor = contexto.socket(zmq.PULL)
    receptor.bind(config["zmq"]["pc3"]["ingesta_principal"])

    log("PC3-MainDB", "Servicio de base principal iniciado.")
    while True:
        mensaje = receptor.recv_json()
        tipo = mensaje["tipo"]
        datos = mensaje["datos"]
        if tipo == "snapshot_operativo":
            repositorio.guardar_snapshot_operativo(datos)
            log("PC3-MainDB", f"Persistido mensaje de tipo {tipo}.")


if __name__ == "__main__":
    main()
