#!/bin/bash
# Experimentos completos. Cada job toma lineas de la cola (colas/*.txt) hasta vaciarla.
# Reclamar una linea = mkdir runs/<id>.claim (atomico): dos jobs nunca toman la misma.
# Limite de la QOS a-pregrado: 8 h por job (10 min antes llega USR1 y el job se reenvia).
# Con la cuota de pregrado (2 jobs corriendo) se lanzan dos cadenas:
#   sbatch slurm/experimentos.slurm ; sbatch slurm/experimentos.slurm
# Otra cola:  sbatch --export=ALL,COLA=colas/vlsi.txt slurm/experimentos.slurm
#SBATCH --job-name=tsp_exp
#SBATCH --partition=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=4G
#SBATCH --time=08:00:00
#SBATCH --signal=B:USR1@600
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
P_LIST="1 2 4 8 16 32"          # no pasar de --cpus-per-task
COLA=${COLA:-colas/capitales.txt}
export OMP_PLACES=cores OMP_PROC_BIND=close
mkdir -p runs logs
[ -x bin/tsp_omp_task ] || { echo "Falta compilar: corre scripts/compilar.sh en el login"; exit 1; }

CPU=$(lscpu | grep -m1 'Model name' | sed 's/.*: *//')
echo "job $SLURM_JOB_ID | nodo $(hostname) | $CPU"

# 1) Overhead de OpenMP en este nodo (3 repeticiones por p)
B="runs/bench_${SLURM_JOB_ID}.csv"
bin/omp_bench 1 20000 --header > "$B"
for r in 1 2 3; do for p in $P_LIST; do bin/omp_bench "$p" 20000 >> "$B"; done; done
echo "$SLURM_JOB_ID,$(hostname),$CPU" >> runs/nodos.csv

# Si el tiempo se acaba: se corta el experimento en curso, se libera para que lo
# repita el siguiente job y se reenvia este script (la cola continua sola).
CUR=""; CHILD=""
on_timeout() {
    echo "$(date '+%F %T') tiempo casi agotado: libero ${CUR:-nada} y reenvio el job"
    if [ -n "$CHILD" ]; then pkill -P "$CHILD" 2>/dev/null || true; kill "$CHILD" 2>/dev/null || true; fi
    # Se reintenta una sola vez: si la misma linea vuelve a agotar el tiempo, se deja
    # marcada como fallida (runs/<id>.claim/failed) para no entrar en un ciclo infinito.
    if [ -n "$CUR" ]; then
        if [ -f "runs/$CUR.timeout" ]; then
            touch "runs/$CUR.claim/failed"; echo "  $CUR ya habia agotado el tiempo: queda como fallido"
        else
            touch "runs/$CUR.timeout"; rm -rf "runs/$CUR.claim" "runs/$CUR.csv"
        fi
    fi
    sbatch --export=ALL,COLA="$COLA" slurm/experimentos.slurm
    exit 0
}
trap on_timeout USR1

# 2) Cola de experimentos
# Formato de linea: tipo N REPS [REP_INICIAL] [DATOS] [COTA] [DEPTH]
while read -r tipo N REPS R0 DATA BOUND DEPTH <&3; do
    [[ -z "${tipo:-}" || "$tipo" == \#* ]] && continue
    if [ -n "${DATA:-}" ]; then
        DS=$(basename "$DATA" .csv)
        id="${tipo}_${DS}_${BOUND}_n${N}_r${R0}"
    else
        id="${tipo}_n${N}"
        if [ -n "${R0:-}" ]; then id="${id}_r${R0}"; else R0=1; fi
        DATA=data/ciudades.csv
    fi
    BOUND=${BOUND:-minout}; DEPTH=${DEPTH:-2}
    INIT=none; [ "$BOUND" = mst ] && INIT=nn           # v4 = cota MST + cota superior inicial
    mkdir "runs/$id.claim" 2>/dev/null || continue
    echo "$(date '+%F %T') inicia $id"
    rm -f "runs/$id.csv"
    CUR=$id
    if [ "$tipo" = "n" ]; then
        scripts/correr_n.sh "$N" "$REPS" "runs/$id.csv" "$P_LIST" "$DEPTH" "$R0" "$DATA" "$BOUND" "$INIT" &
    else
        scripts/correr_depth.sh "$N" "$REPS" "runs/$id.csv" "$P_LIST" &
    fi
    CHILD=$!
    wait "$CHILD"                # en segundo plano para poder atender la senal
    CHILD=""; CUR=""
    touch "runs/$id.claim/done"
    echo "$(date '+%F %T') termina $id"
done 3< "$COLA"
echo "cola vacia"
