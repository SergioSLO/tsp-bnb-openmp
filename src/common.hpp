// Codigo comun a todas las versiones del TSP por Branch and Bound.
// Corresponde a los Algoritmos 1 (CalcularBound) y 2 (Buscar) del informe.
// Datos: CSV de capitales (nombre,pais,lat,lon -> haversine, km) o de puntos
// (id,x,y -> distancia euclidiana redondeada, convencion EUC_2D de TSPLIB).
// Cotas: --bound minout (Algoritmo 1, la del informe) o mst (v4: arbol de expansion minima).
#pragma once
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>
#include <unistd.h>
#ifdef _OPENMP
#include <omp.h>
#endif

constexpr int MAXN = 64;                       // visitadas se guarda en una mascara de 64 bits
constexpr double INF = std::numeric_limits<double>::infinity();
using Mask = uint64_t;

// ---------------------------------------------------------------- argumentos
struct Args {
    std::string data = "data/ciudades.csv";
    int n = 10;                 // numero de ciudades (las primeras n del archivo)
    int p = 1;                  // hilos
    int depth = 2;              // profundidad de corte d (v2: prefijos, v3: tareas)
    std::string schedule = "static";   // v2: static | dynamic
    int rep = 0;                // numero de repeticion (solo se imprime)
    bool header = false;        // imprimir la cabecera del CSV
    std::string bound = "minout";      // minout | mst
    std::string init = "none";         // none | nn (cota superior inicial por vecino mas cercano)
};

inline Args parse_args(int argc, char** argv) {
    Args a;
    for (int i = 1; i < argc; ++i) {
        std::string k = argv[i];
        auto val = [&]() -> std::string {
            if (i + 1 >= argc) { fprintf(stderr, "falta valor para %s\n", k.c_str()); exit(1); }
            return argv[++i];
        };
        if (k == "--data") a.data = val();
        else if (k == "--n") a.n = std::stoi(val());
        else if (k == "--p") a.p = std::stoi(val());
        else if (k == "--depth") a.depth = std::stoi(val());
        else if (k == "--schedule") a.schedule = val();
        else if (k == "--rep") a.rep = std::stoi(val());
        else if (k == "--header") a.header = true;
        else if (k == "--bound") a.bound = val();
        else if (k == "--init") a.init = val();
        else { fprintf(stderr, "argumento desconocido: %s\n", k.c_str()); exit(1); }
    }
    if (a.n < 3 || a.n > MAXN) { fprintf(stderr, "n debe estar entre 3 y %d\n", MAXN); exit(1); }
    if (a.p < 1) a.p = 1;
    if (a.depth < 1) a.depth = 1;
    if (a.bound != "minout" && a.bound != "mst") { fprintf(stderr, "--bound minout|mst\n"); exit(1); }
    if (a.init != "none" && a.init != "nn") { fprintf(stderr, "--init none|nn\n"); exit(1); }
    return a;
}

// ---------------------------------------------------------------- datos
struct City { std::string name; double lat, lon; };   // (lat, lon) o (x, y)
inline bool g_euclid = false;                  // true: puntos (x, y) con EUC_2D

inline std::vector<City> read_cities(const std::string& path, int n) {
    std::ifstream f(path);
    if (!f) { fprintf(stderr, "no se pudo abrir %s\n", path.c_str()); exit(1); }
    std::string line;
    std::getline(f, line);                     // cabecera
    g_euclid = line.rfind("id,x,y", 0) == 0;
    std::vector<City> c;
    while ((int)c.size() < n && std::getline(f, line)) {
        if (line.empty() || line == "\r") continue;
        std::stringstream ss(line);
        std::string a, b, x, y;
        if (g_euclid) {
            std::getline(ss, a, ','); std::getline(ss, x, ','); std::getline(ss, y, ',');
        } else {
            std::getline(ss, a, ','); std::getline(ss, b, ',');
            std::getline(ss, x, ','); std::getline(ss, y, ',');
        }
        c.push_back({a, std::stod(x), std::stod(y)});
    }
    if ((int)c.size() < n) { fprintf(stderr, "el archivo solo tiene %zu ciudades\n", c.size()); exit(1); }
    return c;
}

// Distancia sobre la superficie terrestre (km).
inline double haversine(double lat1, double lon1, double lat2, double lon2) {
    const double R = 6371.0, r = M_PI / 180.0;
    double dlat = (lat2 - lat1) * r, dlon = (lon2 - lon1) * r;
    double h = std::sin(dlat / 2) * std::sin(dlat / 2) +
               std::cos(lat1 * r) * std::cos(lat2 * r) * std::sin(dlon / 2) * std::sin(dlon / 2);
    return 2 * R * std::asin(std::sqrt(h));
}

// Matriz D[i*n+j], O(n^2). Con p > 1 las filas se reparten entre hilos (pardo del Main paralelo).
inline std::vector<double> build_matrix(const std::vector<City>& c, int p) {
    int n = (int)c.size();
    std::vector<double> D(n * n, 0.0);
    (void)p;                                   // sin OpenMP no se usa
    #pragma omp parallel for num_threads(p) schedule(static)
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j)
            D[i * n + j] = (i == j) ? 0.0
                         : g_euclid ? std::nearbyint(std::hypot(c[i].lat - c[j].lat, c[i].lon - c[j].lon))
                                    : haversine(c[i].lat, c[i].lon, c[j].lat, c[j].lon);
    return D;
}

// ---------------------------------------------------------------- contadores
// Convencion de FLOPs: cada suma y cada comparacion de punto flotante cuenta 1.
struct alignas(64) Counters {
    uint64_t nodes = 0;         // llamadas a Buscar (nodos expandidos)
    uint64_t bound_calls = 0;   // llamadas a CalcularBound
    uint64_t updates = 0;       // actualizaciones de la mejor solucion (U)
    uint64_t tasks = 0;         // tareas OpenMP creadas (solo v3)
    uint64_t flops = 0;
    void add(const Counters& o) {
        nodes += o.nodes; bound_calls += o.bound_calls; updates += o.updates;
        tasks += o.tasks; flops += o.flops;
    }
};

// ---------------------------------------------------------------- estado compartido
inline int g_n = 0;
inline const double* g_D = nullptr;
inline bool g_mst = false;                     // cota MST (v4) en vez de minout
inline double g_best = INF;                    // mejor_costo (compartido)
inline int g_route[MAXN];                      // mejor_ruta (compartida)

inline double load_best() {                    // lectura concurrente (CR)
    double v;
    #pragma omp atomic read
    v = g_best;
    return v;
}

// Escritura MIN-CW: se vuelve a comparar dentro de la seccion critica para que
// (mejor_costo, mejor_ruta) se actualicen juntos y siempre quede el minimo.
inline void try_update(double total, const int* route, Counters& c) {
    if (total < load_best()) {
        #pragma omp critical(best_update)
        {
            if (total < g_best) {
                std::memcpy(g_route, route, sizeof(int) * g_n);
                #pragma omp atomic write
                g_best = total;
                c.updates++;
            }
        }
    }
}

// ---------------------------------------------------------------- Algoritmo 1
// CalcularBound (minout): costo + arista minima saliente de cada ciudad no visitada. O(n^2).
inline double bound_minout(double cost, Mask vis, Counters& c) {
    const int n = g_n;
    const double* D = g_D;
    double b = cost;
    uint64_t k = 0;
    for (int i = 0; i < n; ++i) {
        if (vis >> i & 1u) continue;
        double m = INF;
        const double* row = D + i * n;
        for (int j = 0; j < n; ++j)
            if (j != i && row[j] < m) m = row[j];
        b += m;
        ++k;
    }
    c.bound_calls++;
    c.flops += k * n;            // por ciudad: (n-1) comparaciones + 1 suma
    return b;
}

// Cota MST (v4). La ruta parcial termina en `last` (ya agregada a vis). Lo que falta es
// un camino last -> (todas las pendientes U) -> 0, que pesa al menos
//   min_{u in U} D[last][u] + MST(U) + min_{u in U} D[u][0].
// Prim sobre |U| = k nodos: O(k^2) <= O(n^2), el mismo orden que minout.
inline double bound_mst(double cost, int last, Mask vis, Counters& c) {
    const int n = g_n;
    const double* D = g_D;
    c.bound_calls++;
    int U[MAXN], k = 0;
    for (int i = 0; i < n; ++i) if (!(vis >> i & 1u)) U[k++] = i;
    if (k == 0) { c.flops += 1; return cost + D[last * n]; }
    double a = INF, z = INF;
    for (int t = 0; t < k; ++t) {
        a = std::min(a, D[last * n + U[t]]);
        z = std::min(z, D[U[t] * n]);
    }
    double key[MAXN];
    bool in[MAXN];
    for (int t = 0; t < k; ++t) { key[t] = D[U[0] * n + U[t]]; in[t] = false; }
    in[0] = true;
    double tree = 0;
    for (int it = 1; it < k; ++it) {
        int bt = -1;
        for (int t = 0; t < k; ++t) if (!in[t] && (bt < 0 || key[t] < key[bt])) bt = t;
        in[bt] = true;
        tree += key[bt];
        const double* row = D + U[bt] * n;
        for (int t = 0; t < k; ++t) if (!in[t] && row[U[t]] < key[t]) key[t] = row[U[t]];
    }
    c.flops += (uint64_t)2 * k + (uint64_t)2 * k * k + k + 3;   // minimos + Prim + sumas
    return cost + a + tree + z;
}

// vis todavia NO incluye a `next` (como en el Algoritmo 2).
inline double calc_bound(double cost, int next, Mask vis, Counters& c) {
    return g_mst ? bound_mst(cost, next, vis | (Mask(1) << next), c) : bound_minout(cost, vis, c);
}

// ---------------------------------------------------------------- Algoritmo 2
// Buscar secuencial con backtracking. route y vis son del hilo que llama (privados).
inline void dfs(int city, int level, double cost, Mask vis, int* route, Counters& c) {
    c.nodes++;
    const int n = g_n;
    const double* D = g_D;
    if (level == n) {
        double total = cost + D[city * n];
        c.flops += 2;            // suma + comparacion
        try_update(total, route, c);
        return;
    }
    for (int next = 0; next < n; ++next) {
        if (vis >> next & 1u) continue;
        double nc = cost + D[city * n + next];
        double b = calc_bound(nc, next, vis, c);
        c.flops += 2;            // nuevo_costo + comparacion de poda
        if (b < load_best()) {
            route[level] = next;
            dfs(next, level + 1, nc, vis | (Mask(1) << next), route, c);
        }
    }
}

// ---------------------------------------------------------------- utilidades
inline double wall_time() {
    using namespace std::chrono;
    return duration<double>(steady_clock::now().time_since_epoch()).count();
}

inline void reset_best() {
    g_best = INF;
    for (int i = 0; i < MAXN; ++i) g_route[i] = -1;
}

// Prepara el estado global segun las opciones: cota y, si --init nn, una cota superior
// inicial con la ruta del vecino mas cercano (sigue siendo exacto: solo poda antes).
inline void setup_search(const Args& a) {
    g_mst = (a.bound == "mst");
    reset_best();
    if (a.init != "nn") return;
    const int n = g_n;
    int r[MAXN], cur = 0;
    Mask v = 1u;
    double cost = 0;
    r[0] = 0;
    for (int k = 1; k < n; ++k) {
        int b = -1;
        for (int j = 0; j < n; ++j)
            if (!(v >> j & 1u) && (b < 0 || g_D[cur * n + j] < g_D[cur * n + b])) b = j;
        cost += g_D[cur * n + b];
        r[k] = b; v |= Mask(1) << b; cur = b;
    }
    g_best = cost + g_D[cur * n];
    std::memcpy(g_route, r, sizeof(int) * n);
}

inline std::string dataset_name(const std::string& path) {
    std::string b = path.substr(path.find_last_of("/\\") + 1);
    return b.substr(0, b.find_last_of('.'));
}

inline void print_header() {
    printf("version,n,p,schedule,depth,rep,host,time_s,best_cost_km,nodes,bound_calls,"
           "updates,tasks,flops,gflops_s,route,dataset,bound,init\n");
}

inline void print_row(const char* version, const Args& a, const char* schedule, int depth,
                      double t, const Counters& c) {
    char host[128] = "?";
    gethostname(host, sizeof(host));
    std::string r;
    for (int i = 0; i < g_n; ++i) r += std::to_string(g_route[i]) + "-";
    r += "0";
    printf("%s,%d,%d,%s,%d,%d,%s,%.6f,%.3f,%llu,%llu,%llu,%llu,%llu,%.4f,%s,%s,%s,%s\n",
           version, a.n, a.p, schedule, depth, a.rep, host, t, g_best,
           (unsigned long long)c.nodes, (unsigned long long)c.bound_calls,
           (unsigned long long)c.updates, (unsigned long long)c.tasks,
           (unsigned long long)c.flops, c.flops / t / 1e9, r.c_str(),
           dataset_name(a.data).c_str(), a.bound.c_str(), a.init.c_str());
}
