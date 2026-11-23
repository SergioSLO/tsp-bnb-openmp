"""Convierte una instancia VLSI (TSPLIB, EUC_2D) en un CSV id,x,y con los puntos en un
orden aleatorio fijo (semilla 2026). Las primeras n filas forman la instancia recortada
de tamano n, asi cada instancia contiene a la anterior (como con las capitales).

Uso (desde codigo/):  python3 scripts/preparar_vlsi.py data/xqf131.tsp data/xqf131_sub.csv
"""
import random
import sys

src, dst = sys.argv[1], sys.argv[2]
pts = []
with open(src, encoding="utf-8") as f:
    inside = False
    for line in f:
        line = line.strip()
        if line.startswith("NODE_COORD_SECTION"):
            inside = True
            continue
        if line.startswith("EOF") or not line:
            inside = False
            continue
        if inside:
            i, x, y = line.split()[:3]
            pts.append((int(i), float(x), float(y)))

random.Random(2026).shuffle(pts)
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    f.write("id,x,y\n")
    for i, x, y in pts:
        f.write(f"{i},{x:g},{y:g}\n")
print(f"{len(pts)} puntos -> {dst}")
