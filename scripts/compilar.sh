#!/bin/bash
# Compila todas las versiones en bin/. Correr UNA vez en el login de Khipu.
set -euo pipefail
cd "$(dirname "$0")/.."
CXX=${CXX:-g++}
# Los nodos de computo no tienen headers para compilar: se compila en el login y se
# fija la ruta (rpath) a libstdc++ y libgomp del compilador para que corran en los nodos.
LIB1=$(dirname "$($CXX -print-file-name=libstdc++.so)")
LIB2=$(dirname "$($CXX -print-file-name=libgomp.so)")
FLAGS="-O3 -std=c++17 -Wall -Wextra -Wl,-rpath,$LIB1 -Wl,-rpath,$LIB2"
mkdir -p bin
# v1 y el validador sin OpenMP (secuencial puro)
$CXX $FLAGS -Wno-unknown-pragmas src/tsp_seq.cpp   -o bin/tsp_seq
$CXX $FLAGS -Wno-unknown-pragmas src/tsp_brute.cpp -o bin/tsp_brute
$CXX $FLAGS -Wno-unknown-pragmas src/tsp_dp.cpp    -o bin/tsp_dp
# diagnostico: v1 compilada con OpenMP (mismo codigo, distinto runtime)
$CXX $FLAGS -fopenmp src/tsp_seq.cpp  -o bin/tsp_seq_omp
$CXX $FLAGS -fopenmp src/tsp_omp_for.cpp  -o bin/tsp_omp_for
$CXX $FLAGS -fopenmp src/tsp_omp_task.cpp -o bin/tsp_omp_task
$CXX -O1 -std=c++17 -Wl,-rpath,$LIB1 -Wl,-rpath,$LIB2 -fopenmp src/omp_bench.cpp -o bin/omp_bench
echo "compilado: $(ls bin | tr '\n' ' ')"
echo "rpath: $LIB1 $LIB2"
