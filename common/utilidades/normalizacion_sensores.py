from __future__ import annotations


def normalizar_camara(vehiculos_en_espera: int) -> float:
    return min(max(float(vehiculos_en_espera), 0.0) / 10.0, 1.0)


def normalizar_espira(vehiculos_en_transito: int) -> float:
    return min(max(float(vehiculos_en_transito), 0.0) / 10.0, 1.0)


def normalizar_gps(velocidad_promedio: float) -> float:
    velocidad = max(float(velocidad_promedio), 0.0)
    if velocidad == 0:
        return 0.0
    if velocidad < 10:
        return 1.0
    if velocidad > 50:
        velocidad = 50.0
    return round(1 - 0.9 * ((velocidad - 10.0) / 40.0), 4)


def clasificar_nota_trafico(nota: float) -> str:
    valor = max(0.0, min(float(nota), 1.0))
    if valor < 0.4:
        return "BAJO"
    if valor <= 0.7:
        return "MODERADO"
    return "INTENSO"
