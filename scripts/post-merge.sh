#!/bin/bash
# Post-merge setup script para BI Platform VLSur.
# Corre automaticamente tras el merge de cada tarea para mantener
# el entorno principal sincronizado.
#
# Garantias:
# - Idempotente (seguro correr varias veces).
# - No-interactivo (stdin cerrado en post-merge).
# - Falla rapido si algo va mal (set -e).

set -e

echo "[post-merge] Sincronizando dependencias Python con uv..."
uv sync --frozen 2>&1 || uv sync 2>&1

echo "[post-merge] Listo."
