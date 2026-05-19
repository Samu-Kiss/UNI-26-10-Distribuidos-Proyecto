from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import zmq

from PC2.traffic_ctrl.controlador_semaforos import ControladorSemaforos
from common.mensajes.comandos import ComandoSemaforo
from common.mensajes.control_manual import SolicitudControlManual
from common.mensajes.eventos import EventoSensor
from common.modelos.trafico import CiudadMapa
from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import hora_simulada_desde_config, log
from common.utilidades.normalizacion_sensores import (
    clasificar_nota_trafico,
    normalizar_camara,
    normalizar_espira,
    normalizar_gps,
)


class ServicioAnalitica:
    def __init__(self, config: dict[str, object]) -> None:
        self.config = config
        self.controlador = ControladorSemaforos(config)
        self.eventos_por_interseccion_tick: dict[str, dict[int, dict[str, dict[str, EventoSensor]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        self.ultimo_comando_por_interseccion: dict[str, tuple[str, float, float, str]] = {}
        self.ultimo_tick_decidido_por_interseccion: dict[str, int] = {}
        self.controles_manuales_por_interseccion: dict[str, dict[str, int | str]] = {}
        self.ultimo_tick_observado = 0
        self.pesos = config["analitica"]["pesos"]
        self.ciudad_mapa = CiudadMapa.desde_config(config["ciudad"])
        self.contexto = zmq.Context.instance()
        self.emisor_pc0 = self.contexto.socket(zmq.PUSH)
        self.emisor_pc0.connect(config["zmq"]["pc0"]["ingesta_historica"])

    def persistir_comando(self, comando: ComandoSemaforo) -> None:
        carga = {"tipo": "comando_semaforo", "datos": comando.a_dict()}
        self.emisor_pc0.send_json(carga)

    def hora_simulada(self, tick_actual: int) -> str:
        return hora_simulada_desde_config(self.config, tick_actual)

    def control_manual_activo(self, interseccion: str, tick_origen: int) -> bool:
        control = self.controles_manuales_por_interseccion.get(interseccion)
        if control is None:
            return False
        tick_fin = int(control["tick_fin"])
        if tick_fin < 0:
            return True
        if tick_origen <= tick_fin:
            return True
        del self.controles_manuales_por_interseccion[interseccion]
        log(
            "PC2-Analitica",
            f"Control manual liberado en {interseccion} al finalizar el tick {tick_fin}.",
            hora_simulada=self.hora_simulada(tick_origen),
        )
        return False

    def obtener_interseccion_manual_activa(self) -> str | None:
        for interseccion, control in self.controles_manuales_por_interseccion.items():
            if int(control["tick_fin"]) < 0:
                return interseccion
        return None

    def liberar_control_manual(self, interseccion: str) -> None:
        interseccion_estado = self.ciudad_mapa.intersecciones[interseccion]
        self.controles_manuales_por_interseccion.pop(interseccion, None)
        fase = interseccion_estado.fase_prioritaria
        tiempo_verde = float(interseccion_estado.duracion_fase_prioritaria)
        tiempo_opuesto = float(interseccion_estado.duracion_fase_secundaria)
        tick_base = max(
            self.ultimo_tick_observado,
            self.ultimo_tick_decidido_por_interseccion.get(interseccion, 0),
        )
        comando = ComandoSemaforo.crear(
            interseccion=interseccion,
            fase_ganadora=fase,
            tiempo_verde=tiempo_verde,
            tiempo_opuesto=tiempo_opuesto,
            razon="Control manual liberado desde backend; la interseccion vuelve al programa automatico vigente.",
            tick_origen=tick_base,
            modo="AUTOMATICO",
        )
        self.ciudad_mapa.aplicar_programacion_semaforo(
            interseccion_id=interseccion,
            fase_ganadora=fase,
            tiempo_verde=tiempo_verde,
            tiempo_opuesto=tiempo_opuesto,
        )
        self.ultimo_comando_por_interseccion[interseccion] = (
            fase,
            tiempo_verde,
            tiempo_opuesto,
            comando.modo,
        )
        self.controlador.aplicar_comando(comando)
        self.persistir_comando(comando)
        log(
            "PC2-Analitica",
            f"Control manual liberado en {interseccion}; vuelve a modo automatico.",
            hora_simulada=self.hora_simulada(tick_base),
        )

    def aplicar_control_manual(self, solicitud: SolicitudControlManual) -> None:
        if solicitud.interseccion not in self.ciudad_mapa.intersecciones:
            log(
                "PC2-Analitica",
                f"Solicitud de control manual ignorada: {solicitud.interseccion} no existe.",
                hora_simulada=self.hora_simulada(self.ultimo_tick_observado),
            )
            return
        if solicitud.fase_ganadora == "AUTO":
            self.liberar_control_manual(solicitud.interseccion)
            return
        interseccion_manual_activa = self.obtener_interseccion_manual_activa()
        if interseccion_manual_activa is not None and interseccion_manual_activa != solicitud.interseccion:
            log(
                "PC2-Analitica",
                (
                    f"Solicitud de control manual ignorada: {solicitud.interseccion} no puede tomar control "
                    f"mientras {interseccion_manual_activa} siga en manual."
                ),
                hora_simulada=self.hora_simulada(self.ultimo_tick_observado),
            )
            return
        tick_base = max(
            self.ultimo_tick_observado,
            self.ultimo_tick_decidido_por_interseccion.get(solicitud.interseccion, 0),
        )
        self.controles_manuales_por_interseccion[solicitud.interseccion] = {
            "fase_ganadora": solicitud.fase_ganadora,
            "tick_fin": -1,
        }
        comando = ComandoSemaforo.crear(
            interseccion=solicitud.interseccion,
            fase_ganadora=solicitud.fase_ganadora,
            tiempo_verde=-1.0,
            tiempo_opuesto=-1.0,
            razon=(
                "Control manual forzado desde backend. "
                f"Se mantiene la fase {solicitud.fase_ganadora} hasta nueva orden."
            ),
            tick_origen=tick_base,
            modo="MANUAL",
        )
        self.ciudad_mapa.forzar_programacion_semaforo(
            interseccion_id=solicitud.interseccion,
            fase_ganadora=solicitud.fase_ganadora,
            duracion_ticks=comando.tiempo_verde,
        )
        self.ultimo_comando_por_interseccion[solicitud.interseccion] = (
            solicitud.fase_ganadora,
            comando.tiempo_verde,
            comando.tiempo_opuesto,
            comando.modo,
        )
        self.controlador.aplicar_comando(comando)
        self.persistir_comando(comando)
        log(
            "PC2-Analitica",
            (
                f"Control manual aplicado en {solicitud.interseccion}: "
                f"fase={solicitud.fase_ganadora}, vigente_hasta=nueva_orden."
            ),
            hora_simulada=self.hora_simulada(tick_base),
        )

    def obtener_nota_camara(self, datos: dict[str, object]) -> float:
        if "nota" in datos:
            return float(datos["nota"])
        return normalizar_camara(int(datos["volumen"]))

    def obtener_nota_espira(self, datos: dict[str, object]) -> float:
        if "nota" in datos:
            return float(datos["nota"])
        return normalizar_espira(int(datos["vehiculos_en_transito"]))

    def obtener_nota_gps(self, datos: dict[str, object]) -> float:
        if "nota" in datos:
            return float(datos["nota"])
        return normalizar_gps(float(datos["velocidad_promedio"]))

    def calcular_score_via(
        self,
        interseccion: str,
        tick_origen: int,
        via_id: str,
    ) -> tuple[float, dict[str, float]]:
        eventos = self.eventos_por_interseccion_tick[interseccion][tick_origen][via_id]
        nota_camara = self.obtener_nota_camara(eventos["camara"].datos)
        nota_espira = self.obtener_nota_espira(eventos["espira_inductiva"].datos)
        nota_gps = self.obtener_nota_gps(eventos["gps"].datos)
        score = (
            nota_camara * self.pesos["camara"]
            + nota_espira * self.pesos["espira_inductiva"]
            + nota_gps * self.pesos["gps"]
        )
        return round(score, 4), {
            "camara": round(nota_camara, 4),
            "espira_inductiva": round(nota_espira, 4),
            "gps": round(nota_gps, 4),
        }

    def calcular_scores_por_eje(
        self, interseccion: str, tick_origen: int
    ) -> tuple[dict[str, float], dict[str, tuple[float, dict[str, float]]]]:
        vias_entrada = self.ciudad_mapa.obtener_vias_de_entrada(interseccion)
        scores_via: dict[str, tuple[float, dict[str, float]]] = {}
        scores_por_eje: dict[str, list[float]] = {"HORIZONTAL": [], "VERTICAL": []}
        for via in vias_entrada:
            resultado = self.calcular_score_via(interseccion, tick_origen, via.id_via)
            scores_via[via.id_via] = resultado
            score_via, _ = resultado
            self.ciudad_mapa.vias[via.id_via].score = score_via
            scores_por_eje[via.eje].append(score_via)

        agregados = {
            eje: round(sum(scores) / len(scores), 4) if scores else 0.0
            for eje, scores in scores_por_eje.items()
        }
        return agregados, scores_via

    def tick_listo_para_interseccion(self, interseccion: str, tick_origen: int) -> bool:
        requeridos = {"camara", "espira_inductiva", "gps"}
        buffer_tick = self.eventos_por_interseccion_tick[interseccion][tick_origen]
        for via in self.ciudad_mapa.obtener_vias_de_entrada(interseccion):
            if not requeridos.issubset(buffer_tick.get(via.id_via, {}).keys()):
                return False
        return True

    def depurar_ticks_antiguos(self, interseccion: str, tick_origen: int) -> None:
        ticks = self.eventos_por_interseccion_tick[interseccion]
        for tick in [tick_existente for tick_existente in ticks if tick_existente < tick_origen]:
            del ticks[tick]

    def decidir_fase(
        self, interseccion: str, score_horizontal: float, score_vertical: float
    ) -> tuple[str, float, float, str]:
        if score_horizontal > 0.0 and score_vertical == 0.0:
            return (
                "HORIZONTAL",
                30.0,
                0.0,
                "El eje vertical no tiene carga (score=0) y el horizontal si; se libera paso total al horizontal.",
            )
        if score_vertical > 0.0 and score_horizontal == 0.0:
            return (
                "VERTICAL",
                30.0,
                0.0,
                "El eje horizontal no tiene carga (score=0) y el vertical si; se libera paso total al vertical.",
            )
        gap = min(abs(score_horizontal - score_vertical), 1.0)
        fase_actual = self.ciudad_mapa.intersecciones[interseccion].fase_activa
        if score_horizontal > score_vertical:
            fase = "HORIZONTAL"
            razon = "El eje horizontal supera al vertical y recibe prioridad."
        elif score_vertical > score_horizontal:
            fase = "VERTICAL"
            razon = "El eje vertical supera al horizontal y recibe prioridad."
        else:
            fase = fase_actual
            razon = "Empate de scores por eje; se mantiene la fase actual."
        tiempo_verde = 15 + 15 * gap
        tiempo_opuesto = 30 - tiempo_verde
        return fase, round(tiempo_verde, 2), round(tiempo_opuesto, 2), razon

    def procesar_evento(self, evento: EventoSensor) -> None:
        self.ultimo_tick_observado = max(self.ultimo_tick_observado, evento.tick_origen)
        buffer_tick = self.eventos_por_interseccion_tick[evento.interseccion][evento.tick_origen]
        buffer_tick[evento.via_id][evento.tipo_sensor] = evento
        log(
            "PC2-Analitica",
            (
                f"Evento recibido en {evento.interseccion}, via {evento.via_id}, "
                f"sensor {evento.tipo_sensor}, tick={evento.tick_origen}."
            ),
            hora_simulada=self.hora_simulada(evento.tick_origen),
        )

        ultimo_tick_decidido = self.ultimo_tick_decidido_por_interseccion.get(evento.interseccion, -1)
        if evento.tick_origen <= ultimo_tick_decidido:
            return

        if self.control_manual_activo(evento.interseccion, evento.tick_origen):
            return

        if not self.tick_listo_para_interseccion(evento.interseccion, evento.tick_origen):
            return

        scores_eje, scores_via = self.calcular_scores_por_eje(evento.interseccion, evento.tick_origen)
        score_horizontal = scores_eje["HORIZONTAL"]
        score_vertical = scores_eje["VERTICAL"]
        score_global = max(score_horizontal, score_vertical)

        fase, tiempo_verde, tiempo_opuesto, razon = self.decidir_fase(
            evento.interseccion,
            score_horizontal,
            score_vertical,
        )
        self.ultimo_tick_decidido_por_interseccion[evento.interseccion] = evento.tick_origen
        self.depurar_ticks_antiguos(evento.interseccion, evento.tick_origen)
        firma_comando = (fase, tiempo_verde, tiempo_opuesto, "AUTOMATICO")
        if self.ultimo_comando_por_interseccion.get(evento.interseccion) == firma_comando:
            return

        comando = ComandoSemaforo.crear(
            interseccion=evento.interseccion,
            fase_ganadora=fase,
            tiempo_verde=tiempo_verde,
            tiempo_opuesto=tiempo_opuesto,
            razon=(
                f"{razon} Tick={evento.tick_origen}. Scores por eje -> horizontal={score_horizontal:.4f}, "
                f"vertical={score_vertical:.4f}. "
                f"Categoria global={clasificar_nota_trafico(score_global)}"
            ),
            tick_origen=evento.tick_origen,
        )
        self.ciudad_mapa.aplicar_programacion_semaforo(
            interseccion_id=evento.interseccion,
            fase_ganadora=fase,
            tiempo_verde=tiempo_verde,
            tiempo_opuesto=tiempo_opuesto,
        )
        self.ultimo_comando_por_interseccion[evento.interseccion] = firma_comando

        detalle_vias = ", ".join(
            (
                f"{via_id}={score_via:.4f}"
                f"(c={notas['camara']:.4f},e={notas['espira_inductiva']:.4f},g={notas['gps']:.4f})"
            )
            for via_id, (score_via, notas) in sorted(scores_via.items())
        )
        log(
            "PC2-Analitica",
            (
                f"Interseccion {evento.interseccion} en tick {evento.tick_origen}: "
                f"score_horizontal={score_horizontal:.4f}, "
                f"score_vertical={score_vertical:.4f}. "
                f"Detalle por via: {detalle_vias}"
            ),
            hora_simulada=self.hora_simulada(evento.tick_origen),
        )
        self.controlador.aplicar_comando(comando)
        self.persistir_comando(comando)


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    servicio = ServicioAnalitica(config)

    contexto = zmq.Context()
    suscriptor = contexto.socket(zmq.SUB)
    suscriptor.connect(config["zmq"]["pc1"]["salida_broker"])
    for topico in config["sensores"]["tipos"]:
        suscriptor.setsockopt_string(zmq.SUBSCRIBE, topico)
    receptor_control_manual = contexto.socket(zmq.PULL)
    receptor_control_manual.bind(config["zmq"]["pc2"]["entrada_control_manual"])
    poller = zmq.Poller()
    poller.register(suscriptor, zmq.POLLIN)
    poller.register(receptor_control_manual, zmq.POLLIN)

    log("PC2-Analitica", "Servicio de analitica iniciado.")
    while True:
        eventos = dict(poller.poll())
        if receptor_control_manual in eventos:
            solicitud = SolicitudControlManual.desde_dict(receptor_control_manual.recv_json())
            servicio.aplicar_control_manual(solicitud)
        if suscriptor in eventos:
            _, carga = suscriptor.recv_multipart()
            evento = EventoSensor.desde_dict(zmq.utils.jsonapi.loads(carga))
            servicio.procesar_evento(evento)


if __name__ == "__main__":
    main()
