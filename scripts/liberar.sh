#!/bin/bash
# Libera los experimentos que quedaron a medias (job cancelado o caido), para relanzarlos.
# Ejecutar solo cuando no haya jobs tsp_exp corriendo (squeue --me).
cd "$(dirname "$0")/../runs" || exit 1
for c in *.claim; do
    [ -d "$c" ] || continue
    if [ ! -f "$c/done" ]; then
        id="${c%.claim}"
        echo "liberando $id"
        rm -rf "$c" "$id.csv"
    fi
done
