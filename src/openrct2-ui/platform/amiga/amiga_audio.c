/* See amiga_audio.h.
 *
 * Playback runs in its own process. The game's main loop only fills a ring buffer (amiga_audio_pump); the audio
 * process takes 2048-frame slices out of it and double-buffers them to ahi.device the way the AHI autodocs show:
 * send the next request linked (ahir_Link) to the one in flight, *then* WaitIO() the one in flight. The link
 * target is therefore always a pending request. The earlier main-loop design reaped finished requests and then
 * linked to "the last one sent"; when that request finished in between, the link pointed at a replied request,
 * which AHI leaves undefined -- Paula under Emu68 froze the whole machine within seconds (testers' reports on
 * test16..test19). When the ring runs dry (park loads, slow frames) the process plays silence and counts an
 * underrun; nothing waits on the main loop. */
#ifdef __amigaos__
    #include "amiga_audio.h"

    #include <devices/ahi.h>
    #include <dos/dostags.h>
    #include <exec/memory.h>
    #include <proto/dos.h>
    #include <proto/exec.h>
    #include <string.h>

    #define REQ_FRAMES 2048                    /* 93 ms per request at 22050 Hz */
    #define RING_FRAMES 16384                  /* 743 ms */
    #define RING_BYTES (RING_FRAMES * 4)

/* shared between the main loop and the audio process */
static volatile unsigned char* g_ring = NULL;
static volatile unsigned long g_head = 0; /* bytes written by the main loop */
static volatile unsigned long g_tail = 0; /* bytes consumed by the audio process */
static volatile int g_quit = 0;
static volatile int g_status = 0; /* 0 starting, 1 running, -1 failed to open AHI, 2 finished */
static volatile unsigned g_written = 0, g_underruns = 0;
static volatile int g_fed = 0; /* set by the pump; an underrun counts once per stall after real audio was queued */
static struct Task* g_mainTask = NULL;
static LONG g_sigReady = -1, g_sigDone = -1;
static int g_freq = 22050;
static int g_open = 0;
static unsigned g_lastPumpMs = 0;
static unsigned long g_targetBytes = REQ_FRAMES * 4 * 2;
extern unsigned amiga_ticks_ms(void);

int amiga_audio_available(void)
{
    struct MsgPort* port = CreateMsgPort();
    struct AHIRequest* req;
    int ok = 0;
    if (port == NULL)
        return 0;
    req = (struct AHIRequest*)CreateIORequest(port, sizeof(struct AHIRequest));
    if (req != NULL)
    {
        req->ahir_Version = 4;
        if (OpenDevice((STRPTR)AHINAME, AHI_DEFAULT_UNIT, (struct IORequest*)req, 0) == 0)
        {
            CloseDevice((struct IORequest*)req);
            ok = 1;
        }
        DeleteIORequest((struct IORequest*)req);
    }
    DeleteMsgPort(port);
    return ok;
}

/* Take up to `bytes` from the ring into dst, padding with silence. Returns the bytes that came from the ring. */
static unsigned long ring_take(unsigned char* dst, unsigned long bytes)
{
    unsigned long avail = g_head - g_tail, n = avail < bytes ? avail : bytes, pos = g_tail % RING_BYTES;
    unsigned long first = n < RING_BYTES - pos ? n : RING_BYTES - pos;
    if (first > 0)
        memcpy(dst, (const void*)(g_ring + pos), first);
    if (n > first)
        memcpy(dst + first, (const void*)g_ring, n - first);
    if (n < bytes)
        memset(dst + n, 0, bytes - n);
    g_tail += n;
    return n;
}

static void audio_process(void)
{
    struct MsgPort* port = CreateMsgPort();
    struct AHIRequest* req[2] = { NULL, NULL };
    struct AHIRequest* last = NULL;
    unsigned char* buf[2] = { NULL, NULL };
    int i, opened = 0, cur = 0;
    if (port != NULL)
    {
        req[0] = (struct AHIRequest*)CreateIORequest(port, sizeof(struct AHIRequest));
        req[1] = (struct AHIRequest*)CreateIORequest(port, sizeof(struct AHIRequest));
        buf[0] = (unsigned char*)AllocMem(REQ_FRAMES * 4, MEMF_PUBLIC | MEMF_CLEAR);
        buf[1] = (unsigned char*)AllocMem(REQ_FRAMES * 4, MEMF_PUBLIC | MEMF_CLEAR);
    }
    if (req[0] != NULL && req[1] != NULL && buf[0] != NULL && buf[1] != NULL)
    {
        req[0]->ahir_Version = 4;
        if (OpenDevice((STRPTR)AHINAME, AHI_DEFAULT_UNIT, (struct IORequest*)req[0], 0) == 0)
        {
            opened = 1;
            memcpy(req[1], req[0], sizeof(struct AHIRequest)); /* same device/unit; the port is shared */
        }
    }
    g_status = opened ? 1 : -1;
    Signal(g_mainTask, 1L << g_sigReady);
    if (opened)
    {
        while (!g_quit)
        {
            struct AHIRequest* r = req[cur];
            if (ring_take(buf[cur], REQ_FRAMES * 4) < REQ_FRAMES * 4)
            {
                if (g_fed)
                    g_underruns++;
                g_fed = 0;
            }
            r->ahir_Std.io_Message.mn_Node.ln_Pri = 0;
            r->ahir_Std.io_Command = CMD_WRITE;
            r->ahir_Std.io_Data = buf[cur];
            r->ahir_Std.io_Length = REQ_FRAMES * 4;
            r->ahir_Std.io_Offset = 0;
            r->ahir_Type = AHIST_S16S;
            r->ahir_Frequency = g_freq;
            r->ahir_Volume = 0x10000;  /* 1.0 */
            r->ahir_Position = 0x8000; /* centre */
            r->ahir_Link = last;       /* gapless after the request still playing */
            SendIO((struct IORequest*)r);
            g_written++;
            if (last != NULL)
                WaitIO((struct IORequest*)last); /* the link target stays pending until here */
            last = r;
            cur ^= 1;
        }
        if (last != NULL)
        {
            AbortIO((struct IORequest*)last);
            WaitIO((struct IORequest*)last);
        }
        CloseDevice((struct IORequest*)req[0]);
    }
    for (i = 0; i < 2; i++)
    {
        if (req[i] != NULL)
            DeleteIORequest((struct IORequest*)req[i]);
        if (buf[i] != NULL)
            FreeMem(buf[i], REQ_FRAMES * 4);
    }
    if (port != NULL)
        DeleteMsgPort(port);
    g_status = 2;
    Signal(g_mainTask, 1L << g_sigDone);
}

int amiga_audio_open(int freq, int frames, int numBuffers)
{
    (void)frames;
    (void)numBuffers;
    amiga_audio_close();
    g_freq = freq > 0 ? freq : 22050;
    g_ring = (volatile unsigned char*)AllocMem(RING_BYTES, MEMF_PUBLIC | MEMF_CLEAR);
    if (g_ring == NULL)
        return 0;
    g_head = g_tail = 0;
    g_quit = 0;
    g_status = 0;
    g_written = g_underruns = 0;
    g_fed = 0;
    g_lastPumpMs = 0;
    g_targetBytes = REQ_FRAMES * 4 * 2;
    g_mainTask = FindTask(NULL);
    g_sigReady = AllocSignal(-1);
    g_sigDone = AllocSignal(-1);
    if (g_sigReady < 0 || g_sigDone < 0)
    {
        amiga_audio_close();
        return 0;
    }
    if (CreateNewProcTags(
            NP_Entry, (ULONG)audio_process, NP_Name, (ULONG) "OpenRCT2 audio", NP_Priority, 2, NP_StackSize, 32768, TAG_DONE)
        == NULL)
    {
        amiga_audio_close();
        return 0;
    }
    Wait(1L << g_sigReady);
    if (g_status != 1)
    {
        Wait(1L << g_sigDone); /* the process cleans up and ends on its own */
        amiga_audio_close();
        return 0;
    }
    g_open = 1;
    return 1;
}

int amiga_audio_pump(amiga_audio_fill_fn fill, void* user)
{
    int filled = 0;
    unsigned now;
    if (!g_open)
        return 0;
    /* keep enough queued to bridge the interval between two pumps, with half a request of slack */
    now = amiga_ticks_ms();
    if (g_lastPumpMs != 0)
    {
        unsigned long want = ((unsigned long)(now - g_lastPumpMs) * (unsigned long)g_freq / 1000UL) * 4UL * 3UL / 2UL
            + REQ_FRAMES * 4UL;
        if (want > RING_BYTES - REQ_FRAMES * 4UL)
            want = RING_BYTES - REQ_FRAMES * 4UL;
        if (want > g_targetBytes)
            g_targetBytes = want;
        else if (want < g_targetBytes / 2)
            g_targetBytes -= g_targetBytes / 8;
        if (g_targetBytes < REQ_FRAMES * 4UL * 2UL)
            g_targetBytes = REQ_FRAMES * 4UL * 2UL;
    }
    g_lastPumpMs = now;
    while (g_head - g_tail < g_targetBytes && RING_BYTES - (g_head - g_tail) >= REQ_FRAMES * 4UL)
    {
        unsigned long pos = g_head % RING_BYTES, bytes = REQ_FRAMES * 4UL;
        if (RING_BYTES - pos >= bytes)
        {
            fill(user, (unsigned char*)(g_ring + pos), (int)bytes);
        }
        else
        {
            static unsigned char tmp[REQ_FRAMES * 4];
            unsigned long first = RING_BYTES - pos;
            fill(user, tmp, (int)bytes);
            memcpy((void*)(g_ring + pos), tmp, first);
            memcpy((void*)g_ring, tmp + first, bytes - first);
        }
        g_head += bytes;
        filled++;
    }
    if (filled > 0)
        g_fed = 1;
    return filled;
}

void amiga_audio_close(void)
{
    if (g_status == 1)
    {
        g_quit = 1;
        Wait(1L << g_sigDone);
    }
    g_open = 0;
    g_status = 0;
    if (g_sigReady >= 0)
    {
        FreeSignal(g_sigReady);
        g_sigReady = -1;
    }
    if (g_sigDone >= 0)
    {
        FreeSignal(g_sigDone);
        g_sigDone = -1;
    }
    if (g_ring != NULL)
    {
        FreeMem((void*)g_ring, RING_BYTES);
        g_ring = NULL;
    }
}

int amiga_audio_getenv(const char* name, char* buf, int len)
{
    return GetVar((STRPTR)name, (STRPTR)buf, len, 0) > 0 ? 1 : 0;
}

void amiga_audio_stats(unsigned* written, unsigned* underruns)
{
    if (written)
        *written = g_written;
    if (underruns)
        *underruns = g_underruns;
}
#endif
