from __future__ import annotations

from pathlib import Path

import zmq

from common.mensajes.comandos import ComandoSemaforo
from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import hora_simulada_desde_config, log


class ControladorSemaforos:
    def __init__(self, config: dict[str, object] | None = None) -> None:
        if config is None:
            raiz = Path(__file__).resolve().parents[2]
            config = cargar_configuracion(raiz / "config/system_config.json")
        self.config = config
        self.contexto = zmq.Context.instance()
        self.emisor = self.contexto.socket(zmq.PUSH)
        self.emisor.connect(config["zmq"]["pc0"]["entrada_comandos"])

    def aplicar_comando(self, comando: ComandoSemaforo) -> None:
        self.emisor.send_json(comando.a_dict())
        if comando.modo == "MANUAL":
            if comando.tiempo_verde < 0:
                detalle = (
                    f"Interseccion {comando.interseccion}: control manual para {comando.fase_ganadora} "
                    "hasta nueva orden. "
                )
            else:
                detalle = (
                    f"Interseccion {comando.interseccion}: control manual para {comando.fase_ganadora} "
                    f"durante {comando.tiempo_verde:.2f} ticks. "
                )
        else:
            detalle = (
                f"Interseccion {comando.interseccion}: prioridad para {comando.fase_ganadora} "
                f"en {comando.tiempo_verde:.2f} ticks del ciclo; opuesto {comando.tiempo_opuesto:.2f}. "
            )
        log(
            "PC2-Semaforos",
            f"{detalle}Razon: {comando.razon}",
            hora_simulada=hora_simulada_desde_config(self.config, comando.tick_origen),
        )
