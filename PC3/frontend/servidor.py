from __future__ import annotations

import json
import mimetypes
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from common.utilidades.cliente_backend_failover import ClienteBackendFailover
from common.utilidades.persistencia_sqlite import RepositorioSQLite


RUTA_STATIC = Path(__file__).resolve().parent / "static"


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class InterfazPC3Handler(BaseHTTPRequestHandler):
    ruta_bd: Path
    cliente_backend: ClienteBackendFailover
    score_config: dict[str, Any] = {
        "pesos": {"camara": 0.5, "espira_inductiva": 0.35, "gps": 0.15},
        "umbrales": {"bajo": 0.4, "alto": 0.7},
    }
    simulacion_config: dict[str, Any] = {
        "hora_inicio_simulada": "12:00",
        "hora_fin_simulada": "18:00",
        "modo_bucle_infinito": False,
        "minutos_simulados_por_tick": 1,
        "tick_segundos_reales": 1.0,
    }

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        ruta = urlparse(self.path).path
        if ruta in {"/", "/index.html"}:
            self._responder_archivo(RUTA_STATIC / "index.html", "text/html; charset=utf-8")
            return
        if ruta == "/api/estado":
            self._responder_estado()
            return
        if ruta.startswith("/static/"):
            self._responder_static(ruta)
            return
        if ruta == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404, "ruta_no_encontrada")

    def do_POST(self) -> None:
        ruta = urlparse(self.path).path
        if ruta == "/api/ambulancia":
            self._redirigir_solicitud_backend("crear_ambulancia")
            return
        if ruta == "/api/control-manual":
            self._redirigir_solicitud_backend("control_manual")
            return
        self.send_error(404, "ruta_no_encontrada")

    def _responder_static(self, ruta: str) -> None:
        nombre = ruta.removeprefix("/static/")
        archivo = (RUTA_STATIC / nombre).resolve()
        if RUTA_STATIC.resolve() not in archivo.parents or not archivo.is_file():
            self.send_error(404, "asset_no_encontrado")
            return
        tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
        if archivo.suffix == ".js":
            tipo = "text/javascript; charset=utf-8"
        elif archivo.suffix == ".css":
            tipo = "text/css; charset=utf-8"
        self._responder_archivo(archivo, tipo)

    def _responder_archivo(self, archivo: Path, tipo_contenido: str) -> None:
        cuerpo = archivo.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo_contenido)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _responder_json(self, estado_http: int, contenido: dict[str, Any]) -> None:
        cuerpo = json.dumps(contenido, ensure_ascii=False).encode("utf-8")
        self.send_response(estado_http)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _responder_estado(self) -> None:
        repositorio = RepositorioSQLite(self.ruta_bd)
        try:
            repositorio.inicializar_pc3()
            estado = repositorio.obtener_estado_operativo_completo()
        finally:
            repositorio.cerrar()
        self._responder_json(
            200,
            {
                "ok": True,
                "estado": estado,
                "score_config": self.score_config,
                "simulacion": self.simulacion_config,
                "timestamp_consulta": datetime.now().isoformat(),
            },
        )

    def _leer_json(self) -> dict[str, Any]:
        longitud = int(self.headers.get("Content-Length", "0"))
        if longitud <= 0:
            return {}
        cuerpo = self.rfile.read(longitud)
        return json.loads(cuerpo.decode("utf-8"))

    def _redirigir_solicitud_backend(self, tipo: str) -> None:
        try:
            payload = self._leer_json()
        except json.JSONDecodeError:
            self._responder_json(400, {"ok": False, "error": "json_invalido"})
            return
        try:
            respuesta = self.cliente_backend.solicitar({"tipo": tipo, **payload})
        except Exception as error:
            self._responder_json(502, {"ok": False, "error": "backend_no_disponible", "detalle": str(error)})
            return
        estado_http = 200 if respuesta.get("ok") else 400
        self._responder_json(estado_http, respuesta)


def iniciar_interfaz_web(
    *,
    config: dict[str, Any],
    ruta_bd: Path,
) -> tuple[str, ReusableThreadingHTTPServer]:
    config_frontend = config.get("frontend", {})
    config_pc3 = config_frontend.get("pc3", {}) if isinstance(config_frontend, dict) else {}
    host = str(config_pc3.get("host", "127.0.0.1"))
    puerto_inicial = int(config_pc3.get("puerto", 8080))

    class Handler(InterfazPC3Handler):
        pass

    Handler.ruta_bd = Path(ruta_bd)
    Handler.cliente_backend = ClienteBackendFailover(config)
    config_analitica = config.get("analitica", {})
    pesos = config_analitica.get("pesos", {}) if isinstance(config_analitica, dict) else {}
    Handler.score_config = {
        "pesos": {
            "camara": float(pesos.get("camara", 0.5)) if isinstance(pesos, dict) else 0.5,
            "espira_inductiva": float(pesos.get("espira_inductiva", 0.35)) if isinstance(pesos, dict) else 0.35,
            "gps": float(pesos.get("gps", 0.15)) if isinstance(pesos, dict) else 0.15,
        },
        "umbrales": {"bajo": 0.4, "alto": 0.7},
    }
    config_simulacion = config.get("simulacion", {})
    Handler.simulacion_config = {
        "hora_inicio_simulada": str(config_simulacion.get("hora_inicio_simulada", "12:00"))
        if isinstance(config_simulacion, dict)
        else "12:00",
        "hora_fin_simulada": str(config_simulacion.get("hora_fin_simulada", "18:00"))
        if isinstance(config_simulacion, dict)
        else "18:00",
        "modo_bucle_infinito": bool(config_simulacion.get("modo_bucle_infinito", False))
        if isinstance(config_simulacion, dict)
        else False,
        "minutos_simulados_por_tick": int(config_simulacion.get("minutos_simulados_por_tick", 1))
        if isinstance(config_simulacion, dict)
        else 1,
        "tick_segundos_reales": float(config_simulacion.get("tick_segundos_reales", 1.0))
        if isinstance(config_simulacion, dict)
        else 1.0,
    }

    ultimo_error: OSError | None = None
    for puerto in range(puerto_inicial, puerto_inicial + 20):
        try:
            servidor = ReusableThreadingHTTPServer((host, puerto), Handler)
            hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
            hilo.start()
            return f"http://{host}:{puerto}/", servidor
        except OSError as error:
            ultimo_error = error

    raise RuntimeError(
        f"No fue posible iniciar la interfaz web de PC3 desde el puerto {puerto_inicial}."
    ) from ultimo_error
