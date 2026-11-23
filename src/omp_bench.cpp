// Microbenchmarks del overhead de OpenMP (Tabla 3 del informe, metodologia de Bull 1999).
// Para cada p mide, en segundos por operacion:
//   t_fork: abrir y cerrar una region paralela vacia
//   t_bar : una barrera
//   t_crit: una entrada a seccion critica (todos los hilos compiten)
//   t_task: crear y completar una tarea vacia
#include <omp.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <unistd.h>

static volatile long sink = 0;

int main(int argc, char** argv) {
    int p = argc > 1 ? std::atoi(argv[1]) : 1;
    long R = argc > 2 ? std::atol(argv[2]) : 20000;
    bool header = argc > 3 && std::string(argv[3]) == "--header";
    char host[128] = "?";
    gethostname(host, sizeof(host));

    // calentamiento: crea el pool de hilos
    #pragma omp parallel num_threads(p)
    { sink = sink + 1; }

    double t0 = omp_get_wtime();
    for (long r = 0; r < R; ++r) {
        #pragma omp parallel num_threads(p)
        { if (omp_get_thread_num() == 0) sink = sink + 1; }
    }
    double t_fork = (omp_get_wtime() - t0) / R;

    double t_bar = 0;
    #pragma omp parallel num_threads(p)
    {
        #pragma omp barrier
        double s = omp_get_wtime();
        for (long r = 0; r < R; ++r) {
            #pragma omp barrier
        }
        #pragma omp master
        t_bar = (omp_get_wtime() - s) / R;
    }

    double t_crit = 0;
    #pragma omp parallel num_threads(p)
    {
        long mine = R / p;
        #pragma omp barrier
        double s = omp_get_wtime();
        for (long r = 0; r < mine; ++r) {
            #pragma omp critical(bench)
            sink = sink + 1;
        }
        #pragma omp barrier
        #pragma omp master
        t_crit = (omp_get_wtime() - s) / (mine * p);
    }

    double t_task = 0;
    #pragma omp parallel num_threads(p)
    #pragma omp single
    {
        double s = omp_get_wtime();
        for (long r = 0; r < R; ++r) {
            #pragma omp task
            { sink = sink + 1; }
        }
        #pragma omp taskwait
        t_task = (omp_get_wtime() - s) / R;
    }

    if (header) printf("host,p,R,t_fork_s,t_bar_s,t_crit_s,t_task_s\n");
    printf("%s,%d,%ld,%.3e,%.3e,%.3e,%.3e\n", host, p, R, t_fork, t_bar, t_crit, t_task);
    return 0;
}
