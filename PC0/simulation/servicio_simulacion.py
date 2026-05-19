from __future__ import annotations

import time
from pathlib import Path

import zmq

from common.mensajes.ambulancias import SolicitudAmbulancia
from common.mensajes.comandos import ComandoSemaforo
from common.modelos.simulacion import MotorSimulacion
from common.modelos.trafico import CiudadMapa
from common.utilidades.configuracion import cargar_configuracion
from common.utilidades.logs import log
from common.utilidades.mensajeria_zmq import (
    configurar_emisor_mejor_esfuerzo,
    enviar_json_mejor_esfuerzo,
)


def procesar_comandos_pendientes(receptor_comandos: zmq.Socket, motor: MotorSimulacion) -> int:
    comandos_aplicados = 0
    while True:
        try:
            carga = receptor_comandos.recv_json(flags=zmq.NOBLOCK)
        except zmq.Again:
            break
        comando = ComandoSemaforo.desde_dict(carga)
        motor.aplicar_comando_semaforo(comando)
        comandos_aplicados += 1
        if comando.modo == "MANUAL" and comando.tiempo_verde < 0:
            detalle_duracion = "hasta nueva orden"
        else:
            detalle_duracion = f"verde={comando.tiempo_verde:.2f}, opuesto={comando.tiempo_opuesto:.2f}"
        log(
            "PC0-Simulacion",
            (
                f"Comando aplicado en {comando.interseccion}: "
                f"modo={comando.modo}, fase={comando.fase_ganadora}, "
                f"{detalle_duracion}"
            ),
            hora_simulada=motor.obtener_hora_simulada_actual(),
        )
    return comandos_aplicados


def enviar_mensaje(emisor: zmq.Socket, tipo: str, datos: dict[str, object]) -> None:
    emisor.send_json({"tipo": tipo, "datos": datos})


def imprimir_fin_dia_simulado(hora_simulada: str, tick: int) -> None:
    ancho = 64
    borde = "+" + "=" * (ancho - 2) + "+"
    lineas = [
        "",
        borde,
        "|" + " " * (ancho - 2) + "|",
        "|" + "FIN DEL DIA DE SIMULACION".center(ancho - 2) + "|",
        "|" + "GESTION INTELIGENTE DE TRAFICO URBANO".center(ancho - 2) + "|",
        "|" + " " * (ancho - 2) + "|",
        "|" + f"Hora simulada final: {hora_simulada}".center(ancho - 2) + "|",
        "|" + f"Tick final: {tick}".center(ancho - 2) + "|",
        "|" + " " * (ancho - 2) + "|",
        borde,
    ]
    print(
        "\n".join(lineas),
        flush=True,
    )


def procesar_solicitudes_ambulancia(
    receptor_ambulancias: zmq.Socket,
    motor: MotorSimulacion,
) -> int:
    ambulancias_creadas = 0
    while True:
        try:
            carga = receptor_ambulancias.recv_json(flags=zmq.NOBLOCK)
        except zmq.Again:
            break

        solicitud = SolicitudAmbulancia.desde_dict(carga)
        ambulancia = motor.inyectar_ambulancia(
            nodo_origen=solicitud.nodo_origen,
            velocidad=solicitud.velocidad,
        )
        if ambulancia is None:
            log(
                "PC0-Simulacion",
                f"Solicitud de ambulancia descartada: nodo {solicitud.nodo_origen} no tiene via de entrada.",
                hora_simulada=motor.obtener_hora_simulada_actual(),
            )
            continue
        ambulancias_creadas += 1
        log(
            "PC0-Simulacion",
            (
                f"Ambulancia {ambulancia.id_vehiculo} creada en {solicitud.nodo_origen} "
                f"con velocidad {ambulancia.velocidad:.2f}."
            ),
            hora_simulada=motor.obtener_hora_simulada_actual(),
        )
    return ambulancias_creadas


def main() -> None:
    raiz = Path(__file__).resolve().parents[2]
    config = cargar_configuracion(raiz / "config/system_config.json")
    ciudad_mapa = CiudadMapa.desde_config(config["ciudad"])
    motor = MotorSimulacion(
        ciudad_mapa=ciudad_mapa,
        config_simulacion=config["simulacion"],
        pesos_sensores=config["analitica"]["pesos"],
    )

    contexto = zmq.Context()
    receptor_comandos = contexto.socket(zmq.PULL)
    receptor_comandos.bind(config["zmq"]["pc0"]["entrada_comandos"])
    receptor_ambulancias = contexto.socket(zmq.PULL)
    receptor_ambulancias.bind(config["zmq"]["pc0"]["solicitudes_ambulancia"])

    emisor_estado_pc1 = contexto.socket(zmq.PUSH)
    emisor_estado_pc1.connect(config["zmq"]["pc1"]["entrada_estado_operativo"])

    emisor_pc3 = contexto.socket(zmq.PUSH)
    emisor_pc3.connect(config["zmq"]["pc3"]["ingesta_principal"])
    configurar_emisor_mejor_esfuerzo(emisor_pc3)

    emisor_pc2 = contexto.socket(zmq.PUSH)
    emisor_pc2.connect(config["zmq"]["pc2"]["ingesta_replicada"])

    emisor_pc0 = contexto.socket(zmq.PUSH)
    emisor_pc0.connect(config["zmq"]["pc0"]["ingesta_historica"])

    intervalo_tick = float(config["simulacion"]["tick_segundos_reales"])
    intervalo_snapshot_ticks = max(1, int(config["simulacion"].get("intervalo_snapshot_ticks", 1)))
    ultimo_tick_snapshot_enviado = 0

    log("PC0-Simulacion", "Servicio de simulacion iniciado.")
    while True:
        comandos_aplicados = procesar_comandos_pendientes(receptor_comandos, motor)
        ambulancias_creadas = procesar_solicitudes_ambulancia(receptor_ambulancias, motor)
        resultado = motor.avanzar_tick()
        hora_inicio_simulada, hora_fin_simulada = motor.obtener_rango_simulado()
        hora_simulada = motor.obtener_hora_simulada_actual()
        snapshot_enviado = False

        for vehiculo in resultado.vehiculos_creados:
            via = motor.ciudad_mapa.vias[vehiculo.via_actual]
            log(
                "PC0-Simulacion",
                (
                    f"Vehiculo creado: id={vehiculo.id_vehiculo}, tipo={vehiculo.tipo}, "
                    f"via={vehiculo.via_actual}, origen={via.origen}, destino={via.destino}, "
                    f"direccion={vehiculo.direccion_actual}, velocidad={vehiculo.velocidad:.2f}, "
                    f"estado={vehiculo.estado}, tick={resultado.tick}, hora_simulada={hora_simulada}."
                ),
                hora_simulada=hora_simulada,
            )

        for vehiculo in resultado.vehiculos_eliminados:
            log(
                "PC0-Simulacion",
                (
                    f"Vehiculo retirado: id={vehiculo['vehiculo_id']}, tipo={vehiculo['tipo']}, "
                    f"via={vehiculo['via_actual']}, nodo_final={vehiculo['nodo_final']}, "
                    f"direccion={vehiculo['direccion_actual']}, velocidad={float(vehiculo['velocidad']):.2f}, "
                    f"motivo={vehiculo['motivo']}, tick={resultado.tick}, hora_simulada={hora_simulada}."
                ),
                hora_simulada=hora_simulada,
            )

        if (
            ultimo_tick_snapshot_enviado == 0
            or resultado.tick - ultimo_tick_snapshot_enviado >= intervalo_snapshot_ticks
        ):
            snapshot_operativo = motor.generar_snapshot_operativo(resultado_tick=resultado)
            snapshot_dict = snapshot_operativo.a_dict()

            enviar_mensaje(emisor_estado_pc1, "snapshot_operativo", snapshot_dict)
            enviar_json_mejor_esfuerzo(
                emisor_pc3,
                {"tipo": "snapshot_operativo", "datos": snapshot_dict},
            )
            enviar_mensaje(emisor_pc2, "snapshot_operativo", snapshot_dict)
            enviar_mensaje(emisor_pc0, "snapshot_operativo", snapshot_dict)

            ultimo_tick_snapshot_enviado = resultado.tick
            snapshot_enviado = True

        log(
            "PC0-Simulacion",
            (
                f"Tick {resultado.tick}: hora_simulada={hora_simulada}, "
                f"rango={hora_inicio_simulada}-{hora_fin_simulada}, creados={resultado.creados}, "
                f"movidos={resultado.movidos}, eliminados={resultado.eliminados}, "
                f"comandos_aplicados={comandos_aplicados}, ambulancias_creadas={ambulancias_creadas}, "
                f"snapshot_enviado={snapshot_enviado}."
            ),
            hora_simulada=hora_simulada,
        )
        if motor.simulacion_finalizada():
            log(
                "PC0-Simulacion",
                (
                    "Hora final de simulacion alcanzada. "
                    "PC0 detiene la generacion de ticks y cierra el dia simulado."
                ),
                hora_simulada=hora_simulada,
            )
            time.sleep(0.25)
            imprimir_fin_dia_simulado(hora_simulada=hora_simulada, tick=resultado.tick)
            return
        time.sleep(intervalo_tick)


if __name__ == "__main__":
    main()
