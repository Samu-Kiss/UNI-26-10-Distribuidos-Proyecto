from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class SolicitudControlManual:
    interseccion: str
    fase_ganadora: str
    duracion_ticks: int
    timestamp: str

    def a_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def crear(
        cls,
        interseccion: str,
        fase_ganadora: str,
        duracion_ticks: int,
    ) -> "SolicitudControlManual":
        return cls(
            interseccion=interseccion,
            fase_ganadora=fase_ganadora,
            duracion_ticks=duracion_ticks,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def desde_dict(cls, datos: dict[str, object]) -> "SolicitudControlManual":
        return cls(
            interseccion=str(datos["interseccion"]),
            fase_ganadora=str(datos["fase_ganadora"]),
            duracion_ticks=int(datos["duracion_ticks"]),
            timestamp=str(datos["timestamp"]),
        )
