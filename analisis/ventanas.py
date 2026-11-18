"""Construcción de la serie temporal por ventanas (sección 2 del enunciado).

Ventana base: entre dos muestras consecutivas de la cola, [t_{i-1}, t_i), de ≈ 0,05 s.
Ventana de análisis: W ventanas base consecutivas (W = 2 → ≈ 0,1 s).

Para cada ventana k:
    B_k  bytes de las tramas capturadas en la ventana      n_k  número de tramas
    Δ_k  duración real                                     r_k = 8 B_k / (10^6 Δ_k)  [Mbit/s]
    d_k  = D(t_k) − D(t_{k−1})      descartes de la TBF en la ventana
    o_k  = O(t_k) − O(t_{k−1})      overlimits de la TBF en la ventana
Una ventana es válida si ninguna de sus ventanas base dura más de 1,5 periodos de
muestreo (pausa anormal); el enunciado pide no construir filas que crucen esas pausas.
"""
import numpy as np
import pandas as pd

from cargar import leer_cola, leer_paquetes, leer_fases

P = 0.05          # periodo de muestreo de la cola (s)
TOL = 1.5         # una ventana base con Δ > TOL·P es una pausa anormal


def ventanas(corrida: str, W: int = 2) -> pd.DataFrame:
    q = leer_cola(corrida)
    p = leer_paquetes(corrida)
    f = leer_fases(corrida)

    # Bordes cada W muestras: ventana j = [t[W·j], t[W·(j+1)])
    idx = np.arange(0, len(q), W)
    t = q.t.values[idx]
    tb = q.t.values
    base_ok = np.r_[True, np.diff(tb) <= TOL * P]          # base_ok[i]: ventana base que termina en i
    ok = np.array([base_ok[a + 1:b + 1].all() for a, b in zip(idx[:-1], idx[1:])])

    # Bytes y tramas por ventana: búsqueda binaria de los tiempos de paquete en los bordes
    pos = np.searchsorted(p.t.values, t, side="left")
    cum_b = np.r_[0, np.cumsum(p.len.values)]
    B = cum_b[pos[1:]] - cum_b[pos[:-1]]
    n = pos[1:] - pos[:-1]
    dt = np.diff(t)

    df = pd.DataFrame({
        "corrida": corrida,
        "t_ini": t[:-1], "t_fin": t[1:], "dt": dt,
        "B": B, "n": n, "r": 8 * B / (1e6 * dt),
        "d": np.diff(q.drops.values[idx]),
        "o": np.diff(q.overlimits.values[idx]),
        "backlog_fin": q.backlog.values[idx][1:],
        "valida": ok,
    })

    # Fase activa al final de la ventana (solo para interpretar; nunca es predictor)
    fi = np.searchsorted(f.t_ini.values, df.t_fin.values, side="right") - 1
    activa = (fi >= 0) & (df.t_fin.values <= f.t_fin.values[np.clip(fi, 0, None)] + 1e-9)
    df["fase"] = np.where(activa, f.fase.values[np.clip(fi, 0, None)], "pausa")
    df["etiqueta"] = np.where(activa, f.etiqueta.values[np.clip(fi, 0, None)], "pausa")
    df["tasa_ofrecida"] = np.where(activa, f.tasa_mbps.values[np.clip(fi, 0, None)], 0.0)
    df["t_rel"] = df.t_fin - q.t.values[0]
    return df
