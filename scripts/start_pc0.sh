#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

trap 'kill 0' EXIT

python3 -m PC0.historic_db.servicio_bd_historica &
python3 -m PC0.simulation.servicio_simulacion
