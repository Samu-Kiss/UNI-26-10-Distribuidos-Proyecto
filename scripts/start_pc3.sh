#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

trap 'kill 0' EXIT

python3 -m PC3.main_db.servicio_bd_principal &
python3 -m PC3.backend.servicio_backend_principal
