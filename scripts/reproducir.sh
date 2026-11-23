#!/bin/bash
# Reproduce de punta a punta lo que se puede sin Khipu:
#   1) compila las versiones, 2) valida contra fuerza bruta y Held-Karp,
#   3) regenera figuras, tablas y derivados desde resultados/, 4) compila el informe.
# Uso (desde la raiz):  scripts/reproducir.sh [--rapido] [--sin-informe]
#   --rapido      valida solo contra fuerza bruta (n <= 11), sin Held-Karp
#   --sin-informe no compila el PDF (no requiere LaTeX)
set -euo pipefail
cd "$(dirname "$0")/.."
RAPIDO=0; INFORME=1
for a in "$@"; do
    case $a in --rapido) RAPIDO=1;; --sin-informe) INFORME=0;; *) echo "opcion desconocida: $a"; exit 1;; esac
done
chmod +x scripts/*.sh
echo "== 1/4 compilar"; scripts/compilar.sh
echo "== 2/4 validar";  scripts/validar.sh | tail -1
[ "$RAPIDO" = 1 ] || P=2 scripts/validar_dp.sh | tail -1
echo "== 3/4 analisis"; mkdir -p resultados/derivados && python3 analisis/analisis.py > resultados/derivados/analisis_log.txt 2>&1 \
    || { cat resultados/derivados/analisis_log.txt; exit 1; }
echo "   figuras/ e informe/generado/ regenerados (detalle en resultados/derivados/analisis_log.txt)"
if [ "$INFORME" = 1 ]; then
    echo "== 4/4 informe"
    if command -v latexmk >/dev/null; then
        (cd informe && latexmk -pdf -interaction=nonstopmode informe_final.tex > /dev/null 2>&1) \
            && echo "   informe/informe_final.pdf" || { echo "   error de LaTeX: ver informe/informe_final.log"; exit 1; }
    else
        echo "   latexmk no esta instalado: se omite (usa --sin-informe o compila en Overleaf)"
    fi
fi
echo "OK"
