from __future__ import annotations

from datetime import datetime, timedelta


def calcular_hora_simulada(
    tick_actual: int,
    hora_inicio_simulada: str = "12:00",
    minutos_simulados_por_tick: int = 1,
    modo_bucle_infinito: bool = False,
) -> str:
    hora_base = datetime.strptime("00:00" if modo_bucle_infinito else hora_inicio_simulada, "%H:%M")
    desplazamiento = timedelta(minutes=int(tick_actual) * int(minutos_simulados_por_tick))
    hora_actual = hora_base + desplazamiento
    if modo_bucle_infinito:
        minutos = hora_actual.hour * 60 + hora_actual.minute
        return f"{(minutos // 60) % 24:02d}:{minutos % 60:02d}"
    return hora_actual.strftime("%H:%M")


def hora_simulada_desde_config(config: dict[str, object], tick_actual: int) -> str:
    config_simulacion = config["simulacion"]
    return calcular_hora_simulada(
        tick_actual=tick_actual,
        hora_inicio_simulada=str(config_simulacion.get("hora_inicio_simulada", "12:00")),
        minutos_simulados_por_tick=int(config_simulacion.get("minutos_simulados_por_tick", 1)),
        modo_bucle_infinito=bool(config_simulacion.get("modo_bucle_infinito", False)),
    )


def log(nombre_proceso: str, mensaje: str, hora_simulada: str | None = None) -> None:
    marca_real = datetime.now().strftime("%H:%M:%S")
    marca_simulada = hora_simulada if hora_simulada is not None else "--"
    print(f"[real={marca_real}] [sim={marca_simulada}] [{nombre_proceso}] {mensaje}", flush=True)
