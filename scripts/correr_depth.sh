#!/bin/bash
# Efecto de la profundidad de corte d (numero de tareas/prefijos) para un n fijo.
# uso: scripts/correr_depth.sh N REPS SALIDA.csv "LISTA_P"
set -euo pipefail
N=$1; REPS=$2; OUT=$3; P_LIST=$4
first=1
run() {
    if [ $first -eq 1 ]; then "$@" --header >> "$OUT"; first=0; else "$@" >> "$OUT"; fi
}
for rep in $(seq 1 "$REPS"); do
    for d in 1 2 3 4; do
        for p in $P_LIST; do
            run bin/tsp_omp_for  --n "$N" --p "$p" --depth "$d" --schedule dynamic --rep "$rep"
            run bin/tsp_omp_task --n "$N" --p "$p" --depth "$d" --rep "$rep"
        done
    done
done
