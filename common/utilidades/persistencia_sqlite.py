from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class RepositorioSQLite:
    def __init__(self, ruta_bd: str | Path) -> None:
        self.ruta_bd = Path(ruta_bd)
        self.ruta_bd.parent.mkdir(parents=True, exist_ok=True)
        self.conexion = sqlite3.connect(self.ruta_bd, timeout=30)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.execute("PRAGMA journal_mode=WAL")
        self.conexion.execute("PRAGMA synchronous=NORMAL")

    def cerrar(self) -> None:
        self.conexion.close()

    def inicializar_pc3(self) -> None:
        self._crear_tablas_estado_actual()

    def inicializar_pc2(self) -> None:
        self._crear_tablas_estado_actual()

    def inicializar_pc0(self) -> None:
        self._crear_tablas_historial_liviano()
        self._crear_tabla_vehiculos_historico()
        self._asegurar_migraciones_historial()

    def _obtener_tablas(self) -> set[str]:
        cursor = self.conexion.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {str(fila[0]) for fila in cursor.fetchall()}

    def _obtener_columnas_tabla(self, tabla: str) -> set[str]:
        cursor = self.conexion.execute(f"PRAGMA table_info({tabla})")
        return {str(fila[1]) for fila in cursor.fetchall()}

    def _asegurar_columna(self, tabla: str, columna: str, definicion: str) -> None:
        if columna in self._obtener_columnas_tabla(tabla):
            return
        self.conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
        self.conexion.commit()

    def _asegurar_migraciones_historial(self) -> None:
        tablas = self._obtener_tablas()
        if "eventos_sensores" in tablas:
            self._asegurar_columna("eventos_sensores", "tick_origen", "INTEGER NOT NULL DEFAULT 0")
        if "comandos_semaforo" in tablas:
            self._asegurar_columna("comandos_semaforo", "tick_origen", "INTEGER NOT NULL DEFAULT 0")
        self.conexion.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_eventos_sensores_unicos
            ON eventos_sensores (
                timestamp, sensor_id, tipo_sensor, interseccion, via_id, tick_origen, datos_json
            )
            """
        )
        self.conexion.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_comandos_semaforo_unicos
            ON comandos_semaforo (
                timestamp, interseccion, fase_ganadora, tiempo_verde, tiempo_opuesto, tick_origen, razon
            )
            """
        )
        self.conexion.commit()

    def _crear_tablas_estado_actual(self) -> None:
        cursor = self.conexion.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS estado_intersecciones (
                interseccion_id TEXT PRIMARY KEY,
                fase_activa TEXT NOT NULL,
                fase_alterna TEXT NOT NULL,
                duracion_fase_activa INTEGER NOT NULL,
                duracion_fase_alterna INTEGER NOT NULL,
                ticks_restantes_fase INTEGER NOT NULL,
                tick_actual INTEGER NOT NULL,
                actualizado_en TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS estado_vias (
                via_id TEXT PRIMARY KEY,
                origen TEXT NOT NULL,
                destino TEXT NOT NULL,
                direccion TEXT NOT NULL,
                eje TEXT NOT NULL,
                longitud REAL NOT NULL,
                vehiculos_en_circulacion INTEGER NOT NULL,
                vehiculos_en_espera INTEGER NOT NULL,
                velocidad_promedio REAL NOT NULL,
                flujo_vehicular INTEGER NOT NULL,
                score REAL NOT NULL,
                estado_congestion TEXT NOT NULL,
                tick_actual INTEGER NOT NULL,
                actualizado_en TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS estado_vehiculos (
                vehiculo_id TEXT PRIMARY KEY,
                via_actual TEXT NOT NULL,
                posicion_en_via REAL NOT NULL,
                velocidad REAL NOT NULL,
                direccion_actual TEXT NOT NULL,
                estado TEXT NOT NULL,
                tipo TEXT NOT NULL,
                tick_actual INTEGER NOT NULL,
                actualizado_en TEXT NOT NULL
            )
            """
        )
        self.conexion.commit()

    def _crear_tablas_historial_liviano(self) -> None:
        cursor = self.conexion.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS eventos_sensores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                tipo_sensor TEXT NOT NULL,
                interseccion TEXT NOT NULL,
                via_id TEXT NOT NULL,
                tick_origen INTEGER NOT NULL DEFAULT 0,
                datos_json TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comandos_semaforo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                interseccion TEXT NOT NULL,
                fase_ganadora TEXT NOT NULL,
                tiempo_verde REAL NOT NULL,
                tiempo_opuesto REAL NOT NULL,
                tick_origen INTEGER NOT NULL DEFAULT 0,
                razon TEXT NOT NULL
            )
            """
        )
        self.conexion.commit()

    def _crear_tabla_vehiculos_historico(self) -> None:
        cursor = self.conexion.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vehiculos_historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_timestamp TEXT NOT NULL,
                tick_actual INTEGER NOT NULL,
                vehiculo_id TEXT NOT NULL,
                via_actual TEXT NOT NULL,
                posicion_en_via REAL NOT NULL,
                velocidad REAL NOT NULL,
                direccion_actual TEXT NOT NULL,
                estado TEXT NOT NULL,
                tipo TEXT NOT NULL
            )
            """
        )
        self.conexion.commit()

    def guardar_snapshot_operativo(self, snapshot: dict[str, Any]) -> None:
        timestamp = str(snapshot["timestamp"])
        tick_actual = int(snapshot["tick_actual"])
        cursor = self.conexion.cursor()

        for interseccion in snapshot["intersecciones"]:
            cursor.execute(
                """
                INSERT OR REPLACE INTO estado_intersecciones (
                    interseccion_id, fase_activa, fase_alterna, duracion_fase_activa,
                    duracion_fase_alterna, ticks_restantes_fase, tick_actual, actualizado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interseccion["interseccion_id"],
                    interseccion["fase_activa"],
                    interseccion["fase_alterna"],
                    int(interseccion["duracion_fase_activa"]),
                    int(interseccion["duracion_fase_alterna"]),
                    int(interseccion["ticks_restantes_fase"]),
                    tick_actual,
                    timestamp,
                ),
            )

        for via in snapshot["vias"]:
            cursor.execute(
                """
                INSERT OR REPLACE INTO estado_vias (
                    via_id, origen, destino, direccion, eje, longitud,
                    vehiculos_en_circulacion, vehiculos_en_espera, velocidad_promedio,
                    flujo_vehicular, score, estado_congestion, tick_actual, actualizado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    via["via_id"],
                    via["origen"],
                    via["destino"],
                    via["direccion"],
                    via["eje"],
                    float(via["longitud"]),
                    int(via["vehiculos_en_circulacion"]),
                    int(via["vehiculos_en_espera"]),
                    float(via["velocidad_promedio"]),
                    int(via["flujo_vehicular"]),
                    float(via["score"]),
                    via["estado_congestion"],
                    tick_actual,
                    timestamp,
                ),
            )

        cursor.execute("DELETE FROM estado_vehiculos")
        for vehiculo in snapshot["vehiculos"]:
            cursor.execute(
                """
                INSERT INTO estado_vehiculos (
                    vehiculo_id, via_actual, posicion_en_via, velocidad,
                    direccion_actual, estado, tipo, tick_actual, actualizado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vehiculo["vehiculo_id"],
                    vehiculo["via_actual"],
                    float(vehiculo["posicion_en_via"]),
                    float(vehiculo["velocidad"]),
                    vehiculo["direccion_actual"],
                    vehiculo["estado"],
                    vehiculo["tipo"],
                    tick_actual,
                    timestamp,
                ),
            )

        self.conexion.commit()

    def guardar_evento_sensor(self, evento: dict[str, Any]) -> None:
        self.conexion.execute(
            """
            INSERT OR IGNORE INTO eventos_sensores (
                timestamp, sensor_id, tipo_sensor, interseccion, via_id, tick_origen, datos_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evento["timestamp"],
                evento["sensor_id"],
                evento["tipo_sensor"],
                evento["interseccion"],
                evento["via_id"],
                int(evento.get("tick_origen", 0)),
                json.dumps(evento["datos"], sort_keys=True),
            ),
        )
        self.conexion.commit()

    def guardar_comando_semaforo(self, comando: dict[str, Any]) -> None:
        self.conexion.execute(
            """
            INSERT OR IGNORE INTO comandos_semaforo (
                timestamp, interseccion, fase_ganadora, tiempo_verde, tiempo_opuesto, tick_origen, razon
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comando["timestamp"],
                comando["interseccion"],
                comando["fase_ganadora"],
                float(comando["tiempo_verde"]),
                float(comando["tiempo_opuesto"]),
                int(comando.get("tick_origen", 0)),
                comando["razon"],
            ),
        )
        self.conexion.commit()

    def guardar_snapshot_vehiculos_historico(self, snapshot: dict[str, Any]) -> None:
        timestamp = str(snapshot["timestamp"])
        tick_actual = int(snapshot["tick_actual"])
        registros = [
            (
                timestamp,
                tick_actual,
                vehiculo["vehiculo_id"],
                vehiculo["via_actual"],
                float(vehiculo["posicion_en_via"]),
                float(vehiculo["velocidad"]),
                vehiculo["direccion_actual"],
                vehiculo["estado"],
                vehiculo["tipo"],
            )
            for vehiculo in snapshot["vehiculos"]
        ]
        if not registros:
            return
        self.conexion.executemany(
            """
            INSERT INTO vehiculos_historico (
                snapshot_timestamp, tick_actual, vehiculo_id, via_actual,
                posicion_en_via, velocidad, direccion_actual, estado, tipo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            registros,
        )
        self.conexion.commit()

    def reconstruir_snapshot_operativo_actual(self) -> dict[str, Any] | None:
        intersecciones = [
            dict(fila)
            for fila in self.conexion.execute(
                """
                SELECT
                    interseccion_id, fase_activa, fase_alterna, duracion_fase_activa,
                    duracion_fase_alterna, ticks_restantes_fase
                FROM estado_intersecciones
                ORDER BY interseccion_id
                """
            ).fetchall()
        ]
        if not intersecciones:
            return None

        vias = [
            dict(fila)
            for fila in self.conexion.execute(
                """
                SELECT
                    via_id, origen, destino, direccion, eje, longitud,
                    vehiculos_en_circulacion, vehiculos_en_espera, velocidad_promedio,
                    flujo_vehicular, score, estado_congestion
                FROM estado_vias
                ORDER BY via_id
                """
            ).fetchall()
        ]
        vehiculos = [
            dict(fila)
            for fila in self.conexion.execute(
                """
                SELECT
                    vehiculo_id, via_actual, posicion_en_via, velocidad,
                    direccion_actual, estado, tipo
                FROM estado_vehiculos
                ORDER BY vehiculo_id
                """
            ).fetchall()
        ]
        tick_fila = self.conexion.execute(
            "SELECT MAX(tick_actual), MAX(actualizado_en) FROM estado_intersecciones"
        ).fetchone()
        tick_actual = int(tick_fila[0]) if tick_fila and tick_fila[0] is not None else 0
        timestamp = str(tick_fila[1]) if tick_fila and tick_fila[1] is not None else ""
        return {
            "timestamp": timestamp,
            "tick_actual": tick_actual,
            "fuente": "PC2",
            "version_contrato": 1,
            "intersecciones": intersecciones,
            "vias": vias,
            "vehiculos": vehiculos,
        }

    def obtener_resumen_estado(self) -> dict[str, Any]:
        tick_fila = self.conexion.execute(
            "SELECT MAX(tick_actual), MAX(actualizado_en) FROM estado_intersecciones"
        ).fetchone()
        tick_actual = int(tick_fila[0]) if tick_fila and tick_fila[0] is not None else 0
        actualizado_en = str(tick_fila[1]) if tick_fila and tick_fila[1] is not None else ""
        total_vehiculos = int(
            self.conexion.execute("SELECT COUNT(*) FROM estado_vehiculos").fetchone()[0]
        )
        total_ambulancias = int(
            self.conexion.execute(
                "SELECT COUNT(*) FROM estado_vehiculos WHERE tipo = 'AMBULANCIA'"
            ).fetchone()[0]
        )
        vias_congestion_alta = int(
            self.conexion.execute(
                "SELECT COUNT(*) FROM estado_vias WHERE estado_congestion = 'ALTA'"
            ).fetchone()[0]
        )
        return {
            "tick_actual": tick_actual,
            "actualizado_en": actualizado_en,
            "total_intersecciones": int(
                self.conexion.execute("SELECT COUNT(*) FROM estado_intersecciones").fetchone()[0]
            ),
            "total_vias": int(self.conexion.execute("SELECT COUNT(*) FROM estado_vias").fetchone()[0]),
            "total_vehiculos": total_vehiculos,
            "total_ambulancias": total_ambulancias,
            "vias_congestion_alta": vias_congestion_alta,
        }

    def listar_eventos_sensores(self) -> list[dict[str, Any]]:
        return [
            {
                **dict(fila),
                "datos": json.loads(str(fila["datos_json"])),
            }
            for fila in self.conexion.execute(
                """
                SELECT
                    timestamp, sensor_id, tipo_sensor, interseccion, via_id, tick_origen, datos_json
                FROM eventos_sensores
                ORDER BY id
                """
            ).fetchall()
        ]

    def listar_comandos_semaforo(self) -> list[dict[str, Any]]:
        return [
            dict(fila)
            for fila in self.conexion.execute(
                """
                SELECT
                    timestamp, interseccion, fase_ganadora,
                    tiempo_verde, tiempo_opuesto, tick_origen, razon
                FROM comandos_semaforo
                ORDER BY id
                """
            ).fetchall()
        ]

    def obtener_estado_interseccion(self, interseccion_id: str) -> dict[str, Any] | None:
        fila = self.conexion.execute(
            """
            SELECT
                interseccion_id, fase_activa, fase_alterna,
                duracion_fase_activa, duracion_fase_alterna,
                ticks_restantes_fase, tick_actual, actualizado_en
            FROM estado_intersecciones
            WHERE interseccion_id = ?
            """,
            (interseccion_id,),
        ).fetchone()
        if fila is None:
            return None
        vias = [
            dict(via)
            for via in self.conexion.execute(
                """
                SELECT
                    via_id, origen, destino, direccion, eje, longitud,
                    vehiculos_en_circulacion, vehiculos_en_espera,
                    velocidad_promedio, flujo_vehicular, score, estado_congestion,
                    tick_actual, actualizado_en
                FROM estado_vias
                WHERE destino = ?
                ORDER BY via_id
                """,
                (interseccion_id,),
            ).fetchall()
        ]
        return {"interseccion": dict(fila), "vias_entrada": vias}

    def obtener_estado_via(self, via_id: str) -> dict[str, Any] | None:
        fila = self.conexion.execute(
            """
            SELECT
                via_id, origen, destino, direccion, eje, longitud,
                vehiculos_en_circulacion, vehiculos_en_espera,
                velocidad_promedio, flujo_vehicular, score,
                estado_congestion, tick_actual, actualizado_en
            FROM estado_vias
            WHERE via_id = ?
            """,
            (via_id,),
        ).fetchone()
        return dict(fila) if fila is not None else None

    def listar_ambulancias_actuales(self) -> list[dict[str, Any]]:
        return [
            dict(fila)
            for fila in self.conexion.execute(
                """
                SELECT
                    vehiculo_id, via_actual, posicion_en_via, velocidad,
                    direccion_actual, estado, tipo, tick_actual, actualizado_en
                FROM estado_vehiculos
                WHERE tipo = 'AMBULANCIA'
                ORDER BY vehiculo_id
                """
            ).fetchall()
        ]

    def contar_eventos_intervalo(
        self,
        inicio: str,
        fin: str,
        tipo_sensor: str | None = None,
    ) -> int:
        if tipo_sensor is None:
            fila = self.conexion.execute(
                "SELECT COUNT(*) FROM eventos_sensores WHERE timestamp BETWEEN ? AND ?",
                (inicio, fin),
            ).fetchone()
        else:
            fila = self.conexion.execute(
                """
                SELECT COUNT(*) FROM eventos_sensores
                WHERE timestamp BETWEEN ? AND ? AND tipo_sensor = ?
                """,
                (inicio, fin, tipo_sensor),
            ).fetchone()
        return int(fila[0]) if fila is not None else 0

    def contar_comandos_intervalo(
        self,
        inicio: str,
        fin: str,
        interseccion: str | None = None,
    ) -> int:
        if interseccion is None:
            fila = self.conexion.execute(
                "SELECT COUNT(*) FROM comandos_semaforo WHERE timestamp BETWEEN ? AND ?",
                (inicio, fin),
            ).fetchone()
        else:
            fila = self.conexion.execute(
                """
                SELECT COUNT(*) FROM comandos_semaforo
                WHERE timestamp BETWEEN ? AND ? AND interseccion = ?
                """,
                (inicio, fin, interseccion),
            ).fetchone()
        return int(fila[0]) if fila is not None else 0
