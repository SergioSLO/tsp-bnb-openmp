#!/bin/bash
# Compara el costo optimo de v1, v2 (static/dynamic) y v3 contra fuerza bruta, n = 5..11.
set -euo pipefail
cd "$(dirname "$0")/.."
fallos=0
cmp_cost() {  # $1 = esperado, $2 = obtenido, $3 = etiqueta
    if awk -v a="$1" -v b="$2" 'BEGIN { d = a - b; if (d < 0) d = -d; exit !(d < 1e-6) }'; then
        printf "  ok    %-28s %s\n" "$3" "$2"
    else
        printf "  FALLO %-28s %s (esperado %s)\n" "$3" "$2" "$1"; fallos=$((fallos + 1))
    fi
}
for n in 5 6 7 8 9 10 11; do
    ref=$(bin/tsp_brute --n "$n" | cut -d, -f9)
    echo "n=$n  fuerza bruta: $ref km"
    cmp_cost "$ref" "$(bin/tsp_seq --n "$n" | cut -d, -f9)" "v1_seq"
    for p in 1 2 4; do
        for d in 1 2 3; do
            cmp_cost "$ref" "$(bin/tsp_omp_for --n "$n" --p $p --depth $d --schedule static | cut -d, -f9)" "v2_static p=$p d=$d"
            cmp_cost "$ref" "$(bin/tsp_omp_for --n "$n" --p $p --depth $d --schedule dynamic | cut -d, -f9)" "v2_dynamic p=$p d=$d"
            cmp_cost "$ref" "$(bin/tsp_omp_task --n "$n" --p $p --depth $d | cut -d, -f9)" "v3_task p=$p d=$d"
        done
    done
done
if [ "$fallos" -eq 0 ]; then echo "VALIDACION OK"; else echo "VALIDACION CON $fallos FALLOS"; exit 1; fi
