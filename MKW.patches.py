"""MKW: the per-game patches Switch2Recomp applies while it translates this game's code (switchrecomp.py loads <name>.patches.py
from the output folder and calls apply). They are built into the game on the user's PC; this file holds no game code."""


def apply(prog, say):
    """MKW's frame-rate mode, made selectable at run time (runtime option frame_pacing): every thread's
    c->user[6] points at the runtime's current choice (0 = the game's own, 1 = the game's per-frame dynamic mode,
    2 = 60 FPS, 3 = 30 FPS), which the runtime may change while the game runs.
    The frame loop picks each frame's present interval from a mode at [x19+0x210] (0 = from the frame time, 1 or 2
    vblanks; 1 = 60 FPS; 2 = 30 FPS) and advances its clock by that many vblanks a frame. Found by its code, as the
    Eglantine-MKW-DynamicFPS mod (GPL-3.0) finds it: cmp w9,w1; b.ne; ldr w8,[x19,#0x210]; cbnz w8; then within six
    words mov w8,#0x42700000 (60.0f) (1.0.0: main+0x3A9EC8). In dynamic mode the frame time it uses is the next
    ldr xN,[x19,#0x128] (its CPU work only, fast here while the GPU side is the slow part), pointed at [x19,#0xe8]
    (the whole frame) instead."""
    for m in prog.mods:
        if getattr(m, 'name', '') != 'main': continue
        W = m._words; n = len(W); found = []
        for i in range(2, n - 8):
            if W[i] != 0xB9421268 or W[i - 2] != 0x6B01013F or (W[i - 1] & 0xFF00001F) != 0x54000001 or \
               (W[i + 1] & 0xFF00001F) != 0x35000008:
                continue
            if any(W[j] == 0x52A84E08 for j in range(i + 2, i + 8)): found.append(i)
        if len(found) != 1:
            say('Frame-rate mode: not found (%d matches), frame_pacing will do nothing' % len(found)); return
        i = found[0]
        mode = m._t0 + i * 4
        prog.patches[mode] = ('{ u64 o_=*(volatile u64*)c->user[6]; c->x[8]= o_? (u64)(u32)(o_-1) : (u64)(RD32((c->x[19]+528))); }')
        for j in range(i + 1, min(i + 32, n)):
            if (W[j] & 0xFFFFFFE0) == 0xF9409660:
                rt = W[j] & 0x1F
                prog.patches[m._t0 + j * 4] = 'c->x[%d]=(u64)(RD64((c->x[19]+(*(volatile u64*)c->user[6]==1? 232 : 296))));' % rt
                break
        say('Frame-rate mode at main+%X (frame_pacing option)' % (mode - m.base))
