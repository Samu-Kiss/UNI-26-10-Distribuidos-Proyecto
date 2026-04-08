from __future__ import annotations

from pathlib import Path

import zmq

from common.mensajes.eventos import EventoSensor
from common.mensajes.estado_operativo import SnapshotOperativo
from common.modelos.trafico import CiudadMapa
from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log
from common.utilidades.normalizacion_sensores import (
    clasificar_nota_trafico,
    normalizar_camara,
    normalizar_espira,
    normalizar_gps,
)


def enviar_mensaje_persistencia(emisor: zmq.Socket, tipo: str, datos: dict[str, object]) -> None:
    emisor.send_json({"tipo": tipo, "datos": datos})


def construir_datos(
    tipo_sensor: str,
    via: dict[str, object],
    intervalo_espira_segundos: int,
) -> dict[str, int | str]:
    if tipo_sensor == "camara":
        volumen = int(via["vehiculos_en_espera"])
        velocidad_promedio = round(float(via["velocidad_promedio"]))
        nota = normalizar_camara(volumen)
        return {
            "volumen": volumen,
            "velocidad_promedio": velocidad_promedio,
            "nota": nota,
            "categoria_trafico": clasificar_nota_trafico(nota),
        }
    if tipo_sensor == "espira_inductiva":
        vehiculos_en_transito = int(via["vehiculos_en_circulacion"])
        nota = normalizar_espira(vehiculos_en_transito)
        return {
            "vehiculos_en_transito": vehiculos_en_transito,
            "intervalo_segundos": intervalo_espira_segundos,
            "nota": nota,
            "categoria_trafico": clasificar_nota_trafico(nota),
        }
    vehiculos_en_transito = int(via["vehiculos_en_circulacion"])
    velocidad = round(float(via["velocidad_promedio"])) if vehiculos_en_transito > 0 else 0
    nota = normalizar_gps(velocidad)
    categoria = clasificar_nota_trafico(nota)
    return {
        "nivel_congestion": categoria,
        "velocidad_promedio": velocidad,
        "nota": nota,
        "categoria_trafico": categoria,
    }


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    ciudad_mapa = CiudadMapa.desde_config(config["ciudad"])
    contexto = zmq.Context()
    publicador = contexto.socket(zmq.PUB)
    publicador.connect(config["zmq"]["pc1"]["publicador_sensores"])
    receptor_estado = contexto.socket(zmq.PULL)
    receptor_estado.bind(config["zmq"]["pc1"]["entrada_estado_operativo"])
    emisor_pc0 = contexto.socket(zmq.PUSH)
    emisor_pc0.connect(config["zmq"]["pc0"]["ingesta_historica"])

    vias_instrumentadas = {via.id_via: via.destino for via in ciudad_mapa.obtener_vias_instrumentadas()}
    intervalo = int(config["sensores"]["intervalo_publicacion_segundos"])
    intervalo_espira = config["sensores"]["intervalo_espira_segundos"]
    tick_segundos = float(config["simulacion"]["tick_segundos_reales"])
    pasos_por_publicacion = max(1, int(round(intervalo / tick_segundos)))
    ultimo_tick_publicado = 0

    log("PC1-Sensores", "Servicio de sensores iniciado.")
    while True:
        mensaje = receptor_estado.recv_json()
        if mensaje["tipo"] != "snapshot_operativo":
            continue

        snapshot_operativo = SnapshotOperativo.desde_dict(mensaje["datos"])
        tick_actual = snapshot_operativo.tick_actual
        if tick_actual - ultimo_tick_publicado < pasos_por_publicacion:
            continue
        ultimo_tick_publicado = tick_actual

        vias_snapshot = {
            str(via["via_id"]): via for via in snapshot_operativo.vias if str(via["via_id"]) in vias_instrumentadas
        }
        log(
            "PC1-Sensores",
            (
                f"Snapshot recibido del tick {tick_actual}: "
                f"vehiculos_activos={len(snapshot_operativo.vehiculos)}, "
                f"vias_observadas={len(vias_snapshot)}."
            ),
        )

        for via_id, interseccion in vias_instrumentadas.items():
            via = vias_snapshot.get(via_id)
            if via is None:
                continue
            sufijo = via_id.replace("VIA-", "")
            for tipo_sensor in config["sensores"]["tipos"]:
                evento = EventoSensor.crear(
                    sensor_id=f"{tipo_sensor.upper()}-{sufijo}",
                    tipo_sensor=tipo_sensor,
                    interseccion=interseccion,
                    via_id=via_id,
                    tick_origen=tick_actual,
                    datos=construir_datos(
                        tipo_sensor=tipo_sensor,
                        via=via,
                        intervalo_espira_segundos=intervalo_espira,
                    ),
                )
                publicador.send_multipart(
                    [tipo_sensor.encode("utf-8"), zmq.utils.jsonapi.dumps(evento.a_dict())]
                )
                enviar_mensaje_persistencia(emisor_pc0, "evento_sensor", evento.a_dict())
                log(
                    "PC1-Sensores",
                    f"Publicado evento {tipo_sensor} para {via_id} -> {interseccion}: {evento.datos}",
                )


if __name__ == "__main__":
    main()
