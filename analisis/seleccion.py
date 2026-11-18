"""Selección en validación (c04): hiperparámetro de cada familia y umbral τ por F1."""
import json, time
import numpy as np, pandas as pd
from modelos import *
from cargar import RESULTADOS
RESULTADOS.mkdir(exist_ok=True)

X, todas = conjunto()
todas.to_csv(RESULTADOS / "ventanas.csv", index=False)     # CSV de ventanas (entregable)
tr, va = X[X.corrida.isin(ENTRENAMIENTO)], X[X.corrida.isin(VALIDACION)]
ev_va = (va.y > 0).values
res = []
for fam, hp, m in modelos_candidatos():
    t0 = time.time()
    m.fit(tr[ENTRADAS].values, tr.y.values)
    yh = m.predict(va[ENTRADAS].values)
    tau, f1 = mejor_umbral(yh, ev_va)
    mt = metricas(ev_va, yh >= tau, va.y.values, yh)
    ini = va.inicio.values
    res.append(dict(familia=fam, hiper=hp, tau=tau, F1=f1, MAE=mt["MAE"], precision=mt["precision"],
                    sensibilidad=mt["sensibilidad"], inicios_anticipados=float((yh[ini] >= tau).mean()),
                    segundos=round(time.time()-t0, 1)))
R = pd.DataFrame(res)
# referencias en validación
tau_r, f1_r = mejor_umbral(va.r.values, ev_va)
mt = metricas(ev_va, va.r.values >= tau_r)
ref = [dict(familia="Regla r_k ≥ τ_r", hiper="—", tau=tau_r, F1=f1_r, MAE=np.nan, precision=mt["precision"],
            sensibilidad=mt["sensibilidad"], inicios_anticipados=float((va.r.values[va.inicio.values] >= tau_r).mean()))]
mt = metricas(ev_va, va.d.values >= 1, va.y.values, va.d.values)
ref.append(dict(familia="Persistencia d_k ≥ 1", hiper="—", tau=1.0, F1=mt["F1"], MAE=mt["MAE"], precision=mt["precision"],
                sensibilidad=mt["sensibilidad"], inicios_anticipados=0.0))
R = pd.concat([R, pd.DataFrame(ref)], ignore_index=True)
pd.set_option("display.width", 200)
print(R.round(4).to_string(index=False))
R.to_csv(RESULTADOS / "seleccion_validacion.csv", index=False)
mejores = R[R.familia.isin(["Regresión lineal","Árbol de decisión","RNA (MLP)"])].sort_values("F1", ascending=False).groupby("familia").head(1)
print("\nMejor de cada familia:\n", mejores[["familia","hiper","tau","F1","MAE","inicios_anticipados"]].round(4).to_string(index=False))
