#!/bin/bash
# Une los resultados de runs/ en $RESULTADOS/*.csv (por defecto resultados/).
# Para una corrida nueva que no pise los datos del informe:
#   RESULTADOS=resultados_nuevos scripts/juntar.sh
#   tiempos.csv, profundidad.csv : capitales (primera tanda, formato original)
#   tiempos_vlsi.csv             : VLSI recortado, cotas minout y mst (v4)
#   overhead.csv                 : microbenchmarks de todos los jobs
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${RESULTADOS:-resultados}
mkdir -p "$OUT"
merge() {  # $1 = salida, resto = archivos
    out=$1; shift
    [ $# -gt 0 ] && [ -f "$1" ] || { echo "sin archivos para $out"; return; }
    head -1 "$1" > "$out"
    for f in "$@"; do tail -n +2 "$f" >> "$out"; done
    echo "$out: $(($(wc -l < "$out") - 1)) filas"
}
shopt -s nullglob
merge "$OUT"/tiempos.csv runs/n_n*.csv
merge "$OUT"/profundidad.csv runs/depth_n*.csv
merge "$OUT"/tiempos_vlsi.csv runs/n_xqf*.csv
merge "$OUT"/overhead.csv runs/bench_*.csv
[ -f runs/nodos.csv ] && cp runs/nodos.csv "$OUT"/nodos.csv
pend=""; fail=""
for c in runs/*.claim; do
    [ -f "$c/done" ] || pend="$pend $c"
    [ -f "$c/failed" ] && fail="$fail $c"
done
[ -n "$fail" ] && echo "AVISO: experimentos que superaron 8 h dos veces: $fail"
[ -n "$pend" ] && echo "AVISO: experimentos sin terminar: $pend"
exit 0
