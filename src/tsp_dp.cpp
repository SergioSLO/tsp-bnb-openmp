// Validador exacto por programacion dinamica (Held-Karp), O(n^2 2^n) tiempo y
// O(n 2^n) memoria. Independiente de Branch and Bound: sirve para comprobar el optimo
// hasta n ~ 23 (con n = 23 usa ~740 MB).
#include "common.hpp"

int main(int argc, char** argv) {
    Args a = parse_args(argc, argv);
    if (a.n > 24) { fprintf(stderr, "Held-Karp solo hasta n = 24\n"); return 1; }
    auto cities = read_cities(a.data, a.n);

    double t0 = wall_time();
    auto D = build_matrix(cities, 1);
    g_n = a.n; g_D = D.data();
    reset_best();

    const int m = a.n - 1;                      // ciudades 1..n-1, la 0 es el origen
    const size_t S = size_t(1) << m;
    std::vector<double> dp(S * m, INF);         // dp[mask*m + j]: camino 0 -> ... -> j+1
    std::vector<int8_t> par(S * m, -1);
    for (int j = 0; j < m; ++j) dp[(size_t(1) << j) * m + j] = D[j + 1];
    for (size_t mask = 1; mask < S; ++mask)
        for (int j = 0; j < m; ++j) {
            if (!(mask >> j & 1)) continue;
            double cur = dp[mask * m + j];
            if (cur == INF) continue;
            for (int k = 0; k < m; ++k) {
                if (mask >> k & 1) continue;
                size_t nm = mask | (size_t(1) << k);
                double v = cur + D[(j + 1) * a.n + k + 1];
                if (v < dp[nm * m + k]) { dp[nm * m + k] = v; par[nm * m + k] = (int8_t)j; }
            }
        }
    size_t full = S - 1;
    int last = 0;
    for (int j = 0; j < m; ++j) {
        double v = dp[full * m + j] + D[(j + 1) * a.n];
        if (v < g_best) { g_best = v; last = j; }
    }
    // reconstruir la ruta
    size_t mask = full;
    for (int pos = a.n - 1; pos >= 1; --pos) {
        g_route[pos] = last + 1;
        int pj = par[mask * m + last];
        mask &= ~(size_t(1) << last);
        last = pj;
    }
    g_route[0] = 0;
    double t = wall_time() - t0;

    Counters c;
    if (a.header) print_header();
    print_row("dp_heldkarp", a, "none", 0, t, c);
    return 0;
}
