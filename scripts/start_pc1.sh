#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR"

trap 'kill 0' EXIT

python3 -m PC1.broker.broker_mq &
python3 -m PC1.sensors.simulador_sensores
