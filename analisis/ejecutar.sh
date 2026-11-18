#!/usr/bin/env bash
# Reproduce todo el análisis desde los datos crudos de datos/c01 ... c06.
# Orden: ventanas + selección en validación (c04) → prueba única (c05–c06) → figuras.
set -e
cd "$(dirname "$0")"
python3 seleccion.py
python3 prueba.py
python3 figuras.py
