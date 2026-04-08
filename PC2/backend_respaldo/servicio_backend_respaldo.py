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
    repositorio = RepositorioSQLite(raiz / "PC2/replica_db/bd_replicada.sqlite3")
    repositorio.inicializar_pc2()
    backend = BackendOperativo(
        config=config,
        repositorio=repositorio,
        rol_backend="PC2_RESPALDO",
        permitir_operaciones_activas=False,
    )

    contexto = zmq.Context.instance()
    servidor = contexto.socket(zmq.REP)
    servidor.bind(config["zmq"]["pc2"]["backend_respaldo"])

    log("PC2-BackendRespaldo", "Backend de respaldo iniciado.")
    while True:
        solicitud = servidor.recv_json()
        respuesta = backend.atender_solicitud(solicitud)
        servidor.send_json(respuesta)
        log(
            "PC2-BackendRespaldo",
            f"Solicitud atendida: {solicitud.get('tipo', 'desconocida')}.",
        )


if __name__ == "__main__":
    main()
