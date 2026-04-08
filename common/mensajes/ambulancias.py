from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class SolicitudAmbulancia:
    nodo_origen: str
    velocidad: float | None
    timestamp: str

    def a_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def crear(
        cls,
        nodo_origen: str,
        velocidad: float | None = None,
    ) -> "SolicitudAmbulancia":
        return cls(
            nodo_origen=nodo_origen,
            velocidad=velocidad,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def desde_dict(cls, datos: dict[str, object]) -> "SolicitudAmbulancia":
        velocidad = datos.get("velocidad")
        return cls(
            nodo_origen=str(datos["nodo_origen"]),
            velocidad=float(velocidad) if velocidad is not None else None,
            timestamp=str(datos["timestamp"]),
        )
