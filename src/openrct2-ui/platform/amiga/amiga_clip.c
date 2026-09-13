/* See amiga_clip.h. Plain clipboard.device I/O, no iffparse.library. */
#ifdef __amigaos__
    #include "amiga_clip.h"

    #include <devices/clipboard.h>
    #include <exec/memory.h>
    #include <proto/exec.h>
    #include <string.h>

    #define ID_FORM 0x464F524DUL
    #define ID_FTXT 0x46545854UL
    #define ID_CHR 0x43485220UL

static struct IOClipReq* clip_open(struct MsgPort** port)
{
    struct IOClipReq* req;
    *port = CreateMsgPort();
    if (*port == NULL)
        return NULL;
    req = (struct IOClipReq*)CreateIORequest(*port, sizeof(struct IOClipReq));
    if (req == NULL)
    {
        DeleteMsgPort(*port);
        *port = NULL;
        return NULL;
    }
    if (OpenDevice((STRPTR) "clipboard.device", 0, (struct IORequest*)req, 0) != 0)
    {
        DeleteIORequest((struct IORequest*)req);
        DeleteMsgPort(*port);
        *port = NULL;
        return NULL;
    }
    return req;
}

static void clip_close(struct IOClipReq* req, struct MsgPort* port)
{
    CloseDevice((struct IORequest*)req);
    DeleteIORequest((struct IORequest*)req);
    DeleteMsgPort(port);
}

static void put32(unsigned char* p, unsigned long v)
{
    p[0] = (unsigned char)(v >> 24);
    p[1] = (unsigned char)(v >> 16);
    p[2] = (unsigned char)(v >> 8);
    p[3] = (unsigned char)v;
}

static unsigned long get32(const unsigned char* p)
{
    return ((unsigned long)p[0] << 24) | ((unsigned long)p[1] << 16) | ((unsigned long)p[2] << 8) | p[3];
}

static int clip_io(struct IOClipReq* req, UWORD cmd, void* data, long len, long offset)
{
    req->io_Command = cmd;
    req->io_Data = (STRPTR)data;
    req->io_Length = len;
    req->io_Offset = offset;
    DoIO((struct IORequest*)req);
    return req->io_Error == 0;
}

int amiga_clip_write(const char* text, int len)
{
    struct MsgPort* port;
    struct IOClipReq* req = clip_open(&port);
    unsigned char* buf;
    long padded, total;
    int ok;
    if (req == NULL || len < 0)
        return 0;
    padded = (len + 1) & ~1L;
    total = 12 + 8 + padded; /* FORM len FTXT + CHR len data */
    buf = (unsigned char*)AllocMem(total, MEMF_ANY | MEMF_CLEAR);
    if (buf == NULL)
    {
        clip_close(req, port);
        return 0;
    }
    put32(buf, ID_FORM);
    put32(buf + 4, (unsigned long)(total - 8));
    put32(buf + 8, ID_FTXT);
    put32(buf + 12, ID_CHR);
    put32(buf + 16, (unsigned long)len);
    memcpy(buf + 20, text, (size_t)len);
    req->io_ClipID = 0;
    ok = clip_io(req, CMD_WRITE, buf, total, 0);
    if (ok)
    {
        req->io_Command = CMD_UPDATE;
        DoIO((struct IORequest*)req);
        ok = req->io_Error == 0;
    }
    FreeMem(buf, total);
    clip_close(req, port);
    return ok;
}

int amiga_clip_read(char* buf, int size)
{
    struct MsgPort* port;
    struct IOClipReq* req = clip_open(&port);
    unsigned char hdr[12];
    unsigned char chunk[8];
    long offset = 12, got = 0;
    unsigned char sink[256];
    if (req == NULL || buf == NULL || size <= 0)
        return 0;
    buf[0] = 0;
    req->io_ClipID = 0;
    if (!clip_io(req, CMD_READ, hdr, 12, 0) || req->io_Actual < 12 || get32(hdr) != ID_FORM || get32(hdr + 8) != ID_FTXT)
    {
        /* not an FTXT clip (or empty): drain and close */
        while (clip_io(req, CMD_READ, sink, sizeof sink, req->io_Offset) && req->io_Actual > 0)
            ;
        clip_close(req, port);
        return 0;
    }
    /* walk the chunks; the first CHR is the text */
    while (clip_io(req, CMD_READ, chunk, 8, offset) && req->io_Actual == 8)
    {
        unsigned long id = get32(chunk), len = get32(chunk + 4);
        offset += 8;
        if (id == ID_CHR)
        {
            long want = (long)len < size - 1 ? (long)len : size - 1;
            if (want > 0 && clip_io(req, CMD_READ, buf, want, offset))
                got = req->io_Actual;
            buf[got] = 0;
            break;
        }
        offset += (long)((len + 1) & ~1UL);
    }
    /* reading must continue until the device reports no more data, or the clip stays locked */
    while (clip_io(req, CMD_READ, sink, sizeof sink, req->io_Offset) && req->io_Actual > 0)
        ;
    clip_close(req, port);
    return (int)got;
}
#endif
