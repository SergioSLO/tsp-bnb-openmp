"""Analisis de resultados del TSP paralelo (CS4052).

Entrada (datos crudos, tal como salen de Khipu con scripts/juntar.sh):
  resultados/tiempos.csv        capitales, cota minout (v1, v2 static/dynamic, v3)
  resultados/tiempos_vlsi.csv   VLSI xqf131 recortado, cotas minout y mst (v4)
  resultados/profundidad.csv    efecto de la profundidad de corte d (capitales, n = 16)
  resultados/overhead.csv       microbenchmarks de OpenMP
Salida (todo se regenera; no editar a mano):
  figuras/f*.pdf|png            graficas del informe
  informe/generado/*.tex        tablas del informe
  resultados/derivados/*        medianas, speedup, eficiencia, ajustes y regresiones

Uso (desde la raiz del repositorio):  python3 analisis/analisis.py
        Otra corrida:  RESULTADOS=resultados_nuevos python3 analisis/analisis.py
Requiere: pandas, numpy, scipy, matplotlib (requirements.txt). Compatible con Python 3.11.
"""
import math
import os
import sys
from pathlib import Path

from scipy.optimize import least_squares

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
# Por defecto se analizan los datos del informe (resultados/) y se escriben figuras/ e
# informe/generado/. Con RESULTADOS=<carpeta> se analiza otra corrida y TODO lo generado
# queda dentro de esa carpeta, sin tocar el informe.
if os.environ.get("RESULTADOS"):
    RES = Path(os.environ["RESULTADOS"]).resolve()
    FIG, TAB = RES / "figuras", RES / "generado"
else:
    RES = ROOT / "resultados"
    FIG, TAB = ROOT / "figuras", ROOT / "informe" / "generado"
if len(sys.argv) > 1:
    FIG = Path(sys.argv[1])
DER = RES / "derivados"
for _d in (DER, FIG, TAB):
    _d.mkdir(parents=True, exist_ok=True)

# Paleta categorica validada (slots 1-3) + tinta neutra para v1 / ideal
COL = {"v2_for_static": "#2a78d6", "v2_for_dynamic": "#eb6834", "v3_task": "#1baf7a"}
MRK = {"v2_for_static": "o", "v2_for_dynamic": "s", "v3_task": "^"}
LBL = {"v1_seq": "v1 secuencial", "v2_for_static": "v2 for static",
       "v2_for_dynamic": "v2 for dynamic", "v3_task": "v3 tareas"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
PAR = ["v2_for_static", "v2_for_dynamic", "v3_task"]

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "lines.markersize": 5, "legend.frameon": False, "figure.dpi": 150,
    "savefig.bbox": "tight", "pdf.fonttype": 42,
})


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ datos
t = pd.read_csv(RES / "tiempos.csv")
d = pd.read_csv(RES / "profundidad.csv")
o = pd.read_csv(RES / "overhead.csv")
cities = pd.read_csv(ROOT / "data" / "ciudades.csv")

assert t.groupby("n").best_cost_km.nunique().max() == 1, "versiones con costos distintos"

m = (t.groupby(["version", "n", "p"])
       .agg(time=("time_s", "median"), time_min=("time_s", "min"), time_max=("time_s", "max"),
            nodes=("nodes", "median"), flops=("flops", "median"), tasks=("tasks", "median"),
            updates=("updates", "median"), reps=("rep", "count"), cost=("best_cost_km", "first"))
       .reset_index())
v1 = m[m.version == "v1_seq"].set_index("n")
m["T1_v1"] = m.n.map(v1.time)
m["S_abs"] = m.T1_v1 / m.time                       # speedup contra v1
t1_self = m[m.p == 1].set_index(["version", "n"]).time
m["S_rel"] = [t1_self[(v, n)] / tt for v, n, tt in zip(m.version, m.n, m.time)]
m["E_abs"] = m.S_abs / m.p
m["E_rel"] = m.S_rel / m.p
m["sigma"] = m.nodes / m.n.map(v1.nodes) - 1        # search overhead
m["gflops"] = m.flops / m.time / 1e9
m.to_csv(DER / "resumen.csv", index=False)

ns = sorted(v1.index)
P = sorted(m[m.version != "v1_seq"].p.unique())

# ------------------------------------------------------------------ ajustes de T1(n)
n_arr = np.array(ns, dtype=float)
T1 = v1.loc[ns, "time"].to_numpy()
N1 = v1.loc[ns, "nodes"].to_numpy()


def fit_line(x, y):
    k, b = np.polyfit(x, y, 1)
    pred = k * x + b
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    return k, b, r2


k_pol, b_pol, r2_pol = fit_line(np.log(n_arr), np.log(T1))      # T = a n^k
k_exp, b_exp, r2_exp = fit_line(n_arr, np.log(T1))               # T = a c^n
kN_pol, bN_pol, r2N_pol = fit_line(np.log(n_arr), np.log(N1))
c_exp = math.exp(k_exp)
t_node = T1 / N1                                                  # s por nodo
# costo por nodo ~ c n^2 (CalcularBound): ajuste de c con minimos cuadrados
c_node = np.sum(t_node * n_arr ** 2) / np.sum(n_arr ** 4)
worst = np.array([math.e * math.factorial(int(n) - 1) for n in n_arr])

with open(DER / "ajustes.txt", "w", encoding="utf-8") as f:
    f.write(f"Polinomial  T1 = {math.exp(b_pol):.3e} * n^{k_pol:.2f}   R2 = {r2_pol:.4f}\n")
    f.write(f"Exponencial T1 = {math.exp(b_exp):.3e} * {c_exp:.3f}^n   R2 = {r2_exp:.4f}\n")
    f.write(f"Nodos       N  = {math.exp(bN_pol):.3e} * n^{kN_pol:.2f}   R2 = {r2N_pol:.4f}\n")
    f.write(f"Costo por nodo ~ {c_node:.3e} * n^2 s\n")
    for n, a, b, w in zip(ns, T1, N1, worst):
        f.write(f"n={n:2d}  T1={a:10.4f} s  N={int(b):11d}  e(n-1)!={w:.3e}  N/peor={b / w:.2e}\n")

# ------------------------------------------------------------------ F1: T1(n) y ajustes
fig, ax = plt.subplots(figsize=(5.2, 3.2))
xs = np.linspace(10, 20, 100)
ax.plot(n_arr, T1, "o", color=INK, label="v1 medido (mediana)", zorder=3)
ax.plot(xs, math.exp(b_pol) * xs ** k_pol, color=COL["v2_for_static"],
        label=f"polinomio $a\\,n^{{{k_pol:.1f}}}$ ($R^2$={r2_pol:.3f})")
ax.plot(xs, math.exp(b_exp) * c_exp ** xs, "--", color=COL["v2_for_dynamic"],
        label=f"exponencial $b\\cdot{c_exp:.2f}^n$ ($R^2$={r2_exp:.3f})")
ax.set_yscale("log")
ax.set_xlabel("n (ciudades)")
ax.set_ylabel("tiempo secuencial $T_1$ (s)")
ax.set_xticks(ns)
ax.legend(loc="upper left")
save(fig, "f1_tiempo_vs_n")

# ------------------------------------------------------------------ F2: nodos explorados vs peor caso
fig, ax = plt.subplots(figsize=(5.2, 3.2))
ax.plot(n_arr, worst, "--", color=MUTED, label="peor caso $e\\,(n-1)!$")
ax.plot(n_arr, N1, "o-", color=COL["v2_for_static"], label="nodos explorados por v1")
ax.set_yscale("log")
ax.set_xlabel("n (ciudades)")
ax.set_ylabel("nodos del árbol")
ax.set_xticks(ns)
ax.legend(loc="upper left")
save(fig, "f2_nodos_vs_n")

# ------------------------------------------------------------------ F3/F4: speedup y eficiencia
def per_p(ax, n, col, ideal=None, ylabel=None, title=True):
    sub = m[(m.n == n) & (m.version != "v1_seq")]
    for v in PAR:
        s = sub[sub.version == v].sort_values("p")
        ax.plot(s.p, s[col], marker=MRK[v], color=COL[v], label=LBL[v])
    if ideal is not None:
        ax.plot(P, ideal(np.array(P)), ":", color=MUTED, linewidth=1.2, label="ideal")
    ax.set_xscale("log", base=2)
    ax.set_xticks(P)
    ax.set_xticklabels([str(p) for p in P])
    ax.set_xlabel("p (hilos)")
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(f"n = {n}")


for col, name, ylabel, ideal in [
    ("S_abs", "f3_speedup", "speedup $S_p = T_{v1}/T_p$", lambda p: p),
    ("E_abs", "f4_eficiencia", "eficiencia $E_p = S_p/p$", lambda p: np.ones_like(p, dtype=float)),
]:
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.8), sharey=True)
    for ax, n in zip(axs, [16, 18, 20]):
        per_p(ax, n, col, ideal, ylabel if n == 16 else None)
    if col == "S_abs":
        for ax in axs:
            ax.set_yscale("log", base=2)
            ax.set_yticks(P)
            ax.set_yticklabels([str(p) for p in P])
        axs[0].legend(loc="upper left")
    else:
        axs[0].set_ylim(0, 1.1)
        axs[0].legend(loc="lower left")
    fig.tight_layout()
    save(fig, name)

# ------------------------------------------------------------------ F5: speedup relativo (misma version, p=1)
fig, ax = plt.subplots(figsize=(5.2, 3.2))
per_p(ax, 20, "S_rel", lambda p: p, "speedup relativo $T_1^{(v)}/T_p^{(v)}$", title=False)
ax.set_yscale("log", base=2)
ax.set_yticks(P)
ax.set_yticklabels([str(p) for p in P])
ax.legend(loc="upper left")
save(fig, "f5_speedup_relativo")

# ------------------------------------------------------------------ F6: escalabilidad E vs n
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
for ax, p in zip(axs, [8, 16]):
    for v in PAR:
        s = m[(m.version == v) & (m.p == p)].sort_values("n")
        ax.plot(s.n, s.E_abs, marker=MRK[v], color=COL[v], label=LBL[v])
    ax.set_title(f"p = {p}")
    ax.set_xlabel("n (ciudades)")
    ax.set_xticks(ns)
axs[0].set_ylabel("eficiencia $E_p$")
axs[0].set_ylim(0, 1)
axs[0].legend(loc="upper left")
fig.tight_layout()
save(fig, "f6_escalabilidad")

# ------------------------------------------------------------------ F7: FLOP/s vs p
fig, ax = plt.subplots(figsize=(5.2, 3.2))
per_p(ax, 20, "gflops", None, "GFLOP/s", title=False)
ax.axhline(v1.loc[20, "flops"] / v1.loc[20, "time"] / 1e9, color=INK, linestyle="--",
           linewidth=1.2, label="v1 secuencial")
ax.legend(loc="upper left")
save(fig, "f7_flops")

# ------------------------------------------------------------------ F8: profundidad de corte
dm = (d.groupby(["version", "depth", "p"])
        .agg(time=("time_s", "median"), tasks=("tasks", "median"), nodes=("nodes", "median"))
        .reset_index())
dm.to_csv(DER / "resumen_profundidad.csv", index=False)
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8))
for v in ["v2_for_dynamic", "v3_task"]:
    s = dm[(dm.version == v) & (dm.p == 32)].sort_values("depth")
    axs[0].plot(s.depth, s.time, marker=MRK[v], color=COL[v], label=LBL[v])
    s = dm[(dm.version == v) & (dm.p == 16)].sort_values("depth")
    axs[1].plot(s.depth, s.time, marker=MRK[v], color=COL[v], label=LBL[v])
for ax, p in zip(axs, [32, 16]):
    ax.set_title(f"n = 16, p = {p}")
    ax.set_xlabel("profundidad de corte d")
    ax.set_xticks([1, 2, 3, 4])
axs[0].set_ylabel("tiempo (s)")
axs[0].legend(loc="upper right")
fig.tight_layout()
save(fig, "f8_profundidad")

# ------------------------------------------------------------------ F9: overhead OpenMP
om = o.groupby("p").median(numeric_only=True).reset_index()
om.to_csv(DER / "resumen_overhead.csv", index=False)
fig, ax = plt.subplots(figsize=(5.2, 3.2))
comp = [("t_fork_s", "$t_{fork}$", COL["v2_for_static"], "o"),
        ("t_task_s", "$t_{tarea}$", COL["v2_for_dynamic"], "s"),
        ("t_bar_s", "$t_{bar}$", COL["v3_task"], "^"),
        ("t_crit_s", "$t_{crit}$", INK, "D")]
for c, lab, colr, mk in comp:
    ax.plot(om.p, om[c] * 1e6, marker=mk, color=colr, label=lab)
ax.set_xscale("log", base=2)
ax.set_yscale("log")
ax.set_xticks(P)
ax.set_xticklabels([str(p) for p in P])
ax.set_xlabel("p (hilos)")
ax.set_ylabel("costo por operación (µs)")
ax.legend(loc="upper left")
save(fig, "f9_overhead")

# ------------------------------------------------------------------ F10: modelo vs medido (n=20)
ovh = om.set_index("p")
rows = []
for v in PAR:
    s = m[(m.version == v) & (m.n == 20)].set_index("p")
    T1v = s.loc[1, "time"]
    for p in P:
        d_cut = 2
        n_tar = s.loc[p, "tasks"]
        U = s.loc[p, "updates"]
        T_0 = (ovh.loc[p, "t_fork_s"] + n_tar * ovh.loc[p, "t_task_s"]
                 + U * ovh.loc[p, "t_crit_s"] + d_cut * ovh.loc[p, "t_bar_s"])
        pred = T1v * (1 + s.loc[p, "sigma"]) / (1 + s.loc[1, "sigma"]) / p + T_0
        rows.append({"version": v, "p": p, "medido": s.loc[p, "time"], "modelo": pred,
                     "T_0": T_0})
mod = pd.DataFrame(rows)
mod.to_csv(DER / "modelo_n20.csv", index=False)
fig, ax = plt.subplots(figsize=(5.2, 3.2))
for v in PAR:
    s = mod[mod.version == v]
    ax.plot(s.p, s.medido, marker=MRK[v], color=COL[v], label=f"{LBL[v]} medido")
    ax.plot(s.p, s.modelo, ":", color=COL[v], linewidth=1.4)
ax.plot([], [], ":", color=MUTED, label="modelo (punteado)")
ax.set_xscale("log", base=2)
ax.set_yscale("log")
ax.set_xticks(P)
ax.set_xticklabels([str(p) for p in P])
ax.set_xlabel("p (hilos)")
ax.set_ylabel("tiempo $T_p$ (s), n = 20")
ax.legend(loc="upper right")
save(fig, "f10_modelo_vs_medido")

# ------------------------------------------------------------------ F11: rutas optimas
def route_of(n):
    r = t[(t.n == n) & (t.version == "v1_seq")].route.iloc[0]
    return [int(x) for x in r.split("-")]


fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.6))
for ax, n in zip(axs, [10, 20]):
    c = cities.iloc[:n]
    r = route_of(n)
    ax.plot(c.lon.iloc[r], c.lat.iloc[r], "-", color=COL["v2_for_static"], linewidth=1.4, zorder=2)
    ax.scatter(c.lon, c.lat, s=18, color=INK, zorder=3)
    for i, row in c.iterrows():
        ax.annotate(row.nombre, (row.lon, row.lat), fontsize=5.5, color=MUTED,
                    xytext=(2, 2), textcoords="offset points")
    cost = m[(m.version == "v1_seq") & (m.n == n)].cost.iloc[0]
    ax.set_title(f"n = {n}: {cost:,.0f} km".replace(",", " "))
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 75)
    ax.set_xlabel("longitud (°)")
axs[0].set_ylabel("latitud (°)")
fig.tight_layout()
save(fig, "f11_rutas")

# ------------------------------------------------------------------ resumen en consola
print(open(DER / "ajustes.txt", encoding="utf-8").read())
cols = ["version", "p", "time", "S_abs", "E_abs", "S_rel", "sigma", "gflops"]
print(m[m.n == 20][cols].round(3).to_string(index=False))
print(mod.round(3).to_string(index=False))
print(f"figuras en {FIG}")


# ================================================================== VLSI y v4 (cota MST)
fv = RES / "tiempos_vlsi.csv"
if fv.exists():
    tv = pd.read_csv(fv)
    assert tv.groupby(["bound", "n"]).best_cost_km.nunique().max() == 1, "VLSI: costos distintos"
    mv = (tv.groupby(["bound", "version", "n", "p"])
            .agg(time=("time_s", "median"), nodes=("nodes", "median"), flops=("flops", "median"),
                 tasks=("tasks", "median"), cost=("best_cost_km", "first"),
                 depth=("depth", "first"), route=("route", "first"))
            .reset_index())
    base = mv[mv.version == "v1_seq"].set_index(["bound", "n"])
    mv["T1_v1"] = [base.loc[(b, n), "time"] for b, n in zip(mv.bound, mv.n)]
    mv["S_abs"] = mv.T1_v1 / mv.time
    mv["E_abs"] = mv.S_abs / mv.p
    mv["sigma"] = [nd / base.loc[(b, n), "nodes"] - 1 for b, n, nd in zip(mv.bound, mv.n, mv.nodes)]
    mv["gflops"] = mv.flops / mv.time / 1e9
    mv.drop(columns="route").to_csv(DER / "resumen_vlsi.csv", index=False)

    BND = {"minout": ("cota minout (v1–v3)", "o", "-"), "mst": ("cota MST (v4)", "s", "-")}

    # F12: T1(n) para ambas cotas (VLSI) y capitales
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.plot(n_arr, T1, "^--", color=MUTED, linewidth=1.2, label="capitales, minout")
    for b, colr in [("minout", COL["v2_for_static"]), ("mst", COL["v2_for_dynamic"])]:
        s = base.loc[b].sort_index()
        ax.plot(s.index, s.time, marker=BND[b][1], color=colr, label=f"VLSI, {BND[b][0]}")
    ax.set_yscale("log")
    ax.set_xlabel("n (puntos)")
    ax.set_ylabel("tiempo secuencial $T_1$ (s)")
    ax.legend(loc="upper left", bbox_to_anchor=(0.42, 1.0))
    save(fig, "f12_vlsi_tiempo")

    # F13: nodos explorados
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for b, colr in [("minout", COL["v2_for_static"]), ("mst", COL["v2_for_dynamic"])]:
        s = base.loc[b].sort_index()
        ax.plot(s.index, s.nodes, marker=BND[b][1], color=colr, label=f"VLSI, {BND[b][0]}")
    ax.set_yscale("log")
    ax.set_xlabel("n (puntos)")
    ax.set_ylabel("nodos explorados $N(n)$")
    ax.legend(loc="upper left")
    save(fig, "f13_vlsi_nodos")

    # F14: speedup VLSI minout n=20 y mst n=30, n=33
    cases = [("minout", 20), ("mst", 30), ("mst", 33)]
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.8), sharey=True)
    for ax, (b, n) in zip(axs, cases):
        sub = mv[(mv.bound == b) & (mv.n == n)]
        for v in PAR:
            s = sub[sub.version == v].sort_values("p")
            ax.plot(s.p, s.S_abs, marker=MRK[v], color=COL[v], label=LBL[v])
        ax.plot(P, P, ":", color=MUTED, linewidth=1.2, label="ideal")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log", base=2)
        ax.set_xticks(P)
        ax.set_xticklabels([str(p) for p in P])
        ax.set_yticks(P)
        ax.set_yticklabels([str(p) for p in P])
        ax.set_xlabel("p (hilos)")
        ax.set_title(f"{'v4 MST' if b == 'mst' else 'minout'}, n = {n}")
    axs[0].set_ylabel("speedup $S_p = T_{v1}/T_p$")
    axs[0].legend(loc="upper left")
    fig.tight_layout()
    save(fig, "f14_vlsi_speedup")

    # F15: eficiencia vs n con p = 16
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    for ax, b in zip(axs, ["minout", "mst"]):
        for v in PAR:
            s = mv[(mv.bound == b) & (mv.version == v) & (mv.p == 16)].sort_values("n")
            ax.plot(s.n, s.E_abs, marker=MRK[v], color=COL[v], label=LBL[v])
        ax.set_title(f"VLSI, {BND[b][0]}, p = 16")
        ax.set_xlabel("n (puntos)")
    axs[0].set_ylabel("eficiencia $E_{16}$")
    axs[0].set_ylim(0, 1.1)
    axs[0].legend(loc="upper left")
    fig.tight_layout()
    save(fig, "f15_vlsi_eficiencia")

    # F16: rutas VLSI
    pts = pd.read_csv(ROOT / "data" / "xqf131_sub.csv")
    full = pd.read_csv(ROOT / "data" / "xqf131_sub.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for ax, (b, n) in zip(axs, [("minout", 20), ("mst", 33)]):
        r = [int(x) for x in base.loc[(b, n), "route"].split("-")]
        c = pts.iloc[:n]
        ax.scatter(full.x, full.y, s=4, color=GRID, zorder=1)
        ax.plot(c.x.iloc[r], c.y.iloc[r], "-", color=COL["v2_for_static"], linewidth=1.4, zorder=2)
        ax.scatter(c.x, c.y, s=14, color=INK, zorder=3)
        ax.set_title(f"n = {n}: costo {base.loc[(b, n), 'cost']:.0f}")
        ax.set_xlabel("x")
        ax.set_aspect("equal")
    axs[0].set_ylabel("y")
    fig.tight_layout()
    save(fig, "f16_vlsi_rutas")

    cols = ["bound", "version", "n", "p", "time", "S_abs", "E_abs", "sigma", "gflops"]
    print(mv[mv.n.isin([20, 33]) & mv.p.isin([1, 16, 32])][cols].round(3).to_string(index=False))


# ================================================================== tablas para el informe
def fmt_t(x):
    return f"{x * 1e3:.2f}~ms" if x < 1 else f"{x:.2f}~s"


def thin(x):
    return f"{int(x):,}".replace(",", "\\,")


def sci(x):
    e = int(math.floor(math.log10(x)))
    return f"${x / 10 ** e:.1f}\\times10^{{{e}}}$"


def write(name, text):
    (TAB / name).write_text(text, encoding="utf-8")


rows = []
for n_, r in v1.sort_index().iterrows():
    w = math.e * math.factorial(int(n_) - 1)
    rows.append(f"{int(n_)} & {fmt_t(r.time)} & {thin(r.nodes)} & {sci(r.nodes / w)} & "
                f"{thin(round(r.cost))} & {r.flops / r.time / 1e9:.2f} \\\\")
write("tab_v1.tex", "\n".join([
    r"\begin{table}[H]", r"\centering",
    r"\caption{Versión secuencial v1 (mediana de 5 ejecuciones; 3 para $n \ge 19$) en Khipu (nodo n003).}",
    r"\label{tab:v1}", r"\small", r"\begin{tabular}{rrrrrr}", r"\toprule",
    r"$n$ & $T_1$ & Nodos $N(n)$ & $N(n)/e(n-1)!$ & Costo óptimo (km) & GFLOP/s \\", r"\midrule",
    *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]))

LAB = {"v2_for_static": "v2 static", "v2_for_dynamic": "v2 dynamic", "v3_task": "v3 tareas"}
rows = []
for v in PAR:
    s = m[(m.n == 20) & (m.version == v)].sort_values("p")
    for i, (_, r) in enumerate(s.iterrows()):
        sg = f"{r.sigma:+.3f}".replace("+0.000", "0.000").replace("-0.000", "0.000")
        rows.append(f"{LAB[v] if i == 0 else ''} & {int(r.p)} & {r.time:.1f} & {r.S_abs:.2f} & "
                    f"{r.E_abs:.2f} & {r.S_rel:.2f} & {sg} \\\\")
    if v != PAR[-1]:
        rows.append(r"\midrule")
write("tab_n20.tex", "\n".join([
    r"\begin{table}[H]", r"\centering",
    rf"\caption{{Resultados para $n=20$ ($T_{{v1}} = {v1.loc[20, 'time']:.1f}$~s). $S_p = T_{{v1}}/T_p$, "
    r"$E_p = S_p/p$, $S^{rel}_p = T^{(v)}_1/T^{(v)}_p$ y $\sigma_p$ = nodos adicionales respecto de v1.}",
    r"\label{tab:n20}", r"\small", r"\begin{tabular}{llrrrrr}", r"\toprule",
    r"Versión & $p$ & $T_p$ (s) & $S_p$ & $E_p$ & $S^{rel}_p$ & $\sigma_p$ \\", r"\midrule",
    *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]))

if fv.exists():
    LABV = {"v2_for_static": "v2 static", "v2_for_dynamic": "v2 dyn.", "v3_task": "v3"}
    rows = []
    for b in ["minout", "mst"]:
        s = base.loc[b].sort_index()
        for i, (n_, r) in enumerate(s.iterrows()):
            x = mv[(mv.bound == b) & (mv.n == n_) & (mv.version != "v1_seq")]
            best = x.loc[x.S_abs.idxmax()]
            name = ("minout" if b == "minout" else "MST (v4)") if i == 0 else ""
            rows.append(f"{name} & {int(n_)} & {fmt_t(r.time).replace('.00~', '.0~')} & {thin(r.nodes)} & "
                        f"{r.cost:.0f} & {best.S_abs:.1f} ({LABV[best.version]}, {int(best.p)}) \\\\")
        if b == "minout":
            rows.append(r"\midrule")
    write("tab_vlsi.tex", "\n".join([
        r"\begin{table}[H]", r"\centering",
        r"\caption{Instancias VLSI recortadas (\texttt{xqf131}, primeras $n$ filas del orden aleatorio). "
        r"$T_1$ y $N$ de v1 con la cota indicada; mejor speedup $S_p = T_{v1}/T_p$ entre las versiones paralelas.}",
        r"\label{tab:vlsi}", r"\small", r"\begin{tabular}{llrrrl}", r"\toprule",
        r"Cota & $n$ & $T_1$ & Nodos $N(n)$ & Costo óptimo & Mejor $S_p$ (versión, $p$) \\", r"\midrule",
        *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]))

# ================================================================== escalabilidad: Ts/Tp vs n y regresion
# Conjunto de datos de cada caso: T_s = v1 (p = 1) y T_p = v2 dynamic (p = 2..16, nucleos fisicos).
# p = 32 se excluye del ajuste: son 16 nucleos con hyperthreading (ver diagnostico).
# En v4 las instancias con n <= 24 tardan < 0.3 s y no crecen de forma monotona (la de n = 20
# es mas dificil que la de 22): esa variacion no es escalabilidad, asi que se ajusta desde n = 26.
CASES = [("capitales", "Capitales, minout", m)]
NMIN = {"capitales": 10, "vlsi_minout": 10, "vlsi_mst": 26}
if fv.exists():
    CASES += [("vlsi_minout", "VLSI, minout", mv[mv.bound == "minout"]),
              ("vlsi_mst", "VLSI, MST (v4)", mv[mv.bound == "mst"])]
PFIT = [2, 4, 8, 16]
RAMP = {1: INK, 2: "#86b6ef", 4: "#5598e7", 8: "#2a78d6", 16: "#1c5cab", 32: "#104281"}
PMRK = {1: "D", 2: "o", 4: "s", 8: "^", 16: "v", 32: "x"}


def dataset(sub):
    ts = sub[sub.version == "v1_seq"][["n", "time"]].assign(p=1)
    tp = sub[(sub.version == "v2_for_dynamic") & (sub.p.isin(PFIT))][["n", "p", "time"]]
    return pd.concat([ts, tp], ignore_index=True)


def model(x, n, p):
    """log T(n, p) con T = a c^n / p^beta + T_0."""
    la, lc, beta, lt0 = x
    return np.log(np.exp(la + lc * n) / p ** beta + np.exp(lt0))


reg_rows, grow_rows, fits = [], [], {}
for key, title, sub in CASES:
    dd = dataset(sub)
    dd = dd[dd.n >= NMIN[key]]
    nn, pp, yy = dd.n.to_numpy(float), dd.p.to_numpy(float), np.log(dd.time.to_numpy())
    k0, b0 = np.polyfit(nn[pp == 1], yy[pp == 1], 1)
    fit = least_squares(lambda x: model(x, nn, pp) - yy, x0=[b0, k0, 0.8, np.log(1e-3)])
    res = model(fit.x, nn, pp) - yy
    r2 = 1 - np.sum(res ** 2) / np.sum((yy - yy.mean()) ** 2)
    la, lc, beta, lt0 = fit.x
    fits[key] = fit.x
    reg_rows.append({"caso": key, "a": math.exp(la), "c": math.exp(lc), "beta": beta,
                     "T_0_s": math.exp(lt0), "R2_log": r2, "factor_error": math.exp(np.sqrt(np.mean(res ** 2))),
                     "E16_asintotica": 16 ** (beta - 1), "n_min": int(dd.n.min()), "n_max": int(dd.n.max())})
    for p_ in [1] + PFIT:
        s_ = dd[dd.p == p_]
        k, _ = np.polyfit(s_.n, np.log(s_.time), 1)
        grow_rows.append({"caso": key, "p": p_, "c_p": math.exp(k)})
reg = pd.DataFrame(reg_rows)
grow = pd.DataFrame(grow_rows)
reg.to_csv(DER / "regresion_escalabilidad.csv", index=False)
grow.to_csv(DER / "crecimiento_por_p.csv", index=False)

TIT = {k: t_ for k, t_, _ in CASES}
rows = []
for _, r in reg.iterrows():
    cps = grow[grow.caso == r.caso].set_index("p").c_p
    t0 = f"{r.T_0_s * 1e3:.2f}~ms" if r.T_0_s < 0.1 else f"{r.T_0_s:.2f}~s"
    rows.append(f"{TIT[r.caso]} & {r.n_min}--{r.n_max} & {r.c:.2f} & {r.beta:.2f} & {t0} & "
                f"{r.R2_log:.3f} & {r.E16_asintotica:.2f} & "
                + " & ".join(f"{cps[p_]:.2f}" for p_ in [1] + PFIT) + r" \\")
write("tab_regresion.tex", "\n".join([
    r"\begin{table}[H]", r"\centering",
    r"\caption{Regresión de escalabilidad. Modelo conjunto $T_p(n) = a\,c^{\,n}/p^{\beta} + T_0$ "
    r"ajustado por mínimos cuadrados sobre $\log T$ (v1 para $p=1$ y v2 dinámico para $p = 2, \dots, 16$). "
    r"$E_{16}^{\infty} = 16^{\beta-1}$ es la eficiencia con 16 núcleos cuando $T_0$ es despreciable. "
    r"A la derecha, la base de crecimiento $c_p$ de un ajuste exponencial $T_p(n) = a_p\,c_p^{\,n}$ separado para cada $p$.}",
    r"\label{tab:regresion}", r"\small", r"\setlength{\tabcolsep}{4pt}",
    r"\begin{tabular}{lcrrrrr|rrrrr}", r"\toprule",
    r" & & \multicolumn{5}{c|}{Modelo conjunto} & \multicolumn{5}{c}{$c_p$ por separado} \\",
    r"Caso & $n$ & $c$ & $\beta$ & $T_0$ & $R^2$ & $E_{16}^{\infty}$ & $p{=}1$ & 2 & 4 & 8 & 16 \\", r"\midrule",
    *rows, r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]))

# F17: resumen Ts/Tp vs n
fig, axs = plt.subplots(1, len(CASES), figsize=(7.2, 2.8), sharey=True)
axs = np.atleast_1d(axs)
for ax, (key, title, sub) in zip(axs, CASES):
    ts = sub[sub.version == "v1_seq"].set_index("n").time
    for p_ in [2, 4, 8, 16, 32]:
        s_ = sub[(sub.version == "v2_for_dynamic") & (sub.p == p_)].sort_values("n")
        ax.plot(s_.n, ts.loc[s_.n].to_numpy() / s_.time.to_numpy(), marker=PMRK[p_], color=RAMP[p_],
                linestyle="--" if p_ == 32 else "-", linewidth=1.6, markersize=4,
                label=f"p = {p_}" + (" (HT)" if p_ == 32 else ""))
    ax.set_title(title)
    ax.set_xlabel("n")
axs[0].set_ylabel("$T_s / T_p$ (v2 dynamic)")
axs[0].legend(loc="upper left")
fig.tight_layout()
save(fig, "f17_speedup_vs_n")

# F18: regresion, medido (puntos) vs modelo conjunto (lineas)
fig, axs = plt.subplots(1, len(CASES), figsize=(7.2, 2.9))
axs = np.atleast_1d(axs)
for ax, (key, title, sub) in zip(axs, CASES):
    dd = dataset(sub)
    dd = dd[dd.n >= NMIN[key]]
    xs = np.linspace(dd.n.min(), dd.n.max(), 100)
    for p_ in [1, 4, 16]:
        s_ = dd[dd.p == p_].sort_values("n")
        ax.plot(s_.n, s_.time, PMRK[p_], color=RAMP[p_], markersize=4,
                label=("$T_s$ (v1)" if p_ == 1 else f"$T_{{{p_}}}$"))
        ax.plot(xs, np.exp(model(fits[key], xs, p_)), "-", color=RAMP[p_], linewidth=1.3)
    ax.set_yscale("log")
    ax.set_title(title)
    ax.set_xlabel("n")
axs[0].set_ylabel("tiempo (s)")
axs[0].legend(loc="upper left")
fig.tight_layout()
save(fig, "f18_regresion")

print(reg.round(4).to_string(index=False))
print(grow.pivot(index="caso", columns="p", values="c_p").round(3))
print(f"tablas en {TAB}")
