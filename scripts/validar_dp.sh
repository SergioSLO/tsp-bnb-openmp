#!/bin/bash
# Valida contra Held-Karp (programacion dinamica, exacta e independiente de B&B):
#   capitales n = 12..20 y VLSI recortado n = 12..22, con ambas cotas y las 3 versiones.
# La cota minout solo se prueba donde tarda poco (capitales n <= 16, VLSI n <= 15).
set -euo pipefail
cd "$(dirname "$0")/.."
P=${P:-4}
fallos=0
cmp_cost() {
    if awk -v a="$1" -v b="$2" 'BEGIN { d = a - b; if (d < 0) d = -d; exit !(d < 1e-6) }'; then
        printf "  ok    %-34s %s\n" "$3" "$2"
    else
        printf "  FALLO %-34s %s (esperado %s)\n" "$3" "$2" "$1"; fallos=$((fallos + 1))
    fi
}
check() {  # $1 = datos, $2 = n, $3 = n maximo para minout
    local D=$1 n=$2 lim=$3
    ref=$(bin/tsp_dp --data "$D" --n "$n" | cut -d, -f9)
    echo "$(basename "$D") n=$n  Held-Karp: $ref"
    for b in minout mst; do
        [ "$b" = minout ] && [ "$n" -gt "$lim" ] && continue
        cmp_cost "$ref" "$(bin/tsp_seq --data "$D" --n "$n" --bound $b | cut -d, -f9)" "v1 $b"
        cmp_cost "$ref" "$(bin/tsp_omp_for --data "$D" --n "$n" --bound $b --p $P --schedule dynamic | cut -d, -f9)" "v2 dynamic $b p=$P"
        cmp_cost "$ref" "$(bin/tsp_omp_task --data "$D" --n "$n" --bound $b --p $P | cut -d, -f9)" "v3 $b p=$P"
    done
    cmp_cost "$ref" "$(bin/tsp_omp_task --data "$D" --n "$n" --bound mst --init nn --p $P | cut -d, -f9)" "v3 mst+nn p=$P"
}
for n in 12 14 16 18 20; do check data/ciudades.csv $n 16; done
for n in 12 14 16 18 20 22; do check data/xqf131_sub.csv $n 15; done
if [ "$fallos" -eq 0 ]; then echo "VALIDACION DP OK"; else echo "VALIDACION DP CON $fallos FALLOS"; exit 1; fi
