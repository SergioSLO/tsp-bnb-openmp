#!/bin/bash
# Diagnostico de dos efectos vistos en los experimentos (n003):
#  1) con p = 1 las versiones OpenMP tardan ~1.44x mas que v1 con los mismos nodos
#  2) p = 32 es mas lento que p = 16
# Revisa la topologia asignada (hyperthreading, sockets) y repite con otra afinidad.
# Antes, en el login: scripts/compilar.sh   Lanzar: sbatch slurm/diagnostico.slurm
#SBATCH --job-name=tsp_diag
#SBATCH --partition=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=2G
#SBATCH --time=00:40:00
#SBATCH --output=logs/%x_%j.out

set -uo pipefail
cd "$SLURM_SUBMIT_DIR"
N=18
echo "== topologia ($(hostname)) =="
lscpu | grep -E "Model name|Socket|Core\(s\) per|Thread\(s\) per|^CPU\(s\)|NUMA node"
echo "CPUs asignadas al job: $(taskset -cp $$ | sed 's/.*: //')  (nproc = $(nproc))"
grep -E "^(physical id|core id)" /proc/cpuinfo | paste - - | sort -u | wc -l | sed 's/^/nucleos fisicos distintos en el nodo: /'
for c in $(taskset -cp $$ | sed 's/.*: //' | tr ',' ' '); do
    case $c in *-*) seq ${c%-*} ${c#*-};; *) echo $c;; esac
done | while read -r c; do
    echo "$c $(cat /sys/devices/system/cpu/cpu$c/topology/physical_package_id) $(cat /sys/devices/system/cpu/cpu$c/topology/core_id)"
done | awk '{s[$2]++; k[$2" "$3]++} END {for (x in s) printf "socket %s: %d CPUs logicas\n", x, s[x]; printf "nucleos fisicos asignados: %d\n", length(k)}'

run() { echo -n "$1 | "; shift; "$@" | cut -d, -f1,3,8,10; }

echo "== 1) costo con p = 1 (n=$N) =="
export OMP_PLACES=cores OMP_PROC_BIND=close
run "v1 sin OpenMP           " bin/tsp_seq --n $N
run "v1 con -fopenmp         " bin/tsp_seq_omp --n $N
run "v2 p=1 bind=close       " bin/tsp_omp_for --n $N --p 1 --schedule dynamic
OMP_PROC_BIND=false run "v2 p=1 sin afinidad     " bin/tsp_omp_for --n $N --p 1 --schedule dynamic
OMP_WAIT_POLICY=passive run "v2 p=1 wait=passive     " bin/tsp_omp_for --n $N --p 1 --schedule dynamic

echo "== 2) p = 16 vs 32 con distinta afinidad (n=$N) =="
for p in 16 32; do
    OMP_PLACES=cores   OMP_PROC_BIND=close  run "p=$p cores/close      " bin/tsp_omp_for --n $N --p $p --schedule dynamic --depth 3
    OMP_PLACES=cores   OMP_PROC_BIND=spread run "p=$p cores/spread     " bin/tsp_omp_for --n $N --p $p --schedule dynamic --depth 3
    OMP_PLACES=threads OMP_PROC_BIND=close  run "p=$p threads/close    " bin/tsp_omp_for --n $N --p $p --schedule dynamic --depth 3
    OMP_PROC_BIND=false                     run "p=$p sin afinidad     " bin/tsp_omp_for --n $N --p $p --schedule dynamic --depth 3
done
echo "fin"
