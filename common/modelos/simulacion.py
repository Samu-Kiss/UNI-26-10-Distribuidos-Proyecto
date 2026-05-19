from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from common.mensajes.comandos import ComandoSemaforo
from common.mensajes.estado_operativo import SnapshotOperativo
from common.modelos.trafico import CiudadMapa, Via
from common.modelos.vehiculos import Vehiculo
from common.utilidades.normalizacion_sensores import normalizar_camara, normalizar_espira, normalizar_gps


@dataclass(slots=True)
class ResultadoTick:
    tick: int
    creados: int
    eliminados: int
    movidos: int
    vehiculos_creados: list[Vehiculo]
    vehiculos_eliminados: list[dict[str, str | float]]


class MotorSimulacion:
    def __init__(
        self,
        ciudad_mapa: CiudadMapa,
        config_simulacion: dict[str, object],
        pesos_sensores: dict[str, float] | None = None,
    ) -> None:
        self.ciudad_mapa = ciudad_mapa
        self.config = config_simulacion
        self.randomizador = random.Random(int(config_simulacion.get("semilla", 0)))
        self.vehiculos: dict[str, Vehiculo] = {}
        self.contador_vehiculos = 0
        self.contador_ambulancias = 0
        self.minutos_simulados_por_tick = int(config_simulacion.get("minutos_simulados_por_tick", 1))
        self.hora_inicio_simulada = str(config_simulacion.get("hora_inicio_simulada", "12:00"))
        self.hora_fin_simulada = str(config_simulacion.get("hora_fin_simulada", "18:00"))
        self.modo_bucle_infinito = bool(config_simulacion.get("modo_bucle_infinito", False))
        pesos_base = pesos_sensores or {"camara": 0.5, "espira_inductiva": 0.35, "gps": 0.15}
        self.pesos_sensores = {
            "camara": float(pesos_base.get("camara", 0.5)),
            "espira_inductiva": float(pesos_base.get("espira_inductiva", 0.35)),
            "gps": float(pesos_base.get("gps", 0.15)),
        }
        self.vias_entrada = [
            via for via in self.ciudad_mapa.iterar_vias() if self.ciudad_mapa.es_nodo_borde(via.origen)
        ]

    def avanzar_tick(self) -> ResultadoTick:
        self.ciudad_mapa.tick_actual += 1
        for via in self.ciudad_mapa.iterar_vias():
            via.flujo_vehicular = 0
        self._actualizar_fases_semaforicas()
        vehiculos_creados = self._generar_vehiculos()
        movidos = 0
        eliminados = 0
        vehiculos_eliminados: list[dict[str, str | float]] = []

        for vehiculo in list(self.vehiculos.values()):
            via_actual = self.ciudad_mapa.vias[vehiculo.via_actual]
            if vehiculo.estado == "CIRCULANDO":
                siguiente_posicion = vehiculo.posicion_en_via + vehiculo.velocidad
                if self._semaforo_bloquea_llegada(via_actual, siguiente_posicion):
                    vehiculo.posicion_en_via = via_actual.longitud
                    vehiculo.estado = "EN_COLA"
                    movidos += 1
                    continue
                vehiculo.posicion_en_via = siguiente_posicion
                movidos += 1

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
        return ResultadoTick(
            tick=self.ciudad_mapa.tick_actual,
            creados=len(vehiculos_creados),
            eliminados=eliminados,
            movidos=movidos,
            vehiculos_creados=vehiculos_creados,
            vehiculos_eliminados=vehiculos_eliminados,
        )

    def aplicar_comando_semaforo(self, comando: ComandoSemaforo) -> None:
        if comando.modo == "MANUAL":
            self.ciudad_mapa.forzar_programacion_semaforo(
                interseccion_id=comando.interseccion,
                fase_ganadora=comando.fase_ganadora,
                duracion_ticks=comando.tiempo_verde,
            )
            return
        self.ciudad_mapa.aplicar_programacion_semaforo(
            interseccion_id=comando.interseccion,
            fase_ganadora=comando.fase_ganadora,
            tiempo_verde=comando.tiempo_verde,
            tiempo_opuesto=comando.tiempo_opuesto,
        )

    def generar_snapshot_operativo(self, resultado_tick: ResultadoTick | None = None) -> SnapshotOperativo:
        timestamp = datetime.now(timezone.utc).isoformat()
        metricas_tick = {}
        if resultado_tick is not None:
            metricas_tick = {
                "creados": resultado_tick.creados,
                "eliminados": resultado_tick.eliminados,
                "movidos": resultado_tick.movidos,
            }
        return SnapshotOperativo.crear(
            timestamp=timestamp,
            tick_actual=self.ciudad_mapa.tick_actual,
            metricas_tick=metricas_tick,
            intersecciones=[
                {
                    "interseccion_id": interseccion.id_interseccion,
                    "fase_activa": interseccion.fase_activa,
                    "fase_alterna": interseccion.fase_alterna,
                    "duracion_fase_activa": interseccion.duracion_fase_activa,
                    "duracion_fase_alterna": interseccion.duracion_fase_alterna,
                    "ticks_restantes_fase": interseccion.ticks_restantes_fase,
                    "ciclo_semaforo_tick": interseccion.ciclo_semaforo_tick,
                    "ciclo_semaforo_total": interseccion.ciclo_semaforo_total,
                    "fase_prioritaria": interseccion.fase_prioritaria,
                    "duracion_fase_prioritaria": interseccion.duracion_fase_prioritaria,
                    "duracion_fase_secundaria": interseccion.duracion_fase_secundaria,
                    "modo_control": interseccion.modo_control,
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
        hora_base = datetime.strptime("00:00" if self.modo_bucle_infinito else self.hora_inicio_simulada, "%H:%M")
        desplazamiento = timedelta(minutes=self.ciudad_mapa.tick_actual * self.minutos_simulados_por_tick)
        hora_actual = hora_base + desplazamiento
        if self.modo_bucle_infinito:
            minutos = (hora_actual.hour * 60 + hora_actual.minute) % (24 * 60)
            return f"{minutos // 60:02d}:{minutos % 60:02d}"
        return hora_actual.strftime("%H:%M")

    def obtener_rango_simulado(self) -> tuple[str, str]:
        if self.modo_bucle_infinito:
            return "00:00", "23:59"
        return self.hora_inicio_simulada, self.hora_fin_simulada

    def _minutos_desde_medianoche(self, hora: str) -> int:
        hora_parseada = datetime.strptime(hora, "%H:%M")
        return hora_parseada.hour * 60 + hora_parseada.minute

    def minutos_simulados_transcurridos(self) -> int:
        return self.ciudad_mapa.tick_actual * self.minutos_simulados_por_tick

    def simulacion_finalizada(self) -> bool:
        if self.modo_bucle_infinito:
            return False
        inicio = self._minutos_desde_medianoche(self.hora_inicio_simulada)
        fin = self._minutos_desde_medianoche(self.hora_fin_simulada)
        duracion_dia = fin - inicio
        if duracion_dia <= 0:
            duracion_dia += 24 * 60
        return self.minutos_simulados_transcurridos() >= duracion_dia

    def _generar_vehiculos(self) -> list[Vehiculo]:
        max_nuevos_por_entrada = max(
            0,
            int(self.config.get("max_nuevos_por_entrada", self.config["max_nuevos_por_tick"])),
        )
        min_nuevos_por_entrada = max(
            0,
            int(self.config.get("min_nuevos_por_entrada", self.config.get("min_nuevos_por_tick", 0))),
        )
        min_nuevos_por_entrada = min(min_nuevos_por_entrada, max_nuevos_por_entrada)
        probabilidad = float(self.config["probabilidad_generacion_por_via"])
        velocidad_min = float(self.config["velocidad_inicial"]["min"])
        velocidad_max = float(self.config["velocidad_inicial"]["max"])
        creados: list[Vehiculo] = []

        def crear_vehiculo(via: Via) -> None:
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

        for via in self.vias_entrada:
            if self.randomizador.random() > probabilidad:
                continue
            cantidad = self.randomizador.randint(min_nuevos_por_entrada, max_nuevos_por_entrada)
            for _ in range(cantidad):
                crear_vehiculo(via)

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

    def _semaforo_bloquea_llegada(self, via_actual: Via, siguiente_posicion: float) -> bool:
        if siguiente_posicion < via_actual.longitud:
            return False
        if self.ciudad_mapa.es_nodo_borde(via_actual.destino):
            return False
        interseccion = self.ciudad_mapa.intersecciones[via_actual.destino]
        return interseccion.fase_activa != via_actual.eje

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
            ambulancia_presente = any(vehiculo.tipo == "AMBULANCIA" for vehiculo in vehiculos)

            via.vehiculos_en_circulacion = len(circulando)
            via.vehiculos_en_espera = len(en_cola)
            if circulando:
                via.velocidad_promedio = round(
                    sum(vehiculo.velocidad for vehiculo in circulando) / len(circulando), 2
                )
            if ambulancia_presente:
                via.score = 1.0
            else:
                nota_camara = normalizar_camara(via.vehiculos_en_espera)
                nota_espira = normalizar_espira(via.vehiculos_en_circulacion)
                nota_gps = normalizar_gps(via.velocidad_promedio)
                via.score = round(
                    nota_camara * self.pesos_sensores["camara"]
                    + nota_espira * self.pesos_sensores["espira_inductiva"]
                    + nota_gps * self.pesos_sensores["gps"],
                    4,
                )

            if via.score > 0.7:
                via.estado_congestion = "ALTA"
            elif via.score >= 0.4:
                via.estado_congestion = "NORMAL"
            else:
                via.estado_congestion = "BAJA"

    def _actualizar_fases_semaforicas(self) -> None:
        for interseccion in self.ciudad_mapa.intersecciones.values():
            interseccion.ciclo_semaforo_tick = (
                interseccion.ciclo_semaforo_tick % interseccion.ciclo_semaforo_total
            ) + 1
            if interseccion.modo_control == "MANUAL":
                if interseccion.manual_ticks_restantes < 0:
                    interseccion.ticks_restantes_fase = -1
                    continue
                interseccion.manual_ticks_restantes = max(interseccion.manual_ticks_restantes - 1, 0)
                interseccion.ticks_restantes_fase = interseccion.manual_ticks_restantes
                if interseccion.manual_ticks_restantes > 0:
                    continue
                interseccion.modo_control = "AUTO"
            self.ciudad_mapa.actualizar_fase_por_ciclo(interseccion)
