// Validador: fuerza bruta sobre las (n-1)! rutas que empiezan en la ciudad 0.
// Practico hasta n = 12. Se usa para comprobar que las versiones B&B dan el optimo.
#include "common.hpp"

int main(int argc, char** argv) {
    Args a = parse_args(argc, argv);
    if (a.n > 12) { fprintf(stderr, "fuerza bruta solo hasta n = 12\n"); return 1; }
    auto cities = read_cities(a.data, a.n);

    double t0 = wall_time();
    auto D = build_matrix(cities, 1);
    g_n = a.n; g_D = D.data();
    reset_best();

    std::vector<int> perm(a.n);
    for (int i = 0; i < a.n; ++i) perm[i] = i;
    Counters c;
    do {
        double cost = 0;
        for (int i = 0; i + 1 < a.n; ++i) cost += D[perm[i] * a.n + perm[i + 1]];
        cost += D[perm[a.n - 1] * a.n];
        c.nodes++;
        if (cost < g_best) { g_best = cost; std::copy(perm.begin(), perm.end(), g_route); c.updates++; }
    } while (std::next_permutation(perm.begin() + 1, perm.end()));
    double t = wall_time() - t0;

    if (a.header) print_header();
    print_row("brute", a, "none", 0, t, c);
    return 0;
}
