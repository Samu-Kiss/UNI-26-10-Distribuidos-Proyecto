from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Vehiculo:
    id_vehiculo: str
    via_actual: str
    posicion_en_via: float
    velocidad: float
    direccion_actual: str
    estado: str
    tipo: str = "NORMAL"
