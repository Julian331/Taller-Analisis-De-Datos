"""Lectura de los archivos que deja corrida.sh para cada corrida.

cXX_cola.log     pares de líneas: tiempo Unix (punto medio de la lectura) y JSON de
                 `tc -j -s qdisc show`; se toma el objeto kind=tbf, handle=10:.
cXX_paquetes.csv tiempo de cada trama capturada y su longitud (frame.len).
cXX_fases.csv    etiqueta, tasa ofrecida, hora de inicio/fin y descartes de cada fase.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(os.environ.get("DATOS_LAB", RAIZ / "datos"))   # carpeta con c01 ... c06
RESULTADOS = RAIZ / "resultados"
FIGURAS = RAIZ / "informe" / "figuras"
CORRIDAS = ["c01", "c02", "c03", "c04", "c05", "c06"]


def leer_cola(corrida: str) -> pd.DataFrame:
    """Muestras de los contadores de la TBF (acumulados) con su tiempo."""
    filas = []
    lineas = (DATOS / corrida / f"{corrida}_cola.log").read_text().splitlines()
    for a, b in zip(lineas[0::2], lineas[1::2]):
        if not b.startswith("["):
            continue
        q = next(x for x in json.loads(b) if x.get("kind") == "tbf" and x.get("handle") == "10:")
        filas.append((float(a), q["drops"], q["overlimits"], q["backlog"], q["qlen"],
                      q["bytes"], q["packets"]))
    return pd.DataFrame(filas, columns=["t", "drops", "overlimits", "backlog", "qlen",
                                        "bytes_tbf", "pkts_tbf"])


def leer_paquetes(corrida: str) -> pd.DataFrame:
    return pd.read_csv(DATOS / corrida / f"{corrida}_paquetes.csv",
                       names=["t", "len"], header=0, dtype={"t": float, "len": int})


def leer_fases(corrida: str) -> pd.DataFrame:
    return pd.read_csv(DATOS / corrida / f"{corrida}_fases.csv")
