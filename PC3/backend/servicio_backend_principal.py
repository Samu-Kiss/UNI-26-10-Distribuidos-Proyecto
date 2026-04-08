from __future__ import annotations

from pathlib import Path

import zmq

from common.utilidades.backend_operativo import BackendOperativo
from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log
from common.utilidades.persistencia_sqlite import RepositorioSQLite


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    repositorio = RepositorioSQLite(raiz / "PC3/main_db/bd_principal.sqlite3")
    repositorio.inicializar_pc3()
    backend = BackendOperativo(
        config=config,
        repositorio=repositorio,
        rol_backend="PC3_PRINCIPAL",
        permitir_operaciones_activas=True,
    )

    contexto = zmq.Context.instance()
    servidor = contexto.socket(zmq.REP)
    servidor.bind(config["zmq"]["pc3"]["backend_principal"])

    log("PC3-Backend", "Backend principal iniciado.")
    while True:
        solicitud = servidor.recv_json()
        respuesta = backend.atender_solicitud(solicitud)
        servidor.send_json(respuesta)
        log("PC3-Backend", f"Solicitud atendida: {solicitud.get('tipo', 'desconocida')}.")


if __name__ == "__main__":
    main()
