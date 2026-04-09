#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rm -f "$ROOT_DIR"/PC0/historic_db/bd_historica.sqlite3*
rm -f "$ROOT_DIR"/PC2/replica_db/bd_replicada.sqlite3*
rm -f "$ROOT_DIR"/PC3/main_db/bd_principal.sqlite3*

echo "Bases de datos eliminadas."
