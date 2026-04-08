#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

trap 'kill 0' EXIT

python3 -m PC2.replica_db.servicio_bd_replica &
python3 -m PC2.backend_respaldo.servicio_backend_respaldo &
python3 -m PC2.analytics.servicio_analitica
