"""Figuras del informe (PDF vectorial).

Colores por entidad (paleta de referencia, validada para daltonismo en pares adyacentes):
  azul    #2a78d6  lo medido (traza, descartes reales)
  naranja #eb6834  lo predicho (pronóstico y alerta del modelo elegido)
  gris    #8a8984  referencias (carga ofrecida del calendario, curva teórica)
Identidad nunca solo por color: leyendas, etiquetas directas y marcadores distintos.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from modelos import conjunto
from cargar import RESULTADOS, FIGURAS

AZUL, NARANJA, GRIS, TINTA, TINTA2 = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e"
OUT = FIGURAS; OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42,
})
MODELO = "Árbol de decisión (profundidad 6)"
LIMITE_CABLE, ESCALON_95 = 10.0, 9.5 * 1242 / 1200


def clase_inicio(df):
    return np.where(df.etiqueta_sig == "salto", "salto",
                    np.where(df.tasa_sig <= 10.5, "cruce", "reinicio"))


# ---------------------------------------------------------------- Figura 1
def fig_tasa_antes_de_inicio(X):
    cl = clase_inicio(X)
    grupos = [
        ("Ventanas sin descarte ahora ni en la siguiente", X[(X.d == 0) & (X.y == 0)].r),
        ("Ventana previa a un inicio en rampa (cruce del límite)", X[X.inicio & (cl == "cruce")].r),
        ("Ventana previa a un inicio en salto", X[X.inicio & (cl == "salto")].r),
    ]
    fig, ax = plt.subplots(3, 1, figsize=(6.3, 4.6), sharex=True)
    bins = np.arange(0, 11.6, 0.1)
    for a, (titulo, r) in zip(ax, grupos):
        a.hist(r.clip(upper=11.5), bins=bins, color=AZUL, edgecolor="white", linewidth=0.3,
               weights=np.full(len(r), 100 / len(r)))
        a.set_title(f"{titulo}  (n = {len(r)})", loc="left", color=TINTA)
        a.set_ylabel("% de ventanas")
        frac = (r > 9.9).mean() * 100
        a.text(0.01, 0.80, f"r$_k$ > 9,9 Mbit/s: {frac:.0f} %", transform=a.transAxes, color=TINTA2)
        for x, lab in [(ESCALON_95, "9,83 (escalón 9,5)"), (LIMITE_CABLE, "10 (límite TBF)")]:
            a.axvline(x, color=GRIS, lw=0.9, ls="--")
    ax[0].text(ESCALON_95 - 0.08, ax[0].get_ylim()[1] * 0.92, "9,83", ha="right", color=TINTA2, fontsize=8)
    ax[0].text(LIMITE_CABLE + 0.08, ax[0].get_ylim()[1] * 0.92, "10,0", ha="left", color=TINTA2, fontsize=8)
    ax[-1].set_xlabel("Tasa capturada en la ventana k, r$_k$ (Mbit/s)")
    fig.tight_layout()
    fig.savefig(OUT / "fig1_tasa_antes_de_inicio.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figura 2
def fig_serie_prueba(te, tau, corrida="c05", t0=25.0, t1=72.0):
    s = te[(te.corrida == corrida) & (te.t_rel >= t0) & (te.t_rel <= t1)].copy()
    dt = 0.1
    t_sig = s.t_rel.values + dt                  # cada pronóstico se ubica en la ventana a la que se refiere
    yhat = np.clip(s.yhat_0.values, 0, None)
    alerta = yhat >= tau
    fig, ax = plt.subplots(3, 1, figsize=(6.3, 5.8), sharex=True,
                           gridspec_kw={"height_ratios": [1.15, 1.15, 0.75]})
    # (a) tasa
    ax[0].step(s.t_rel, s.tasa, where="post", color=GRIS, lw=1.0, ls="--",
               label="carga ofrecida (calendario; solo para interpretar)")
    ax[0].step(s.t_rel, s.r, where="post", color=AZUL, lw=1.2, label="tasa capturada r$_k$")
    ax[0].axhline(10, color=GRIS, lw=0.6)
    ax[0].set_ylabel("Mbit/s"); ax[0].set_ylim(0, 15.5)
    ax[0].legend(loc="lower left", frameon=False, ncol=1)
    ax[0].set_title("a) Traza", loc="left", color=TINTA)
    # (b) descartes reales y pronosticados
    ax[1].step(s.t_rel + dt, s.y, where="post", color=AZUL, lw=1.2, label="descartes reales d$_{k+1}$")
    ax[1].step(t_sig, yhat, where="post", color=NARANJA, lw=1.2, label="pronóstico ŷ$_k$ (árbol, prof. 6)")
    ax[1].axhline(tau, color=NARANJA, lw=0.8, ls=":")
    ax[1].text(t1, tau, f"τ = {tau:.1f}".replace(".", ","), va="bottom", ha="right", color=TINTA2, fontsize=8)
    ax[1].set_ylabel("paquetes / 0,1 s")
    ax[1].legend(loc="center left", frameon=False, bbox_to_anchor=(0.0, 0.62))
    ax[1].set_title("b) Descartes en la ventana pronosticada", loc="left", color=TINTA)
    # (c) alertas e inicios
    for ti, a in zip(t_sig, alerta):
        if a:
            ax[2].axvspan(ti, ti + dt, ymin=0.15, ymax=0.85, color=NARANJA, lw=0)
    ini = s[s.inicio]
    clases = clase_inicio(ini)
    nombre = {"cruce": "rampa: cruce", "reinicio": "rampa: reinicio tras pausa", "salto": "salto"}
    for j, ((_, r), cl) in enumerate(zip(ini.iterrows(), clases)):
        ti = r.t_rel + dt
        anunciado = r.yhat_0 >= tau
        ax[2].axvline(ti, color=TINTA, lw=0.8)
        ax[1].axvline(ti, color=TINTA, lw=0.5, alpha=0.4)
        ax[2].plot(ti, 1.1, marker="v" if anunciado else "x", color=TINTA, ms=6, clip_on=False, mew=1.4)
        lado = -1 if j % 2 == 0 and j + 1 < len(ini) else 1
        ax[2].annotate(("anunciado" if anunciado else "omitido") + f"\n({nombre[cl]})",
                       (ti, 1.1), xytext=(lado * 6, 9), textcoords="offset points",
                       ha="right" if lado < 0 else "left", va="bottom", color=TINTA, fontsize=7.5,
                       annotation_clip=False)
    ax[2].set_ylim(0, 1); ax[2].set_yticks([])
    ax[2].set_ylabel("c) alertas", rotation=0, ha="right", va="center", color=TINTA)
    ax[2].set_xlabel(f"Tiempo desde el inicio de la corrida {corrida} (s)")
    ax[2].set_xlim(t0, t1)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_serie_prueba.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- Figura 3
def fig_magnitud(te):
    per = te[te.persistencia & te.tasa_sig.isin([10, 10.5, 12, 14, 20, 30])]
    g = per.groupby("tasa_sig").agg(real=("y", "mean"), pred=("yhat_0", lambda v: np.clip(v, 0, None).mean()))
    x = np.linspace(9.7, 31, 300)
    teo = np.clip(x * 1242 / 1200 - 10, 0, None) * 1e6 / 8 / 1242 * 0.1
    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    ax.plot(x, teo, color=GRIS, lw=1.0, ls="--", label="teórico: (1,035·tasa − 10)·10⁶/(8·1242)·0,1")
    ax.plot(g.index, g.real, "o", color=AZUL, ms=7, mec="white", mew=1.5, label="descartes reales (media)")
    ax.plot(g.index, g.pred, "s", color=NARANJA, ms=7, mec="white", mew=1.5, label="pronóstico del árbol (media)")
    desp = {10: (-4, 8, "right"), 10.5: (6, -12, "left")}
    for xi, yi in g.real.items():
        dx, dy, ha = desp.get(xi, (7, -11, "left"))
        ax.annotate(f"{yi:.1f}".replace(".", ","), (xi, yi), textcoords="offset points", xytext=(dx, dy),
                    ha=ha, color=TINTA2, fontsize=8)
    ax.set_xlabel("Carga ofrecida en la ventana pronosticada (Mbit/s; calendario)")
    ax.set_ylabel("descartes / 0,1 s")
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("Ventanas de persistencia en prueba: la traza indica cuándo, no cuánto", loc="left", color=TINTA)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_magnitud.pdf")
    plt.close(fig)


if __name__ == "__main__":
    X, _ = conjunto()
    te = pd.read_csv(RESULTADOS / "prueba_predicciones.csv")
    tau = json.load(open(RESULTADOS / "umbrales.json"))[MODELO]
    fig_tasa_antes_de_inicio(X)
    fig_serie_prueba(te, tau)
    fig_magnitud(te)
    print("figuras en", OUT)
