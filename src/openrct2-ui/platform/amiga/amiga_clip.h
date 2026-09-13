#pragma once
/* Text clipboard via clipboard.device unit 0, IFF FTXT (the standard Amiga text clip format). Latin-1 in and out. */
#ifdef __cplusplus
extern "C" {
#endif
/* Writes text (Latin-1, len bytes) as an FTXT clip. Returns 1 on success. */
int amiga_clip_write(const char* text, int len);
/* Reads the current FTXT clip into buf (up to size-1 bytes, NUL-terminated). Returns the byte count, 0 if none. */
int amiga_clip_read(char* buf, int size);
#ifdef __cplusplus
}
#endif
