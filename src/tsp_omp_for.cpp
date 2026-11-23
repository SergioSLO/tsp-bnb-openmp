// v2: TSP paralelo con OpenMP "parallel for" sobre prefijos del arbol.
// Se generan todas las rutas parciales de profundidad d (los primeros d niveles del
// arbol, con su cota ya calculada) y se reparten entre hilos con schedule static o
// dynamic. Cada hilo explora sus subarboles con dfs() sobre su propia ruta (privada).
#include "common.hpp"

struct Prefix {
    int city, level;
    double cost, bound;
    Mask vis;
    int route[MAXN];
};

// Expande los primeros niveles. Aun no hay solucion (mejor_costo = inf), asi que no se
// poda aqui: la cota se guarda y se compara al momento de explorar el prefijo.
static void expand(int city, int level, double cost, Mask vis, int* route, int stop,
                   std::vector<Prefix>& out, Counters& c) {
    c.nodes++;
    const int n = g_n;
    for (int next = 0; next < n; ++next) {
        if (vis >> next & 1u) continue;
        double nc = cost + g_D[city * n + next];
        double b = calc_bound(nc, next, vis, c);
        c.flops += 2;
        route[level] = next;
        if (level + 1 == stop || level + 1 == n) {
            Prefix p{next, level + 1, nc, b, vis | (Mask(1) << next), {}};
            std::memcpy(p.route, route, sizeof(int) * n);
            out.push_back(p);
        } else {
            expand(next, level + 1, nc, vis | (Mask(1) << next), route, stop, out, c);
        }
    }
}

int main(int argc, char** argv) {
    Args a = parse_args(argc, argv);
    const bool dynamic = (a.schedule == "dynamic");
    if (!dynamic && a.schedule != "static") { fprintf(stderr, "--schedule static|dynamic\n"); return 1; }
    auto cities = read_cities(a.data, a.n);

    double t0 = wall_time();
    auto D = build_matrix(cities, a.p);
    g_n = a.n; g_D = D.data();
    setup_search(a);

    Counters total;
    std::vector<Prefix> pre;
    int route[MAXN];
    route[0] = 0;
    expand(0, 1, 0.0, 1u, route, 1 + a.depth, pre, total);
    const long m = (long)pre.size();

    omp_set_schedule(dynamic ? omp_sched_dynamic : omp_sched_static, dynamic ? 1 : 0);
    #pragma omp parallel num_threads(a.p)
    {
        Counters c;
        int r[MAXN];
        #pragma omp for schedule(runtime) nowait
        for (long i = 0; i < m; ++i) {
            const Prefix& q = pre[i];
            c.flops += 1;
            if (q.bound < load_best()) {
                std::memcpy(r, q.route, sizeof(int) * g_n);
                if (q.level == g_n) {             // n muy chico: el prefijo ya es una hoja
                    c.nodes++; c.flops += 2;
                    try_update(q.cost + g_D[q.city * g_n], r, c);
                } else {
                    dfs(q.city, q.level, q.cost, q.vis, r, c);
                }
            }
        }
        #pragma omp critical(merge)
        total.add(c);
    }                                            // barrera implicita = fin del pardo
    double t = wall_time() - t0;

    if (a.header) print_header();
    print_row(dynamic ? "v2_for_dynamic" : "v2_for_static", a, dynamic ? "dynamic" : "static",
              a.depth, t, total);
    return 0;
}
