from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from common.mensajes.comandos import ComandoSemaforo
from common.mensajes.estado_operativo import SnapshotOperativo
from common.modelos.trafico import CiudadMapa, Via
from common.modelos.vehiculos import Vehiculo


@dataclass(slots=True)
class ResultadoTick:
    tick: int
    creados: int
    eliminados: int
    movidos: int
    vehiculos_creados: list[Vehiculo]
    vehiculos_eliminados: list[dict[str, str | float]]


class MotorSimulacion:
    def __init__(self, ciudad_mapa: CiudadMapa, config_simulacion: dict[str, object]) -> None:
        self.ciudad_mapa = ciudad_mapa
        self.config = config_simulacion
        self.randomizador = random.Random(int(config_simulacion.get("semilla", 0)))
        self.vehiculos: dict[str, Vehiculo] = {}
        self.contador_vehiculos = 0
        self.contador_ambulancias = 0
        self.minutos_simulados_por_tick = int(config_simulacion.get("minutos_simulados_por_tick", 1))
        self.hora_inicio_simulada = str(config_simulacion.get("hora_inicio_simulada", "12:00"))
        self.hora_fin_simulada = str(config_simulacion.get("hora_fin_simulada", "18:00"))
        self.vias_entrada = [
            via for via in self.ciudad_mapa.iterar_vias() if self.ciudad_mapa.es_nodo_borde(via.origen)
        ]

    def avanzar_tick(self) -> ResultadoTick:
        self.ciudad_mapa.tick_actual += 1
        for via in self.ciudad_mapa.iterar_vias():
            via.flujo_vehicular = 0
        vehiculos_creados = self._generar_vehiculos()
        movidos = 0
        eliminados = 0
        vehiculos_eliminados: list[dict[str, str | float]] = []

        for vehiculo in list(self.vehiculos.values()):
            if vehiculo.estado == "CIRCULANDO":
                vehiculo.posicion_en_via += vehiculo.velocidad
                movidos += 1

            via_actual = self.ciudad_mapa.vias[vehiculo.via_actual]
            if vehiculo.posicion_en_via < via_actual.longitud:
                continue

            if self.ciudad_mapa.es_nodo_borde(via_actual.destino):
                vehiculos_eliminados.append(
                    {
                        "vehiculo_id": vehiculo.id_vehiculo,
                        "tipo": vehiculo.tipo,
                        "via_actual": vehiculo.via_actual,
                        "direccion_actual": vehiculo.direccion_actual,
                        "velocidad": vehiculo.velocidad,
                        "motivo": "SALIDA_DE_LA_CIUDAD",
                        "nodo_final": via_actual.destino,
                    }
                )
                del self.vehiculos[vehiculo.id_vehiculo]
                eliminados += 1
                continue

            interseccion = self.ciudad_mapa.intersecciones[via_actual.destino]
            if interseccion.fase_activa != via_actual.eje:
                vehiculo.estado = "EN_COLA"
                vehiculo.posicion_en_via = via_actual.longitud
                continue

            siguiente_via = self._escoger_siguiente_via(via_actual)
            if siguiente_via is None:
                vehiculos_eliminados.append(
                    {
                        "vehiculo_id": vehiculo.id_vehiculo,
                        "tipo": vehiculo.tipo,
                        "via_actual": vehiculo.via_actual,
                        "direccion_actual": vehiculo.direccion_actual,
                        "velocidad": vehiculo.velocidad,
                        "motivo": "SIN_SALIDA_DISPONIBLE",
                        "nodo_final": via_actual.destino,
                    }
                )
                del self.vehiculos[vehiculo.id_vehiculo]
                eliminados += 1
                continue

            via_actual.flujo_vehicular += 1
            vehiculo.via_actual = siguiente_via.id_via
            vehiculo.direccion_actual = siguiente_via.direccion
            vehiculo.posicion_en_via = 0.0
            vehiculo.estado = "CIRCULANDO"

        self._actualizar_metricas_vias()
        self._actualizar_fases_semaforicas()
        return ResultadoTick(
            tick=self.ciudad_mapa.tick_actual,
            creados=len(vehiculos_creados),
            eliminados=eliminados,
            movidos=movidos,
            vehiculos_creados=vehiculos_creados,
            vehiculos_eliminados=vehiculos_eliminados,
        )

    def aplicar_comando_semaforo(self, comando: ComandoSemaforo) -> None:
        self.ciudad_mapa.aplicar_programacion_semaforo(
            interseccion_id=comando.interseccion,
            fase_ganadora=comando.fase_ganadora,
            tiempo_verde=comando.tiempo_verde,
            tiempo_opuesto=comando.tiempo_opuesto,
        )

    def generar_snapshot_operativo(self) -> SnapshotOperativo:
        timestamp = datetime.now(timezone.utc).isoformat()
        return SnapshotOperativo.crear(
            timestamp=timestamp,
            tick_actual=self.ciudad_mapa.tick_actual,
            intersecciones=[
                {
                    "interseccion_id": interseccion.id_interseccion,
                    "fase_activa": interseccion.fase_activa,
                    "fase_alterna": interseccion.fase_alterna,
                    "duracion_fase_activa": interseccion.duracion_fase_activa,
                    "duracion_fase_alterna": interseccion.duracion_fase_alterna,
                    "ticks_restantes_fase": interseccion.ticks_restantes_fase,
                }
                for interseccion in self.ciudad_mapa.intersecciones.values()
            ],
            vias=[
                {
                    "via_id": via.id_via,
                    "origen": via.origen,
                    "destino": via.destino,
                    "direccion": via.direccion,
                    "eje": via.eje,
                    "longitud": via.longitud,
                    "vehiculos_en_circulacion": via.vehiculos_en_circulacion,
                    "vehiculos_en_espera": via.vehiculos_en_espera,
                    "velocidad_promedio": via.velocidad_promedio,
                    "flujo_vehicular": via.flujo_vehicular,
                    "score": via.score,
                    "estado_congestion": via.estado_congestion,
                }
                for via in self.ciudad_mapa.iterar_vias()
            ],
            vehiculos=[
                {
                    "vehiculo_id": vehiculo.id_vehiculo,
                    "via_actual": vehiculo.via_actual,
                    "posicion_en_via": vehiculo.posicion_en_via,
                    "velocidad": vehiculo.velocidad,
                    "direccion_actual": vehiculo.direccion_actual,
                    "estado": vehiculo.estado,
                    "tipo": vehiculo.tipo,
                }
                for vehiculo in self.vehiculos.values()
            ],
        )

    def inyectar_ambulancia(self, nodo_origen: str, velocidad: float | None = None) -> Vehiculo | None:
        opciones = [via for via in self.vias_entrada if via.origen == nodo_origen]
        if not opciones:
            return None

        velocidad_config = float(self.config.get("ambulancias", {}).get("velocidad_constante", 45))
        via = self.randomizador.choice(opciones)
        self.contador_ambulancias += 1
        vehiculo_id = f"AMB-{self.contador_ambulancias:05d}"
        vehiculo = Vehiculo(
            id_vehiculo=vehiculo_id,
            via_actual=via.id_via,
            posicion_en_via=0.0,
            velocidad=float(velocidad if velocidad is not None else velocidad_config),
            direccion_actual=via.direccion,
            estado="CIRCULANDO",
            tipo="AMBULANCIA",
        )
        self.vehiculos[vehiculo_id] = vehiculo
        return vehiculo

    def obtener_hora_simulada_actual(self) -> str:
        hora_base = datetime.strptime(self.hora_inicio_simulada, "%H:%M")
        desplazamiento = timedelta(minutes=self.ciudad_mapa.tick_actual * self.minutos_simulados_por_tick)
        hora_actual = hora_base + desplazamiento
        return hora_actual.strftime("%H:%M")

    def obtener_rango_simulado(self) -> tuple[str, str]:
        return self.hora_inicio_simulada, self.hora_fin_simulada

    def _generar_vehiculos(self) -> list[Vehiculo]:
        max_nuevos = int(self.config["max_nuevos_por_tick"])
        probabilidad = float(self.config["probabilidad_generacion_por_via"])
        velocidad_min = float(self.config["velocidad_inicial"]["min"])
        velocidad_max = float(self.config["velocidad_inicial"]["max"])
        creados: list[Vehiculo] = []

        for via in self.vias_entrada:
            if len(creados) >= max_nuevos:
                break
            if self.randomizador.random() > probabilidad:
                continue
            self.contador_vehiculos += 1
            vehiculo_id = f"VEH-{self.contador_vehiculos:05d}"
            velocidad = round(self.randomizador.uniform(velocidad_min, velocidad_max), 2)
            vehiculo = Vehiculo(
                id_vehiculo=vehiculo_id,
                via_actual=via.id_via,
                posicion_en_via=0.0,
                velocidad=velocidad,
                direccion_actual=via.direccion,
                estado="CIRCULANDO",
            )
            self.vehiculos[vehiculo_id] = vehiculo
            creados.append(vehiculo)

        return creados

    def _escoger_siguiente_via(self, via_actual: Via) -> Via | None:
        opciones = self.ciudad_mapa.obtener_vias_salida(via_actual.destino)
        if not opciones:
            return None

        seguir_derecho = next((via for via in opciones if via.direccion == via_actual.direccion), None)
        curvas = [via for via in opciones if via.direccion != via_actual.direccion]

        candidatos: list[Via] = []
        if seguir_derecho is not None:
            candidatos.append(seguir_derecho)
        if curvas:
            candidatos.append(self.randomizador.choice(curvas))

        if not candidatos:
            return self.randomizador.choice(opciones)
        return self.randomizador.choice(candidatos)

    def _actualizar_metricas_vias(self) -> None:
        for via in self.ciudad_mapa.iterar_vias():
            via.vehiculos_en_circulacion = 0
            via.vehiculos_en_espera = 0
            via.velocidad_promedio = 0.0
            via.estado_congestion = "BAJA"
            via.score = 0.0

        agrupados: dict[str, list[Vehiculo]] = {via.id_via: [] for via in self.ciudad_mapa.iterar_vias()}
        for vehiculo in self.vehiculos.values():
            agrupados[vehiculo.via_actual].append(vehiculo)

        for via_id, vehiculos in agrupados.items():
            via = self.ciudad_mapa.vias[via_id]
            en_cola = [vehiculo for vehiculo in vehiculos if vehiculo.estado == "EN_COLA"]
            circulando = [vehiculo for vehiculo in vehiculos if vehiculo.estado == "CIRCULANDO"]

            via.vehiculos_en_circulacion = len(circulando)
            via.vehiculos_en_espera = len(en_cola)
            if circulando:
                via.velocidad_promedio = round(
                    sum(vehiculo.velocidad for vehiculo in circulando) / len(circulando), 2
                )
            via.score = min(via.vehiculos_en_espera / 10.0, 1.0)

            if via.vehiculos_en_espera >= 8 or (
                via.vehiculos_en_circulacion > 0 and via.velocidad_promedio < 15
            ):
                via.estado_congestion = "ALTA"
            elif via.vehiculos_en_espera >= 4:
                via.estado_congestion = "NORMAL"
            else:
                via.estado_congestion = "BAJA"

    def _actualizar_fases_semaforicas(self) -> None:
        for interseccion in self.ciudad_mapa.intersecciones.values():
            interseccion.ticks_restantes_fase = max(interseccion.ticks_restantes_fase - 1, 0)
            if interseccion.ticks_restantes_fase > 0:
                continue

            interseccion.fase_activa, interseccion.fase_alterna = (
                interseccion.fase_alterna,
                interseccion.fase_activa,
            )
            interseccion.duracion_fase_activa, interseccion.duracion_fase_alterna = (
                interseccion.duracion_fase_alterna,
                interseccion.duracion_fase_activa,
            )
            interseccion.ticks_restantes_fase = interseccion.duracion_fase_activa
