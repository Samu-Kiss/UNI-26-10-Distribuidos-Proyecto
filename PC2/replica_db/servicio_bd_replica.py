from __future__ import annotations

from pathlib import Path

import zmq

from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log
from common.utilidades.persistencia_sqlite import RepositorioSQLite


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    repositorio = RepositorioSQLite(raiz / "PC2/replica_db/bd_replicada.sqlite3")
    repositorio.inicializar_pc2()

    contexto = zmq.Context()
    receptor = contexto.socket(zmq.PULL)
    receptor.bind(config["zmq"]["pc2"]["ingesta_replicada"])
    sincronizador = contexto.socket(zmq.REP)
    sincronizador.bind(config["zmq"]["pc2"]["sincronizacion_estado"])
    poller = zmq.Poller()
    poller.register(receptor, zmq.POLLIN)
    poller.register(sincronizador, zmq.POLLIN)

    log("PC2-ReplicaDB", "Servicio de replica operativa iniciado.")
    while True:
        eventos = dict(poller.poll())
        if receptor in eventos:
            mensaje = receptor.recv_json()
            tipo = mensaje["tipo"]
            datos = mensaje["datos"]
            if tipo == "snapshot_operativo":
                repositorio.guardar_snapshot_operativo(datos)
                log("PC2-ReplicaDB", "Snapshot operativo replicado.")

        if sincronizador in eventos:
            solicitud = sincronizador.recv_json()
            tipo_solicitud = solicitud.get("tipo")
            if tipo_solicitud == "solicitar_snapshot_operativo":
                snapshot = repositorio.reconstruir_snapshot_operativo_actual()
                sincronizador.send_json({"ok": snapshot is not None, "snapshot_operativo": snapshot})
                log("PC2-ReplicaDB", "Solicitud de sincronizacion atendida.")
                continue
            sincronizador.send_json({"ok": False, "error": "tipo_no_soportado"})


if __name__ == "__main__":
    main()
