from __future__ import annotations

import zmq


def configurar_emisor_mejor_esfuerzo(emisor: zmq.Socket) -> None:
    emisor.setsockopt(zmq.IMMEDIATE, 1)
    emisor.setsockopt(zmq.SNDHWM, 1)
    emisor.setsockopt(zmq.LINGER, 0)


def enviar_json_mejor_esfuerzo(emisor: zmq.Socket, mensaje: dict[str, object]) -> bool:
    try:
        emisor.send_json(mensaje, flags=zmq.NOBLOCK)
    except zmq.Again:
        return False
    return True
