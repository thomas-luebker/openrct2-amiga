#pragma once
// Stage-probe tracing for the AmigaOS port: one line per call, written straight to disk.
#ifdef __amigaos__
    #include <cstdio>
extern "C" void amiga_trace(const char* line);
extern "C" unsigned amiga_avail_kb(void);
extern "C" int amiga_machine_info(char* buf, int len);
extern "C" unsigned amiga_ticks_us(void);
extern "C" unsigned amiga_ticks_bias_us(void);
extern "C" int amiga_env_flag(const char* name);
extern "C" int amiga_getenv_str(const char* name, char* buf, int len);
extern "C" int amiga_trace_enabled(void);
extern "C" int amiga_paint_log_armed;
extern "C" void amiga_malloc_stats(unsigned long* footprint, unsigned long* inUse);
    #define AMIGA_TRACE(msg) amiga_trace(msg)
    // Trace a label with the heap's current in-use and footprint figures, so the deltas between two
    // labels say what a load stage cost. Only while a trace is being written.
    #define AMIGA_TRACE_HEAP(label)                                                                                            \
        do                                                                                                                     \
        {                                                                                                                      \
            if (amiga_trace_enabled())                                                                                         \
            {                                                                                                                  \
                unsigned long _fp = 0, _iu = 0;                                                                                \
                amiga_malloc_stats(&_fp, &_iu);                                                                                \
                char _b[128];                                                                                                  \
                std::snprintf(_b, sizeof(_b), "mem: %s: in use %lu KB, footprint %lu KB", label, _iu / 1024, _fp / 1024);       \
                amiga_trace(_b);                                                                                               \
            }                                                                                                                  \
        } while (0)
    #define AMIGA_TRACE_ONCE(msg)                                                                                              \
        do                                                                                                                     \
        {                                                                                                                      \
            static bool _traced = false;                                                                                       \
            if (!_traced)                                                                                                      \
            {                                                                                                                  \
                _traced = true;                                                                                                \
                amiga_trace(msg);                                                                                              \
            }                                                                                                                  \
        } while (0)
#elif defined(OPENRCT2_TRACE_STDERR)
    #define AMIGA_TRACE_HEAP(label) ((void)0)
    #include <cstdio>
    #define AMIGA_TRACE(msg) std::fprintf(stderr, "TRACE: %s\n", msg)
    #define AMIGA_TRACE_ONCE(msg)                                                                                              \
        do                                                                                                                     \
        {                                                                                                                      \
            static bool _traced = false;                                                                                       \
            if (!_traced)                                                                                                      \
            {                                                                                                                  \
                _traced = true;                                                                                                \
                std::fprintf(stderr, "TRACE: %s\n", msg);                                                                      \
            }                                                                                                                  \
        } while (0)
#else
    #define AMIGA_TRACE(msg) ((void)0)
    #define AMIGA_TRACE_ONCE(msg) ((void)0)
    #define AMIGA_TRACE_HEAP(label) ((void)0)
#endif
