"""Evaluación única en prueba (c05–c06) de lo elegido en validación."""
import json
import numpy as np, pandas as pd
from sklearn.base import clone
from modelos import *
from cargar import RESULTADOS

X, _ = conjunto()
tr, va, te = (X[X.corrida.isin(s)] for s in (ENTRENAMIENTO, VALIDACION, PRUEBA))
S = pd.read_csv(RESULTADOS / "seleccion_validacion.csv")
cand = {(f, h): m for f, h, m in modelos_candidatos()}
elegidos = (S[S.familia.isin(["Regresión lineal", "Árbol de decisión", "RNA (MLP)"])]
            .sort_values("F1", ascending=False).groupby("familia").head(1))

ev = (te.y > 0).values
ini, per = te.inicio.values, te.persistencia.values
tipo_ini = te.etiqueta_sig.values
filas, pred = [], {}

def registrar(nombre, alerta, yhat=None, tau=np.nan):
    m = metricas(ev, alerta, te.y.values if yhat is not None else None, yhat)
    m.update(modelo=nombre, tau=tau,
             inicios=int(ini.sum()), inicios_anticipados=int(alerta[ini].sum()),
             frac_inicios=float(alerta[ini].mean()),
             frac_rampa=float(alerta[ini & (tipo_ini == "rampa")].mean()),
             frac_salto=float(alerta[ini & (tipo_ini == "salto")].mean()),
             sens_persistencia=float(alerta[per].mean()))
    filas.append(m)

for _, e in elegidos.iterrows():
    m = clone(cand[(e.familia, e.hiper)]).fit(tr[ENTRADAS].values, tr.y.values)
    yh = m.predict(te[ENTRADAS].values)
    nombre = f"{e.familia} ({e.hiper})" if e.hiper != "—" else e.familia
    pred[nombre] = (yh, e.tau)
    registrar(nombre, yh >= e.tau, yh, e.tau)
    if e.familia == "Regresión lineal":
        coef = dict(zip(["β0"] + ENTRADAS, [m.intercept_] + list(m.coef_)))

R = S.set_index("familia")
tau_r = float(R.loc["Regla r_k ≥ τ_r", "tau"])
registrar("Regla r_k ≥ τ_r", te.r.values >= tau_r, tau=tau_r)
registrar("Persistencia d_k ≥ 1", te.d.values >= 1, te.d.values, 1.0)

T = pd.DataFrame(filas)[["modelo", "tau", "MAE", "VP", "FP", "FN", "VN", "precision", "sensibilidad", "F1",
                         "inicios", "inicios_anticipados", "frac_inicios", "frac_rampa", "frac_salto", "sens_persistencia"]]
pd.set_option("display.width", 250)
print(T.round(4).to_string(index=False))
print("\nInicios en prueba por tipo:", pd.Series(tipo_ini[ini]).value_counts().to_dict())
print("Coeficientes regresión lineal:", {k: round(v, 4) for k, v in coef.items()})
T.to_csv(RESULTADOS / "resultados_prueba.csv", index=False)
te = te.assign(**{f"yhat_{i}": pred[k][0] for i, k in enumerate(pred)})
te.to_csv(RESULTADOS / "prueba_predicciones.csv", index=False)
json.dump({k: v[1] for k, v in pred.items()} | {"regla": tau_r}, open(RESULTADOS / "umbrales.json", "w"), ensure_ascii=False, indent=1)
