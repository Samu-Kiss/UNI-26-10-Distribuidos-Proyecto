from __future__ import annotations

from typing import Any

import zmq

from common.mensajes.ambulancias import SolicitudAmbulancia
from common.mensajes.control_manual import SolicitudControlManual
from common.utilidades.mensajeria_zmq import (
    configurar_emisor_mejor_esfuerzo,
    enviar_json_mejor_esfuerzo,
)
from common.utilidades.persistencia_sqlite import RepositorioSQLite


class BackendOperativo:
    def __init__(
        self,
        *,
        config: dict[str, object],
        repositorio: RepositorioSQLite,
        rol_backend: str,
        permitir_operaciones_activas: bool,
    ) -> None:
        self.config = config
        self.repositorio = repositorio
        self.rol_backend = rol_backend
        self.permitir_operaciones_activas = permitir_operaciones_activas
        self.contexto = zmq.Context.instance()
        self.emisor_ambulancias = self.contexto.socket(zmq.PUSH)
        self.emisor_ambulancias.connect(config["zmq"]["pc0"]["solicitudes_ambulancia"])
        configurar_emisor_mejor_esfuerzo(self.emisor_ambulancias)
        self.emisor_control_manual = self.contexto.socket(zmq.PUSH)
        self.emisor_control_manual.connect(config["zmq"]["pc2"]["entrada_control_manual"])
        configurar_emisor_mejor_esfuerzo(self.emisor_control_manual)

    def atender_solicitud(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        tipo = str(solicitud.get("tipo", ""))
        if tipo == "salud":
            return {
                "ok": True,
                "backend_atendio": self.rol_backend,
            }
        if tipo == "resumen_estado":
            return {
                "ok": True,
                "backend_atendio": self.rol_backend,
                "resumen": self.repositorio.obtener_resumen_estado(),
            }
        if tipo == "estado_interseccion":
            interseccion = str(solicitud["interseccion"])
            estado = self.repositorio.obtener_estado_interseccion(interseccion)
            return {
                "ok": estado is not None,
                "backend_atendio": self.rol_backend,
                "estado": estado,
            }
        if tipo == "estado_via":
            via_id = str(solicitud["via_id"])
            estado = self.repositorio.obtener_estado_via(via_id)
            return {
                "ok": estado is not None,
                "backend_atendio": self.rol_backend,
                "estado": estado,
            }
        if tipo == "listar_ambulancias":
            return {
                "ok": True,
                "backend_atendio": self.rol_backend,
                "ambulancias": self.repositorio.listar_ambulancias_actuales(),
            }
        if tipo == "conteo_eventos_intervalo":
            return {
                "ok": False,
                "backend_atendio": self.rol_backend,
                "error": "consulta_no_disponible_en_backend_operativo",
            }
        if tipo == "conteo_comandos_intervalo":
            return {
                "ok": False,
                "backend_atendio": self.rol_backend,
                "error": "consulta_no_disponible_en_backend_operativo",
            }
        if tipo == "crear_ambulancia":
            if not self.permitir_operaciones_activas:
                return {
                    "ok": False,
                    "backend_atendio": self.rol_backend,
                    "error": "operacion_no_disponible_en_respaldo",
                }
            solicitud_ambulancia = SolicitudAmbulancia.crear(
                nodo_origen=str(solicitud["nodo_origen"]),
                velocidad=(
                    float(solicitud["velocidad"])
                    if solicitud.get("velocidad") is not None
                    else None
                ),
            )
            aceptada = enviar_json_mejor_esfuerzo(
                self.emisor_ambulancias,
                solicitud_ambulancia.a_dict(),
            )
            return {
                "ok": aceptada,
                "backend_atendio": self.rol_backend,
                "solicitud": solicitud_ambulancia.a_dict(),
            }
        if tipo == "control_manual":
            if not self.permitir_operaciones_activas:
                return {
                    "ok": False,
                    "backend_atendio": self.rol_backend,
                    "error": "operacion_no_disponible_en_respaldo",
                }
            if self.repositorio.obtener_estado_interseccion(str(solicitud["interseccion"])) is None:
                return {
                    "ok": False,
                    "backend_atendio": self.rol_backend,
                    "error": "interseccion_no_encontrada",
                }
            solicitud_control = SolicitudControlManual.crear(
                interseccion=str(solicitud["interseccion"]),
                fase_ganadora=str(solicitud["fase_ganadora"]),
                duracion_ticks=int(solicitud["duracion_ticks"]),
            )
            aceptada = enviar_json_mejor_esfuerzo(
                self.emisor_control_manual,
                solicitud_control.a_dict(),
            )
            return {
                "ok": aceptada,
                "backend_atendio": self.rol_backend,
                "solicitud": solicitud_control.a_dict(),
            }
        return {
            "ok": False,
            "backend_atendio": self.rol_backend,
            "error": "tipo_no_soportado",
        }
