# TSP exacto por Branch and Bound con OpenMP

Proyecto final de **CS4052 – Computación Paralela y Distribuida** (UTEC, 2026-II).
Integrantes: Melanie Alexia Cortez Rojas, Sergio Sebastián Lezama Orihuela, Federico Iribar Casanova.
Docente: José Antonio Fiestas Iquira.

Resuelve de forma exacta el Problema del Agente Viajero con Branch and Bound, en una versión secuencial y tres paralelas con OpenMP. Todas se ejecutaron y midieron en el clúster **Khipu** de la UTEC. El repositorio contiene el código, los datos, las colas de experimentos, los resultados crudos medidos en Khipu y el análisis que regenera todas las figuras y tablas del informe.

## Resultados principales

| | |
| --- | --- |
| Ruta mínima, 20 capitales | **69 696 km** (57 288 km con 10), validada contra Held–Karp |
| Mejor speedup con la cota original | **12.4** (v3, VLSI n = 20, 32 hilos); **8.6** con 16 núcleos (capitales, n = 20) |
| v4 (cota MST) | 14 000× menos nodos que la cota original; resuelve VLSI hasta **n = 33** (9 min en secuencial, 70 s con 16 núcleos) |
| Regresión | $T_p(n) = a\,c^n/p^\beta + T_0$ con $R^2 \ge 0.99$; $\beta = 0.73$–$0.83$; el speedup crece con $n$ |
| Hardware | 32 CPUs por job = 16 núcleos físicos con hyperthreading, por eso $p = 32$ no mejora sobre $p = 16$ |

## Estructura

```
src/            código C++17
  common.hpp      datos, distancias, cotas (minout y MST), búsqueda, contadores, salida CSV
  tsp_seq.cpp     v1 secuencial (se compila sin OpenMP)
  tsp_omp_for.cpp v2: parallel for sobre prefijos de profundidad d (static | dynamic)
  tsp_omp_task.cpp v3: tareas OpenMP con corte en el nivel d
  tsp_brute.cpp   validador por fuerza bruta (n <= 12)
  tsp_dp.cpp      validador Held–Karp, programación dinámica (n <= 23)
  omp_bench.cpp   microbenchmarks del overhead de OpenMP (t_fork, t_bar, t_crit, t_task)
data/           ciudades.csv (20 capitales), xqf131.tsp (VLSI original), xqf131_sub.csv (orden aleatorio, semilla 2026)
colas/          capitales.txt y vlsi.txt: los experimentos que se corrieron en Khipu
scripts/        compilar, validar, correr, juntar, liberar, preparar_vlsi.py, reproducir.sh
slurm/          prueba.slurm (debug), experimentos.slurm (cola), diagnostico.slurm (hardware y afinidad)
analisis/       analisis.py: figuras, tablas, ajustes y regresiones desde resultados/
resultados/     datos crudos de Khipu (no editar) y derivados/ (generado)
figuras/        generado por analisis.py
informe/        informe_final.tex, references.bib, generado/ (tablas generadas), informe_final.pdf
```

**v4** no es un binario aparte: son v1–v3 ejecutadas con `--bound mst --init nn`.

Todos los binarios aceptan `--data ARCHIVO --n N --p P --depth D --schedule static|dynamic --bound minout|mst --init none|nn --rep R --header` e imprimen una fila CSV con la versión, el nodo, el tiempo, el costo, la ruta, los nodos explorados, las llamadas a la cota, las actualizaciones de la mejor solución, las tareas y los FLOPs (cada suma o comparación de punto flotante cuenta 1).

## Reproducir

Requisitos: `g++` con OpenMP (GCC ≥ 9), Python 3.11 con `pip install -r requirements.txt` y, para el PDF, LaTeX con `latexmk`. Funciona en Linux, en WSL y en el login de Khipu.

### 1. Todo lo que no necesita Khipu (~1 min)

```bash
bash scripts/reproducir.sh            # compila, valida, regenera figuras/tablas y compila el informe
bash scripts/reproducir.sh --rapido --sin-informe   # sin Held–Karp ni LaTeX
```

`analisis/analisis.py` regenera desde `resultados/*.csv` todas las figuras (`figuras/`), las tablas del informe (`informe/generado/`) y los derivados (`resultados/derivados/`: medianas, speedup, eficiencia, $\sigma_p$, ajustes de $T_s(n)$, el modelo con overhead y la regresión de escalabilidad). Ningún número del informe se escribe a mano.

### 2. Repetir las mediciones en Khipu

```bash
# en Khipu, desde la carpeta del repositorio
chmod -R u+rwX . && chmod +x scripts/*.sh
sed -i 's/\r$//' scripts/*.sh slurm/*.slurm colas/*.txt     # si los archivos pasaron por Windows
scripts/compilar.sh                     # SIEMPRE en el login: los nodos no tienen headers para compilar
scripts/validar.sh && scripts/validar_dp.sh
sbatch slurm/prueba.slurm               # debug, < 30 min: valida y mide el overhead

sbatch slurm/experimentos.slurm         # capitales: colas/capitales.txt (~4.5 h)
sbatch --export=ALL,COLA=colas/vlsi.txt slurm/experimentos.slurm   # VLSI y v4 (~15 h)
sbatch slurm/diagnostico.slurm          # topología asignada y efecto de la afinidad (~15 min)

squeue --me                             # al terminar:
RESULTADOS=resultados_nuevos scripts/juntar.sh
RESULTADOS=resultados_nuevos python3 analisis/analisis.py   # figuras y tablas quedan en resultados_nuevos/
```

Con `RESULTADOS=<carpeta>` una corrida nueva no sobrescribe los datos del informe. Sin esa variable, `juntar.sh` y `analisis.py` trabajan sobre `resultados/`, `figuras/` e `informe/generado/`. El análisis espera el conjunto completo: las dos colas y los microbenchmarks.

Detalles de la cola (`slurm/experimentos.slurm`):

- Cada job toma líneas de la cola hasta vaciarla. El reclamo de una línea es `mkdir runs/<id>.claim`, que es atómico, así que dos jobs nunca corren la misma.
- Cada línea corre completa en un solo nodo, de modo que $T_s$ y $T_p$ de un mismo $n$ se miden en el mismo hardware.
- El límite de la QOS `a-pregrado` es de **8 h por job**. 10 min antes llega `USR1`: el job libera la línea en curso y se reenvía. Una línea que agota el tiempo dos veces queda marcada como fallida, para no repetirse sin fin.
- `scripts/liberar.sh` libera las líneas que quedaron a medias si se cancela un job. `juntar.sh` avisa si quedó algo pendiente o fallido.
- La QOS limita las CPUs por usuario: con 32 CPUs por job, los dos jobs corren uno detrás del otro.

## Notas sobre los datos

- **Todas las mediciones son del nodo n003** (2 × Xeon Gold 6130; ver la Tabla de plataforma del informe). `resultados/nodos.csv` registra el nodo de cada job y `resultados/diagnostico_n003.txt` la topología asignada.
- `resultados/tiempos.csv` (capitales) se midió con una compilación anterior a la extensión VLSI/v4: mismo algoritmo, máscara de 32 bits y sin las columnas `dataset,bound,init`. El código actual reproduce exactamente sus nodos explorados y costos; por ejemplo, n = 14 da 186 497 nodos y 60 861.978 km.
- En esa tanda, las versiones OpenMP con $p = 1$ fueron 1.44× más lentas que v1 por la afinidad (`OMP_PROC_BIND`), no por OpenMP; lo explica la sección 5.6 del informe.
- `data/xqf131_sub.csv` se genera con `python3 scripts/preparar_vlsi.py data/xqf131.tsp data/xqf131_sub.csv`. La instancia de tamaño $n$ son sus primeras $n$ filas. Las distancias son euclidianas redondeadas (EUC_2D de TSPLIB).

## Fuentes de datos

- Capitales: coordenadas públicas de cada capital, distancias con haversine ($R = 6371$ km).
- VLSI: `xqf131` de la colección VLSI de W. Cook (University of Waterloo), https://www.math.uwaterloo.ca/tsp/vlsi/.
