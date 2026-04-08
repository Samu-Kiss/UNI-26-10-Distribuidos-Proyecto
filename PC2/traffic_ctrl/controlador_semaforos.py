from __future__ import annotations

from pathlib import Path

import zmq

from common.mensajes.comandos import ComandoSemaforo
from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log


class ControladorSemaforos:
    def __init__(self, config: dict[str, object] | None = None) -> None:
        if config is None:
            raiz = Path(__file__).resolve().parents[2]
            config = cargar_configuracion(raiz / "config/system_config.json")
        self.contexto = zmq.Context.instance()
        self.emisor = self.contexto.socket(zmq.PUSH)
        self.emisor.connect(config["zmq"]["pc0"]["entrada_comandos"])

    def aplicar_comando(self, comando: ComandoSemaforo) -> None:
        self.emisor.send_json(comando.a_dict())
        log(
            "PC2-Semaforos",
            (
                f"Interseccion {comando.interseccion}: verde para {comando.fase_ganadora} "
                f"durante {comando.tiempo_verde:.2f}s, opuesto {comando.tiempo_opuesto:.2f}s. "
                f"Razon: {comando.razon}"
            ),
        )
