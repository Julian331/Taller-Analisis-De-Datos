"""Conjunto de datos, modelos, selección en validación y evaluación en prueba.

Decisiones (registro D10–D13):
  - Congestión en la ventana k  ⇔  d_k ≥ 1 (al menos un descarte de la TBF en 0,1 s).
  - Objetivo: y_k = d_{k+1}; alerta al cierre de k si ŷ_k ≥ τ.
  - Entradas (las del enunciado): r_k, r_{k−1}, r_{k−2}, n_k.
  - Entrenamiento c01–c03; validación c04 (hiperparámetros y τ, criterio F1);
    prueba c05–c06, una sola vez.
"""
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import f1_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

from cargar import CORRIDAS
from ventanas import ventanas

ENTRADAS = ["r", "r1", "r2", "n"]
ENTRENAMIENTO, VALIDACION, PRUEBA = ["c01", "c02", "c03"], ["c04"], ["c05", "c06"]
SEMILLA = 2026


def desplazar(x, k):
    """x desplazado k posiciones (k > 0: valor anterior; k < 0: valor siguiente)."""
    out = np.full(len(x), np.nan, dtype=float)
    if k > 0:
        out[k:] = x[:-k]
    else:
        out[:k] = x[-k:]
    return out


def conjunto(W: int = 2):
    """Filas utilizables por corrida: k, k−1, k−2 y k+1 válidas (sin cruzar pausas)."""
    filas, todas = [], []
    for c in CORRIDAS:
        w = ventanas(c, W)
        todas.append(w)
        ok = w.valida.values.astype(float)
        util = (ok * desplazar(ok, 1) * desplazar(ok, 2) * desplazar(ok, -1)) == 1
        d = w.d.values.astype(float)
        df = pd.DataFrame({
            "corrida": c, "t_rel": w.t_rel.values,
            "r": w.r.values, "r1": desplazar(w.r.values, 1), "r2": desplazar(w.r.values, 2),
            "n": w.n.values.astype(float),
            "d": d, "y": desplazar(d, -1),
            "etiqueta": w.etiqueta.values,
            "etiqueta_sig": np.append(w.etiqueta.values[1:], "fin"),
            "tasa": w.tasa_ofrecida.values.astype(float),
            "tasa_sig": np.append(w.tasa_ofrecida.values[1:], 0.0).astype(float),
        })
        filas.append(df[util].reset_index(drop=True))
    X = pd.concat(filas, ignore_index=True)
    X["inicio"] = (X.d == 0) & (X.y > 0)
    X["persistencia"] = (X.d > 0) & (X.y > 0)
    return X, pd.concat(todas, ignore_index=True)


def mejor_umbral(puntaje, evento):
    """τ que maximiza F1 de la alerta (puntaje ≥ τ) sobre los datos dados."""
    cand = np.unique(np.quantile(puntaje, np.linspace(0, 1, 401)))
    cand = np.union1d(cand, [1.0])           # incluye el umbral del enunciado
    f1 = [f1_score(evento, puntaje >= u, zero_division=0) for u in cand]
    i = int(np.argmax(f1))
    return float(cand[i]), float(f1[i])


def modelos_candidatos():
    """Familias y la rejilla del hiperparámetro que controla la capacidad de cada una."""
    yield "Regresión lineal", "—", LinearRegression()
    for p in range(1, 13):
        yield "Árbol de decisión", f"profundidad {p}", DecisionTreeRegressor(max_depth=p, random_state=SEMILLA)
    for capas in [(4,), (8,), (16,), (16, 8)]:
        red = make_pipeline(StandardScaler(), MLPRegressor(
            hidden_layer_sizes=capas, activation="relu", solver="adam", max_iter=1000,
            early_stopping=True, n_iter_no_change=20, random_state=SEMILLA))
        yield "RNA (MLP)", f"capas {capas}", TransformedTargetRegressor(red, transformer=StandardScaler())


def metricas(evento, alerta, y=None, yhat=None):
    tp = int((alerta & evento).sum()); fp = int((alerta & ~evento).sum())
    fn = int((~alerta & evento).sum()); tn = int((~alerta & ~evento).sum())
    m = {"VP": tp, "FP": fp, "FN": fn, "VN": tn,
         "precision": tp / (tp + fp) if tp + fp else np.nan,
         "sensibilidad": tp / (tp + fn) if tp + fn else np.nan}
    m["F1"] = 2 * m["precision"] * m["sensibilidad"] / (m["precision"] + m["sensibilidad"]) \
        if tp else 0.0
    if y is not None:
        m["MAE"] = float(np.mean(np.abs(np.clip(yhat, 0, None) - y)))
    return m
