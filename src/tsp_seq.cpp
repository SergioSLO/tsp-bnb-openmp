// v1: TSP secuencial por Branch and Bound (Algoritmos 1-3 del informe).
// Se compila SIN OpenMP: los pragmas de common.hpp se ignoran.
#include "common.hpp"

int main(int argc, char** argv) {
    Args a = parse_args(argc, argv);
    a.p = 1;
    auto cities = read_cities(a.data, a.n);

    double t0 = wall_time();
    auto D = build_matrix(cities, 1);
    g_n = a.n; g_D = D.data();
    setup_search(a);

    Counters c;
    int route[MAXN];
    route[0] = 0;
    dfs(0, 1, 0.0, 1u, route, c);              // Buscar(0, 1, 0) con la ciudad 0 visitada
    double t = wall_time() - t0;

    if (a.header) print_header();
    print_row("v1_seq", a, "none", 0, t, c);
    return 0;
}
