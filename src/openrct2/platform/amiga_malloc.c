/* Doug Lea's malloc (MIT-0) configured for AmigaOS/libnix: memory comes from AllocMem() in large steps,
 * every step is returned to the system when the program exits. Replaces libnix's flat-list malloc, whose
 * free() and malloc() walk every block (200-400 us per call with 40k blocks live). */
#include <proto/dos.h>
#include <proto/exec.h>
#include <exec/memory.h>
#include <stdlib.h>

#define LACKS_UNISTD_H 1
#define LACKS_FCNTL_H 1
#define LACKS_SYS_PARAM_H 1
#define LACKS_SYS_MMAN_H 1
#define LACKS_SCHED_H 1
#define LACKS_TIME_H 1
/* Large blocks (>= 256 KB, dlmalloc's mmap threshold) come straight from exec and go back to it on free: the
 * sbrk-style heap below can never be trimmed, so without this every big transient (autosave buffers, the track
 * design preview map, file reads) would raise the footprint for good. The hidden header keeps the exact size
 * FreeMem() needs; dlmalloc copes with any alignment of what MMAP returns. */
#define HAVE_MMAP 1
#define HAVE_MREMAP 0
#define MMAP_CLEARS 0
#define MMAP(s) amiga_mmap(s)
#define MUNMAP(a, s) amiga_munmap((a), (s))
#define DIRECT_MMAP(s) amiga_mmap(s)
#define HAVE_MORECORE 1
#define MORECORE amiga_morecore
#define MORECORE_CONTIGUOUS 0
#define MORECORE_CANNOT_TRIM 1
#define USE_LOCKS 0
#define NO_MALLINFO 0
#define NO_MALLOC_STATS 1
#define malloc_getpagesize 4096
#define DEFAULT_GRANULARITY (1024UL * 1024UL)
/* Heap corruption detection: FOOTERS stores a check word behind every chunk and fails loudly instead of
 * looping forever on a damaged bin; the failure is written to the trace file before the process ends. */
#define FOOTERS 1
/* OPENRCT2_HEAP_DEBUG=1 at build time turns on dlmalloc's own consistency walk at every malloc and free.
 * It is far too slow to ship, but it turns "the heap was damaged some time before shutdown" into "the heap
 * was damaged before this allocation", which is the only way to find a stray write without a debugger. */
#ifdef OPENRCT2_HEAP_DEBUG
    #define DEBUG 1
#endif
#define PROCEED_ON_ERROR 0
#include <stdio.h>
void amiga_trace(const char* line);
static void amiga_heap_abort(void)
{
    amiga_trace("HEAP: dlmalloc detected a corrupted chunk (FOOTERS) -- aborting");
    abort();
}
/* Which chunk, so the damage can be traced back to its neighbour rather than only reported. */
static void amiga_heap_usage_error(void* p)
{
    /* The first bytes of the payload usually say what the block was: a vtable pointer names a class, and
     * printable bytes name a string. Without a debugger this is how the victim gets identified. */
    char b[200];
    const unsigned char* q = (const unsigned char*)p;
    char txt[17];
    int i;
    for (i = 0; i < 16; i++)
        txt[i] = (q[i] >= 32 && q[i] < 127) ? (char)q[i] : '.';
    txt[16] = 0;
    snprintf(
        b, sizeof(b), "HEAP: damaged chunk at %p  first words %08lx %08lx %08lx %08lx  \"%s\"", p,
        (unsigned long)((const unsigned long*)p)[0], (unsigned long)((const unsigned long*)p)[1],
        (unsigned long)((const unsigned long*)p)[2], (unsigned long)((const unsigned long*)p)[3], txt);
    amiga_trace(b);
    amiga_heap_abort();
}
/* Checks the whole heap on demand: called from amiga_heap_verify() so a run can narrow down when the
 * damage appears instead of only learning that it happened. */
#define ABORT amiga_heap_abort()
#define USAGE_ERROR_ACTION(m, p) amiga_heap_usage_error(p)
#define CORRUPTION_ERROR_ACTION(m) amiga_heap_abort()
#define USE_DL_PREFIX 1

/* Every block amiga_mmap hands out, so the exit cleanup can give them back. AmigaOS does not reclaim a
 * program's AllocMem when it exits, so a large block still live at exit would be lost to the system until
 * the next reboot -- which is exactly what happened on the A4000 the first time this path was made the
 * default: 132 MB gone with the game not running. The header is the same 16 bytes the size alone used to
 * take, so the payload alignment is unchanged. */
struct amiga_big
{
    unsigned long size; /* what FreeMem needs, header included */
    struct amiga_big* next;
    struct amiga_big* prev;
    unsigned long pad;
};
static struct amiga_big* g_bigs = NULL;

static void* amiga_mmap(size_t s)
{
    /* On by default. The sbrk-style heap below can never be trimmed, so without this path every large
     * transient of a park load -- object decode buffers, file reads, autosave buffers -- raises the
     * footprint for the rest of the run. Measured on Crazy Castle: 159.7 MB held from the system against
     * 104.3 MB actually in use with this off, and 105.4 against 104.3 with it on. That 54 MB is the
     * difference between needing 192 MB and fitting on a 128 MB accelerator.
     *
     * It was off from test19 to test25 because a tester saw garbled text on test17, the first build that
     * returned large blocks to the system. That symptom has been gone since test19 and was not traced to
     * this switch, so the memory was being paid for nothing. OPENRCT2_NO_BIGALLOC=1 restores the old
     * behaviour for anyone who needs to bisect it. */
    static int checked = 0, on = 0;
    struct amiga_big* b;
    if (!checked)
    {
        char buf[8];
        checked = 1;
        on = GetVar((STRPTR) "OPENRCT2_NO_BIGALLOC", (STRPTR)buf, sizeof buf, 0) <= 0;
        amiga_trace(on ? "heap: large blocks come from exec and go back to it on free"
                       : "heap: OPENRCT2_NO_BIGALLOC set, large blocks stay in the heap (pre-test26 behaviour)");
    }
    if (!on)
        return (void*)~(size_t)0; /* MFAIL */
    b = (struct amiga_big*)AllocMem(s + sizeof(struct amiga_big), MEMF_ANY);
    if (b == NULL)
        return (void*)~(size_t)0; /* MFAIL */
    b->size = s + sizeof(struct amiga_big);
    b->prev = NULL;
    b->next = g_bigs;
    if (g_bigs != NULL)
        g_bigs->prev = b;
    g_bigs = b;
    return (char*)b + sizeof(struct amiga_big);
}

static int amiga_munmap(void* a, size_t s)
{
    struct amiga_big* b = (struct amiga_big*)((char*)a - sizeof(struct amiga_big));
    (void)s;
    if (b->prev != NULL)
        b->prev->next = b->next;
    else
        g_bigs = b->next;
    if (b->next != NULL)
        b->next->prev = b->prev;
    FreeMem(b, b->size);
    return 0;
}

struct amiga_step { struct amiga_step* next; unsigned long size; };
static struct amiga_step* g_steps = NULL;
static char* g_top = NULL;

static void* amiga_morecore(long n)
{
    if (n == 0)
        return g_top != NULL ? (void*)g_top : (void*)-1;
    if (n < 0)
        return (void*)-1;
    {
        unsigned long size = (unsigned long)n + sizeof(struct amiga_step);
        struct amiga_step* s = (struct amiga_step*)AllocMem(size, MEMF_ANY);
        if (s == NULL)
            return (void*)-1;
        if (n >= 4L * 1024L * 1024L)
        {
            char line[80];
            unsigned long kb = (unsigned long)n / 1024UL, d = 100000000UL;
            int i = 0;
            const char* pfx = "heap: morecore ";
            while (*pfx)
                line[i++] = *pfx++;
            while (d > kb && d > 1)
                d /= 10;
            while (d > 0)
            {
                line[i++] = (char)('0' + (kb / d) % 10);
                d /= 10;
            }
            pfx = " KB";
            while (*pfx)
                line[i++] = *pfx++;
            line[i] = 0;
            amiga_trace(line);
        }
        s->size = size;
        s->next = g_steps;
        g_steps = s;
        g_top = (char*)(s + 1) + n;
        return (void*)(s + 1);
    }
}

#include "dlmalloc.inc"

void* malloc(size_t n) { return dlmalloc(n); }
void free(void* p) { dlfree(p); }
void* calloc(size_t n, size_t m) { return dlcalloc(n, m); }
void* realloc(void* p, size_t n) { return dlrealloc(p, n); }
void* memalign(size_t a, size_t n) { return dlmemalign(a, n); }
int posix_memalign(void** pp, size_t a, size_t n) { return dlposix_memalign(pp, a, n); }
size_t malloc_usable_size(void* p) { return dlmalloc_usable_size(p); }

/* Heap statistics for the trace: bytes obtained from the system and bytes currently allocated by the program. */
void amiga_malloc_stats(unsigned long* footprint, unsigned long* inUse)
{
    struct mallinfo mi = dlmallinfo();
    *footprint = (unsigned long)dlmalloc_footprint();
    *inUse = (unsigned long)mi.uordblks;
}

/* Runs after every other destructor (priority 101 = first constructor, last destructor). */
__attribute__((destructor(101))) static void amiga_malloc_cleanup(void)
{
    struct amiga_step* s = g_steps;
    struct amiga_big* b = g_bigs;
    g_steps = NULL;
    g_bigs = NULL;
    while (s != NULL)
    {
        struct amiga_step* next = s->next;
        FreeMem(s, s->size);
        s = next;
    }
    /* Anything still allocated through amiga_mmap: the program is ending, and nothing else will ever
     * give these back. */
    while (b != NULL)
    {
        struct amiga_big* next = b->next;
        FreeMem(b, b->size);
        b = next;
    }
}
