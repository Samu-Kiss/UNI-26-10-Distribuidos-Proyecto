from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass(slots=True)
class ComandoSemaforo:
    interseccion: str
    fase_ganadora: str
    tiempo_verde: float
    tiempo_opuesto: float
    razon: str
    tick_origen: int
    timestamp: str

    def a_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def crear(
        cls,
        interseccion: str,
        fase_ganadora: str,
        tiempo_verde: float,
        tiempo_opuesto: float,
        razon: str,
        tick_origen: int,
    ) -> "ComandoSemaforo":
        return cls(
            interseccion=interseccion,
            fase_ganadora=fase_ganadora,
            tiempo_verde=tiempo_verde,
            tiempo_opuesto=tiempo_opuesto,
            razon=razon,
            tick_origen=tick_origen,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def desde_dict(cls, datos: dict[str, object]) -> "ComandoSemaforo":
        return cls(
            interseccion=str(datos["interseccion"]),
            fase_ganadora=str(datos["fase_ganadora"]),
            tiempo_verde=float(datos["tiempo_verde"]),
            tiempo_opuesto=float(datos["tiempo_opuesto"]),
            razon=str(datos["razon"]),
            tick_origen=int(datos.get("tick_origen", 0)),
            timestamp=str(datos["timestamp"]),
        )
