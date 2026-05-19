from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable


def indice_a_fila(indice: int) -> str:
    letras: list[str] = []
    numero = indice
    while True:
        numero, resto = divmod(numero, 26)
        letras.append(chr(ord("A") + resto))
        if numero == 0:
            break
        numero -= 1
    return "".join(reversed(letras))


def construir_id_interseccion(fila: int, columna: int) -> str:
    return f"INT-{indice_a_fila(fila)}{columna + 1}"


@dataclass(slots=True)
class PuntajesVia:
    camara: float
    espira_inductiva: float
    gps: float

    @property
    def score_total(self) -> float:
        return self.camara + self.espira_inductiva + self.gps


@dataclass(slots=True)
class EstadoInterseccion:
    interseccion: str
    score_horizontal: float
    score_vertical: float
    fase_activa: str


@dataclass(slots=True)
class Interseccion:
    id_interseccion: str
    fila: int
    columna: int
    fase_activa: str = "HORIZONTAL"
    fase_alterna: str = "VERTICAL"
    duracion_fase_activa: int = 15
    duracion_fase_alterna: int = 15
    ticks_restantes_fase: int = 15
    ciclo_semaforo_tick: int = 1
    ciclo_semaforo_total: int = 30
    fase_prioritaria: str = "HORIZONTAL"
    duracion_fase_prioritaria: int = 15
    duracion_fase_secundaria: int = 15
    modo_control: str = "AUTO"
    manual_ticks_restantes: int = 0


@dataclass(slots=True)
class NodoBorde:
    id_nodo: str
    lado: str
    fila: int | None
    columna: int | None


@dataclass(slots=True)
class Via:
    id_via: str
    origen: str
    destino: str
    direccion: str
    eje: str
    longitud: float
    vehiculos_en_circulacion: int = 0
    vehiculos_en_espera: int = 0
    velocidad_promedio: float = 0.0
    flujo_vehicular: int = 0
    score: float = 0.0
    estado_congestion: str = "NORMAL"


@dataclass(slots=True)
class CiudadMapa:
    intersecciones: dict[str, Interseccion] = field(default_factory=dict)
    nodos_borde: dict[str, NodoBorde] = field(default_factory=dict)
    vias: dict[str, Via] = field(default_factory=dict)
    tick_actual: int = 0

    @classmethod
    def desde_config(cls, config_ciudad: dict[str, object]) -> "CiudadMapa":
        filas = int(config_ciudad["tamano_cuadricula"]["filas"])
        columnas = int(config_ciudad["tamano_cuadricula"]["columnas"])
        longitud_min = float(config_ciudad["longitud_vias"]["min"])
        longitud_max = float(config_ciudad["longitud_vias"]["max"])
        randomizador = random.Random(int(config_ciudad.get("semilla", 0)))

        ciudad = cls()
        ciudad.intersecciones = cls._crear_intersecciones(filas, columnas)
        ciudad.nodos_borde = cls._crear_nodos_borde(filas, columnas)
        ciudad.vias = cls._crear_vias(
            filas=filas,
            columnas=columnas,
            longitud_min=longitud_min,
            longitud_max=longitud_max,
            randomizador=randomizador,
        )
        return ciudad

    @staticmethod
    def _crear_intersecciones(filas: int, columnas: int) -> dict[str, Interseccion]:
        resultado: dict[str, Interseccion] = {}
        for fila in range(filas):
            for columna in range(columnas):
                identificador = construir_id_interseccion(fila, columna)
                fase_inicial = "HORIZONTAL" if (fila + columna) % 2 == 0 else "VERTICAL"
                fase_alterna = "VERTICAL" if fase_inicial == "HORIZONTAL" else "HORIZONTAL"
                resultado[identificador] = Interseccion(
                    id_interseccion=identificador,
                    fila=fila,
                    columna=columna,
                    fase_activa=fase_inicial,
                    fase_alterna=fase_alterna,
                    ciclo_semaforo_tick=16,
                    fase_prioritaria=fase_inicial,
                )
        return resultado

    @staticmethod
    def _crear_nodos_borde(filas: int, columnas: int) -> dict[str, NodoBorde]:
        bordes: dict[str, NodoBorde] = {}
        for columna in range(columnas):
            bordes[f"BORDE-N-{columna + 1}"] = NodoBorde(
                id_nodo=f"BORDE-N-{columna + 1}",
                lado="NORTE",
                fila=None,
                columna=columna,
            )
            bordes[f"BORDE-S-{columna + 1}"] = NodoBorde(
                id_nodo=f"BORDE-S-{columna + 1}",
                lado="SUR",
                fila=None,
                columna=columna,
            )
        for fila in range(filas):
            etiqueta = indice_a_fila(fila)
            bordes[f"BORDE-O-{etiqueta}"] = NodoBorde(
                id_nodo=f"BORDE-O-{etiqueta}",
                lado="OESTE",
                fila=fila,
                columna=None,
            )
            bordes[f"BORDE-E-{etiqueta}"] = NodoBorde(
                id_nodo=f"BORDE-E-{etiqueta}",
                lado="ESTE",
                fila=fila,
                columna=None,
            )
        return bordes

    @classmethod
    def _crear_vias(
        cls,
        filas: int,
        columnas: int,
        longitud_min: float,
        longitud_max: float,
        randomizador: random.Random,
    ) -> dict[str, Via]:
        vias: dict[str, Via] = {}

        def agregar_via(origen: str, destino: str, direccion: str, eje: str) -> None:
            via_id = f"VIA-{origen}-A-{destino}"
            vias[via_id] = Via(
                id_via=via_id,
                origen=origen,
                destino=destino,
                direccion=direccion,
                eje=eje,
                longitud=round(randomizador.uniform(longitud_min, longitud_max), 2),
            )

        for fila in range(filas):
            sentido_este = fila % 2 == 0
            etiqueta = indice_a_fila(fila)
            if sentido_este:
                agregar_via(f"BORDE-O-{etiqueta}", construir_id_interseccion(fila, 0), "ESTE", "HORIZONTAL")
                for columna in range(columnas - 1):
                    agregar_via(
                        construir_id_interseccion(fila, columna),
                        construir_id_interseccion(fila, columna + 1),
                        "ESTE",
                        "HORIZONTAL",
                    )
                agregar_via(
                    construir_id_interseccion(fila, columnas - 1),
                    f"BORDE-E-{etiqueta}",
                    "ESTE",
                    "HORIZONTAL",
                )
            else:
                agregar_via(f"BORDE-E-{etiqueta}", construir_id_interseccion(fila, columnas - 1), "OESTE", "HORIZONTAL")
                for columna in range(columnas - 1, 0, -1):
                    agregar_via(
                        construir_id_interseccion(fila, columna),
                        construir_id_interseccion(fila, columna - 1),
                        "OESTE",
                        "HORIZONTAL",
                    )
                agregar_via(
                    construir_id_interseccion(fila, 0),
                    f"BORDE-O-{etiqueta}",
                    "OESTE",
                    "HORIZONTAL",
                )

        for columna in range(columnas):
            sentido_norte = columna % 2 == 0
            if sentido_norte:
                agregar_via(f"BORDE-S-{columna + 1}", construir_id_interseccion(filas - 1, columna), "NORTE", "VERTICAL")
                for fila in range(filas - 1, 0, -1):
                    agregar_via(
                        construir_id_interseccion(fila, columna),
                        construir_id_interseccion(fila - 1, columna),
                        "NORTE",
                        "VERTICAL",
                    )
                agregar_via(
                    construir_id_interseccion(0, columna),
                    f"BORDE-N-{columna + 1}",
                    "NORTE",
                    "VERTICAL",
                )
            else:
                agregar_via(f"BORDE-N-{columna + 1}", construir_id_interseccion(0, columna), "SUR", "VERTICAL")
                for fila in range(filas - 1):
                    agregar_via(
                        construir_id_interseccion(fila, columna),
                        construir_id_interseccion(fila + 1, columna),
                        "SUR",
                        "VERTICAL",
                    )
                agregar_via(
                    construir_id_interseccion(filas - 1, columna),
                    f"BORDE-S-{columna + 1}",
                    "SUR",
                    "VERTICAL",
                )

        return vias

    def iterar_vias(self) -> Iterable[Via]:
        return self.vias.values()

    def obtener_vias_de_entrada(self, interseccion: str) -> list[Via]:
        return [via for via in self.vias.values() if via.destino == interseccion]

    def obtener_vias_instrumentadas(self) -> list[Via]:
        return [via for via in self.vias.values() if via.destino in self.intersecciones]

    def obtener_vias_por_eje(self, interseccion: str, eje: str) -> list[Via]:
        return [via for via in self.obtener_vias_de_entrada(interseccion) if via.eje == eje]

    def obtener_vias_salida(self, nodo: str) -> list[Via]:
        return [via for via in self.vias.values() if via.origen == nodo]

    def es_interseccion(self, nodo: str) -> bool:
        return nodo in self.intersecciones

    def es_nodo_borde(self, nodo: str) -> bool:
        return nodo in self.nodos_borde

    def obtener_intersecciones_activas(self) -> list[str]:
        return sorted(self.intersecciones.keys())

    def aplicar_programacion_semaforo(
        self,
        interseccion_id: str,
        fase_ganadora: str,
        tiempo_verde: float,
        tiempo_opuesto: float,
    ) -> None:
        interseccion = self.intersecciones[interseccion_id]
        total = interseccion.ciclo_semaforo_total
        duracion_prioritaria = self._normalizar_ticks_ciclo(tiempo_verde, total)
        duracion_secundaria = total - duracion_prioritaria

        interseccion.modo_control = "AUTO"
        interseccion.manual_ticks_restantes = 0
        interseccion.fase_prioritaria = fase_ganadora
        interseccion.duracion_fase_prioritaria = duracion_prioritaria
        interseccion.duracion_fase_secundaria = duracion_secundaria
        self.actualizar_fase_por_ciclo(interseccion)

    def forzar_programacion_semaforo(
        self,
        interseccion_id: str,
        fase_ganadora: str,
        duracion_ticks: float,
    ) -> None:
        interseccion = self.intersecciones[interseccion_id]
        duracion = -1 if float(duracion_ticks) < 0 else max(1, int(round(duracion_ticks)))
        interseccion.modo_control = "MANUAL"
        interseccion.manual_ticks_restantes = duracion
        interseccion.fase_activa = fase_ganadora
        interseccion.fase_alterna = self.fase_opuesta(fase_ganadora)
        interseccion.duracion_fase_activa = duracion
        interseccion.duracion_fase_alterna = 0
        interseccion.ticks_restantes_fase = duracion

    @staticmethod
    def fase_opuesta(fase: str) -> str:
        return "VERTICAL" if fase == "HORIZONTAL" else "HORIZONTAL"

    @staticmethod
    def _normalizar_ticks_ciclo(valor: float, total: int) -> int:
        return min(max(int(float(valor) + 0.5), 0), total)

    def actualizar_fase_por_ciclo(self, interseccion: Interseccion) -> None:
        total = max(1, int(interseccion.ciclo_semaforo_total))
        contador = ((int(interseccion.ciclo_semaforo_tick) - 1) % total) + 1
        interseccion.ciclo_semaforo_total = total
        interseccion.ciclo_semaforo_tick = contador

        fase_prioritaria = interseccion.fase_prioritaria
        fase_secundaria = self.fase_opuesta(fase_prioritaria)
        duracion_prioritaria = self._normalizar_ticks_ciclo(interseccion.duracion_fase_prioritaria, total)
        duracion_secundaria = total - duracion_prioritaria

        interseccion.duracion_fase_prioritaria = duracion_prioritaria
        interseccion.duracion_fase_secundaria = duracion_secundaria

        if duracion_secundaria > 0 and contador <= duracion_secundaria:
            interseccion.fase_activa = fase_secundaria
            interseccion.fase_alterna = fase_prioritaria
            interseccion.duracion_fase_activa = duracion_secundaria
            interseccion.duracion_fase_alterna = duracion_prioritaria
            interseccion.ticks_restantes_fase = duracion_secundaria - contador + 1
            return

        interseccion.fase_activa = fase_prioritaria
        interseccion.fase_alterna = fase_secundaria
        interseccion.duracion_fase_activa = duracion_prioritaria
        interseccion.duracion_fase_alterna = duracion_secundaria
        interseccion.ticks_restantes_fase = total - contador + 1

    def resumir_interseccion(self, interseccion: str) -> dict[str, object]:
        vias_entrada = self.obtener_vias_de_entrada(interseccion)
        return {
            "interseccion": interseccion,
            "cantidad_vias_entrada": len(vias_entrada),
            "vias": [
                {
                    "id_via": via.id_via,
                    "origen": via.origen,
                    "eje": via.eje,
                    "direccion": via.direccion,
                    "longitud": via.longitud,
                    "vehiculos_en_circulacion": via.vehiculos_en_circulacion,
                    "vehiculos_en_espera": via.vehiculos_en_espera,
                    "velocidad_promedio": via.velocidad_promedio,
                    "flujo_vehicular": via.flujo_vehicular,
                    "estado_congestion": via.estado_congestion,
                }
                for via in vias_entrada
            ],
        }
