from __future__ import annotations

from pathlib import Path
from typing import Any

import zmq

from common.utilidades.configuracion import cargar_configuracion


class ClienteBackendFailover:
    def __init__(self, config: dict[str, object] | None = None) -> None:
        if config is None:
            raiz = Path(__file__).resolve().parents[2]
            config = cargar_configuracion(raiz / "config/system_config.json")
        self.config = config
        self.contexto = zmq.Context.instance()
        self.endpoint_primario = str(config["zmq"]["pc3"]["backend_principal"])
        self.endpoint_respaldo = str(config["zmq"]["pc2"]["backend_respaldo"])

    def _solicitar_endpoint(self, endpoint: str, solicitud: dict[str, Any]) -> dict[str, Any]:
        socket = self.contexto.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.RCVTIMEO, 1500)
        socket.setsockopt(zmq.SNDTIMEO, 1500)
        socket.connect(endpoint)
        try:
            socket.send_json(solicitud)
            respuesta = socket.recv_json()
        finally:
            socket.close()
        return respuesta

    def solicitar(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        try:
            respuesta = self._solicitar_endpoint(self.endpoint_primario, solicitud)
            respuesta.setdefault("failover_usado", False)
            return respuesta
        except zmq.ZMQError:
            respuesta = self._solicitar_endpoint(self.endpoint_respaldo, solicitud)
            respuesta.setdefault("failover_usado", True)
            return respuesta
