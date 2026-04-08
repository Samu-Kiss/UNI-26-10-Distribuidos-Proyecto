from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def cargar_configuracion(ruta: str | Path) -> dict[str, Any]:
    ruta_config = Path(ruta)
    with ruta_config.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)
