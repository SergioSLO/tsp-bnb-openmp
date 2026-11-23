// v3: TSP paralelo con tareas OpenMP (BuscarPar, Algoritmo 4 del informe).
// Cada hijo de un nodo en los primeros d niveles se lanza como tarea con copias
// privadas (firstprivate) de la ruta y de visitadas. Por debajo del corte, cada tarea
// sigue en secuencial con dfs() para no crear O((n-1)!) tareas de grano fino.
#include "common.hpp"
#include <array>

static int g_cut = 2;
static Counters g_tc[256];                       // contadores por hilo (alineados a 64 B)

static void buscar_par(int city, int level, double cost, Mask vis, std::array<int, MAXN> route) {
    Counters& c = g_tc[omp_get_thread_num()];
    c.nodes++;
    const int n = g_n;
    if (level == n) {
        c.flops += 2;
        try_update(cost + g_D[city * n], route.data(), c);
        return;
    }
    const bool spawn = level <= g_cut;           // niveles 1..d crean tareas
    for (int next = 0; next < n; ++next) {
        if (vis >> next & 1u) continue;
        double nc = cost + g_D[city * n + next];
        double b = calc_bound(nc, next, vis, c);
        c.flops += 2;
        if (b < load_best()) {
            std::array<int, MAXN> r2 = route;    // copia privada O(n)
            r2[level] = next;
            Mask v2 = vis | (Mask(1) << next);
            if (spawn) {
                c.tasks++;
                #pragma omp task firstprivate(next, level, nc, v2, r2)
                buscar_par(next, level + 1, nc, v2, r2);
            } else {
                dfs(next, level + 1, nc, v2, r2.data(), c);
            }
        }
    }
    if (spawn) {
        #pragma omp taskwait                     // fin del pardo de este nivel
    }
}

int main(int argc, char** argv) {
    Args a = parse_args(argc, argv);
    if (a.p > 256) { fprintf(stderr, "p maximo 256\n"); return 1; }
    g_cut = a.depth;
    auto cities = read_cities(a.data, a.n);

    double t0 = wall_time();
    auto D = build_matrix(cities, a.p);
    g_n = a.n; g_D = D.data();
    setup_search(a);
    for (auto& c : g_tc) c = Counters();

    std::array<int, MAXN> route{};
    route[0] = 0;
    #pragma omp parallel num_threads(a.p)
    #pragma omp single
    buscar_par(0, 1, 0.0, 1u, route);
    double t = wall_time() - t0;

    Counters total;
    for (int i = 0; i < a.p; ++i) total.add(g_tc[i]);
    if (a.header) print_header();
    print_row("v3_task", a, "task", a.depth, t, total);
    return 0;
}
