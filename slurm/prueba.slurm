#!/bin/bash
# Prueba corta en la particion debug: valida, mide overhead y calibra tiempos.
# Antes, en el login: scripts/compilar.sh   (los nodos no pueden compilar)
# Lanzar desde la carpeta codigo/:  sbatch slurm/prueba.slurm
#SBATCH --job-name=tsp_prueba
#SBATCH --partition=debug
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
mkdir -p logs
export OMP_PLACES=cores OMP_PROC_BIND=close

echo "nodo: $(hostname) | $(lscpu | grep -m1 'Model name' | sed 's/ \+/ /g')"
[ -x bin/tsp_omp_task ] || { echo "Falta compilar: corre scripts/compilar.sh en el login"; exit 1; }
ldd bin/tsp_omp_task | grep -E "gomp|stdc|not found" || true

echo "== validacion =="
scripts/validar.sh

echo "== overhead OpenMP =="
bin/omp_bench 1 20000 --header
for p in 2 4 8; do bin/omp_bench $p 20000; done

echo "== calibracion v1 (tiempo vs n) =="
bin/tsp_seq --n 12 --header
for n in 14 16 17 18; do bin/tsp_seq --n $n; done

echo "== calibracion v3 n=17 =="
for p in 1 2 4 8; do bin/tsp_omp_task --n 17 --p $p; done
