from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class EventoSensor:
    sensor_id: str
    tipo_sensor: str
    interseccion: str
    via_id: str
    tick_origen: int
    datos: dict[str, Any]
    timestamp: str

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def crear(
        cls,
        sensor_id: str,
        tipo_sensor: str,
        interseccion: str,
        via_id: str,
        tick_origen: int,
        datos: dict[str, Any],
    ) -> "EventoSensor":
        return cls(
            sensor_id=sensor_id,
            tipo_sensor=tipo_sensor,
            interseccion=interseccion,
            via_id=via_id,
            tick_origen=tick_origen,
            datos=datos,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> "EventoSensor":
        return cls(
            sensor_id=datos["sensor_id"],
            tipo_sensor=datos["tipo_sensor"],
            interseccion=datos["interseccion"],
            via_id=datos["via_id"],
            tick_origen=int(datos.get("tick_origen", 0)),
            datos=datos["datos"],
            timestamp=datos["timestamp"],
        )
