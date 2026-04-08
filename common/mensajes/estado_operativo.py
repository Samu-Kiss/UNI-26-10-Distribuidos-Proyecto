from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class SnapshotOperativo:
    timestamp: str
    tick_actual: int
    fuente: str
    version_contrato: int
    intersecciones: list[dict[str, Any]]
    vias: list[dict[str, Any]]
    vehiculos: list[dict[str, Any]]

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def crear(
        cls,
        timestamp: str,
        tick_actual: int,
        intersecciones: list[dict[str, Any]],
        vias: list[dict[str, Any]],
        vehiculos: list[dict[str, Any]],
        fuente: str = "PC0",
        version_contrato: int = 1,
    ) -> "SnapshotOperativo":
        return cls(
            timestamp=timestamp,
            tick_actual=tick_actual,
            fuente=fuente,
            version_contrato=version_contrato,
            intersecciones=intersecciones,
            vias=vias,
            vehiculos=vehiculos,
        )

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> "SnapshotOperativo":
        return cls(
            timestamp=str(datos["timestamp"]),
            tick_actual=int(datos["tick_actual"]),
            fuente=str(datos.get("fuente", "PC0")),
            version_contrato=int(datos.get("version_contrato", 1)),
            intersecciones=list(datos["intersecciones"]),
            vias=list(datos["vias"]),
            vehiculos=list(datos["vehiculos"]),
        )
