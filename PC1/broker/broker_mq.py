from __future__ import annotations

from pathlib import Path

import zmq

from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    contexto = zmq.Context()

    suscriptor = contexto.socket(zmq.SUB)
    suscriptor.bind(config["zmq"]["pc1"]["publicador_sensores"])
    for topico in config["sensores"]["tipos"]:
        suscriptor.setsockopt_string(zmq.SUBSCRIBE, topico)

    publicador = contexto.socket(zmq.PUB)
    publicador.bind(config["zmq"]["pc1"]["salida_broker"])

    log("PC1-Broker", "Broker base iniciado.")
    while True:
        topico, carga = suscriptor.recv_multipart()
        publicador.send_multipart([topico, carga])
        log("PC1-Broker", f"Reenviado evento del topico {topico.decode('utf-8')}.")


if __name__ == "__main__":
    main()
