from __future__ import annotations

from datetime import datetime


def log(nombre_proceso: str, mensaje: str) -> None:
    marca = datetime.now().strftime("%H:%M:%S")
    print(f"[{marca}] [{nombre_proceso}] {mensaje}", flush=True)
