#!/bin/bash
# Corre todas las versiones para un n fijo y agrega las filas a un CSV.
# uso: scripts/correr_n.sh N REPS SALIDA.csv "LISTA_P" [DEPTH] [REP_INICIAL] [DATOS] [COTA] [INIT]
set -euo pipefail
N=$1; REPS=$2; OUT=$3; P_LIST=$4; DEPTH=${5:-2}; R0=${6:-1}
DATA=${7:-data/ciudades.csv}; BOUND=${8:-minout}; INIT=${9:-none}
X=(--data "$DATA" --bound "$BOUND" --init "$INIT")
first=1
run() {
    if [ $first -eq 1 ]; then "$@" --header >> "$OUT"; first=0; else "$@" >> "$OUT"; fi
}
for rep in $(seq "$R0" $((R0 + REPS - 1))); do            # repeticiones por fuera: el ruido se reparte
    run bin/tsp_seq --n "$N" --rep "$rep" "${X[@]}"
    for p in $P_LIST; do
        run bin/tsp_omp_for  --n "$N" --p "$p" --depth "$DEPTH" --schedule static  --rep "$rep" "${X[@]}"
        run bin/tsp_omp_for  --n "$N" --p "$p" --depth "$DEPTH" --schedule dynamic --rep "$rep" "${X[@]}"
        run bin/tsp_omp_task --n "$N" --p "$p" --depth "$DEPTH" --rep "$rep" "${X[@]}"
    done
done
