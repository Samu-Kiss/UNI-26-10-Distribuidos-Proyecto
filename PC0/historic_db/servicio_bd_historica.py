from __future__ import annotations

from pathlib import Path

import zmq

from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log
from common.utilidades.persistencia_sqlite import RepositorioSQLite


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    repositorio = RepositorioSQLite(raiz / "PC0/historic_db/bd_historica.sqlite3")
    repositorio.inicializar_pc0()

    contexto = zmq.Context()
    receptor = contexto.socket(zmq.PULL)
    receptor.bind(config["zmq"]["pc0"]["ingesta_historica"])

    log("PC0-BD", "Servicio de base historica iniciado.")
    while True:
        mensaje = receptor.recv_json()
        tipo = mensaje["tipo"]
        datos = mensaje["datos"]
        if tipo == "evento_sensor":
            repositorio.guardar_evento_sensor(datos)
        elif tipo == "comando_semaforo":
            repositorio.guardar_comando_semaforo(datos)
        elif tipo == "snapshot_operativo":
            repositorio.guardar_snapshot_vehiculos_historico(datos)
        log("PC0-BD", f"Persistido mensaje historico de tipo {tipo}.")


if __name__ == "__main__":
    main()
