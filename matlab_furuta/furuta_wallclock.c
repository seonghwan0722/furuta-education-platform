#include "furuta_wallclock.h"
#ifdef __linux__
#include <time.h>
double furuta_wallclock(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}
#else
double furuta_wallclock(void) { return 0.0; }
#endif
