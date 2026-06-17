import asyncio, io, sys, threading, time, tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFilter

try:
    import winsdk.windows.media.control as wmc
    import winsdk.windows.storage.streams as wss
    WINSDK_OK = True
except ImportError:
    WINSDK_OK = False

W, H        = 340, 100
THUMB_SIZE  = 80
PADX, PADY  = 12, 10

BG_DARK  = (18, 18, 28)
TEXT_C   = "#e0e4f6"
DIM_C    = "#6b7194"
ACCENT_C = "#89b4fa"

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True).start()
time.sleep(0.05)

def sync(coro, timeout=5):
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout)

async def _read_thumbnail(ref) -> bytes | None:
    try:
        stream = await ref.open_read_async()
        size   = stream.size
        reader = wss.DataReader(stream.get_input_stream_at(0))
        await reader.load_async(size)
        buf = bytearray(size)
        reader.read_bytes(buf)
        return bytes(buf)
    except Exception:
        return None

async def fetch_now_playing() -> dict | None:
    try:
        mgr = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
    except Exception:
        return None
    sessions = []
    cur = mgr.get_current_session()
    if cur: sessions.append(cur)
    try:
        for s in mgr.get_sessions():
            if s not in sessions: sessions.append(s)
    except Exception:
        pass
    PS = wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus
    for session in sessions:
        try:
            props = await session.try_get_media_properties_async()
            if not props: continue
            title  = (props.title       or "").strip()
            artist = (props.artist      or "").strip()
            album  = (props.album_title or "").strip()
            if not title or title in ("Amazon Music", "YouTube Music"): continue
            pb   = session.get_playback_info()
            caps = pb.controls
            is_playing = pb.playback_status == PS.PLAYING
            thumb = None
            if props.thumbnail:
                thumb = await _read_thumbnail(props.thumbnail)
            return {
                "title": title, "artist": artist, "album": album,
                "is_playing": is_playing,
                "thumb": thumb,
                "can_prev": caps.is_previous_enabled,
                "can_next": caps.is_next_enabled,
                "can_pp":   caps.is_play_pause_toggle_enabled,
                "session":  session,
            }
        except Exception:
            continue
    return None

async def send_cmd(session, cmd: str):
    try:
        if cmd == "play_pause": await session.try_toggle_play_pause_async()
        elif cmd == "next":     await session.try_skip_next_async()
        elif cmd == "prev":     await session.try_skip_previous_async()
    except Exception:
        pass

def make_skip_icon(size: int, direction: str, fg, dim=False) -> Image.Image:
    rs = size * 2
    img = Image.new("RGBA", (rs, rs), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = rs
    alpha = 130 if dim else 220
    c = (*fg, alpha)
    if direction == "next":
        bx = s * 3 // 16
        d.rectangle([bx, s*3//10, bx + max(2, s//14), s*7//10], fill=c)
        tx0 = bx + max(2, s//14) + s//16
        d.polygon([(tx0, s*2//10), (tx0, s*8//10), (s*13//16, s//2)], fill=c)
    else:
        bar_w = max(2, s//14)
        bx = s * 13 // 16        
        d.rectangle([bx - bar_w, s*3//10, bx, s*7//10], fill=c)
        tx1 = bx - bar_w - s//16  
        d.polygon([(tx1, s*2//10), (tx1, s*8//10), (s*3//16, s//2)], fill=c)
    return img.resize((size, size), Image.LANCZOS)

def make_pp_icon(size: int, is_play: bool, fg) -> Image.Image:
    rs = size * 2
    img = Image.new("RGBA", (rs, rs), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = rs
    d.ellipse([0, 0, s-1, s-1], fill=(255, 255, 255, 28))
    c = (*fg, 240)
    if is_play:
        d.polygon([(s*5//16, s*3//16), (s*5//16, s*13//16), (s*13//16, s//2)], fill=c)
    else:
        bw = max(3, s // 9)
        gap = s // 9
        cx = s // 2
        d.rounded_rectangle([cx - gap//2 - bw, s*3//16, cx - gap//2, s*13//16],
                             radius=bw//2, fill=c)
        d.rounded_rectangle([cx + gap//2, s*3//16, cx + gap//2 + bw, s*13//16],
                             radius=bw//2, fill=c)
    return img.resize((size, size), Image.LANCZOS)

def make_bg(thumb_bytes, w, h) -> Image.Image:
    if thumb_bytes:
        try:
            img = Image.open(io.BytesIO(thumb_bytes)).convert("RGB")
            img = img.resize((w, h), Image.LANCZOS)
            img = img.filter(ImageFilter.GaussianBlur(radius=30))
            dark = Image.new("RGB", (w, h), (8, 8, 16))
            img  = Image.blend(img, dark, 0.62)
            return img.convert("RGBA")
        except Exception:
            pass
    return Image.new("RGBA", (w, h), (*BG_DARK, 255))

def rounded_thumb_img(data, size) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA") if data else _placeholder(size)
        img = img.resize((size, size), Image.LANCZOS)
    except Exception:
        img = _placeholder(size)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size-1, size-1], radius=10, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    return out

def _placeholder(size) -> Image.Image:
    img = Image.new("RGBA", (size, size), (32, 32, 50, 255))
    d   = ImageDraw.Draw(img)
    c   = (137, 180, 250, 160)
    cx  = size // 2
    d.ellipse([cx-14, cx, cx-4, cx+10],  fill=c)
    d.ellipse([cx+2,  cx, cx+12, cx+10], fill=c)
    d.rectangle([cx-4, cx-22, cx-2, cx+3],   fill=c)
    d.rectangle([cx+12, cx-22, cx+14, cx+3], fill=c)
    d.rectangle([cx-4, cx-22, cx+14, cx-20], fill=c)
    return img

def set_rounded_corners(hwnd):
    try:
        import ctypes
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int))
    except Exception:
        pass

class NowPlayingWidget:
    POLL_MS = 2000

    TX = PADX + THUMB_SIZE + 12
    TW = W - (PADX + THUMB_SIZE + 12) - PADX

    BTN_Y  = 62
    BTN_H  = H - BTN_Y - 6
    _BCOL  = W - (PADX + THUMB_SIZE + 12) - PADX
    BTN_CX = [TX + _BCOL*1//6,
               TX + _BCOL*3//6,
               TX + _BCOL*5//6]
    BTN_HIT = 28

    SKIP_SZ = 22
    PP_SZ   = 30

    def __init__(self):
        self.root = tk.Tk()

        self._session     = None
        self._pinned      = True
        self._drag_x = self._drag_y = 0
        self._thumb_bytes = None
        self._thumb_pil   = None
        self._bg_pil      = make_bg(None, W, H)
        self._is_playing  = False

        FG  = (210, 218, 248)
        DIM = (90, 95, 120)
        self._icons = {
            "prev":     make_skip_icon(self.SKIP_SZ, "prev", FG),
            "prev_dim": make_skip_icon(self.SKIP_SZ, "prev", DIM, dim=True),
            "next":     make_skip_icon(self.SKIP_SZ, "next", FG),
            "next_dim": make_skip_icon(self.SKIP_SZ, "next", DIM, dim=True),
            "play":     make_pp_icon(self.PP_SZ, True,  FG),
            "pause":    make_pp_icon(self.PP_SZ, False, FG),
        }
        self._cur_pp_key   = "pause"
        self._cur_prev_key = "prev"
        self._cur_next_key = "next"
        self._frame_photo  = None

        self._setup_window()
        self._build_canvas()
        self._render_frame()
        self._schedule_refresh()
        self.root.mainloop()

    def _setup_window(self):
        r = self.root
        r.title("Now Playing")
        r.geometry(f"{W}x{H}+60+60")
        r.resizable(False, False)
        r.overrideredirect(True)
        r.wm_attributes("-topmost", True)
        r.wm_attributes("-alpha", 0.96)
        r.configure(bg="#000000")
        r.update_idletasks()
        set_rounded_corners(r.winfo_id())

    def _build_canvas(self):
        self.cv = tk.Canvas(self.root, width=W, height=H,
                            highlightthickness=0, bd=0, bg="#000000")
        self.cv.pack()

        self._id_bg = self.cv.create_image(0, 0, anchor="nw")

        self._id_title = self.cv.create_text(
            self.TX, PADY + 2, anchor="nw", fill=TEXT_C,
            font=("Segoe UI Semibold", 10), width=self.TW)
        self._id_artist = self.cv.create_text(
            self.TX, PADY + 18, anchor="nw", fill=DIM_C,
            font=("Segoe UI", 8), width=self.TW)
        self._id_album = self.cv.create_text(
            self.TX, PADY + 32, anchor="nw", fill=DIM_C,
            font=("Segoe UI", 7), width=self.TW)

        self._id_close = self.cv.create_text(
            W - 10, 8, anchor="ne", text="✕",
            fill=DIM_C, font=("Segoe UI", 9))
        self._id_pin = self.cv.create_text(
            W - 24, 9, anchor="ne", text="●",
            fill=ACCENT_C, font=("Segoe UI", 7))

        self.cv.bind("<ButtonPress-1>", self._on_click)
        self.cv.bind("<B1-Motion>",     self._drag_move)

        self.cv.tag_bind(self._id_close, "<Enter>",
                         lambda e: [self.cv.itemconfig(self._id_close, fill=TEXT_C),
                                    self.cv.config(cursor="hand2")])
        self.cv.tag_bind(self._id_close, "<Leave>",
                         lambda e: [self.cv.itemconfig(self._id_close, fill=DIM_C),
                                    self.cv.config(cursor="")])
        self.cv.tag_bind(self._id_close, "<Button-1>", lambda e: self.root.destroy())
        self.cv.tag_bind(self._id_pin, "<Button-1>", self._toggle_pin)

        SZ = self.BTN_HIT
        for cx, handler, attr in [
            (self.BTN_CX[0], self._prev,       "_hit_prev"),
            (self.BTN_CX[1], self._play_pause, "_hit_pp"),
            (self.BTN_CX[2], self._next,       "_hit_next"),
        ]:
            rid = self.cv.create_rectangle(
                cx - SZ//2, self.BTN_Y,
                cx + SZ//2, self.BTN_Y + self.BTN_H,
                fill="", outline="")
            self.cv.tag_bind(rid, "<Button-1>", lambda e, h=handler: h())
            self.cv.tag_bind(rid, "<Enter>", lambda e: self.cv.config(cursor="hand2"))
            self.cv.tag_bind(rid, "<Leave>", lambda e: self.cv.config(cursor=""))
            setattr(self, attr, rid)

        self.cv.bind("<Button-3>", self._ctx_menu)

    def _render_frame(self):
        frame = self._bg_pil.copy().convert("RGBA")

        if self._thumb_pil:
            ty = (H - THUMB_SIZE) // 2
            frame.paste(self._thumb_pil, (PADX, ty), self._thumb_pil)

        btn_cy = self.BTN_Y + self.BTN_H // 2
        for cx, key, isz in [
            (self.BTN_CX[0], self._cur_prev_key, self.SKIP_SZ),
            (self.BTN_CX[1], self._cur_pp_key,   self.PP_SZ),
            (self.BTN_CX[2], self._cur_next_key, self.SKIP_SZ),
        ]:
            icon = self._icons[key]
            frame.paste(icon, (cx - isz//2, btn_cy - isz//2), icon)

        photo = ImageTk.PhotoImage(frame)
        self._frame_photo = photo
        self.cv.itemconfig(self._id_bg, image=photo)

    def _update(self, info):
        if info is None:
            self.cv.itemconfig(self._id_title,  text="Nothing playing")
            self.cv.itemconfig(self._id_artist, text="Start something in your browser")
            self.cv.itemconfig(self._id_album,  text="")
            self._is_playing   = False
            self._cur_pp_key   = "play"
            self._render_frame()
            return

        self._session    = info["session"]
        self._is_playing = info["is_playing"]

        def trunc(s, n): return s if len(s) <= n else s[:n-1] + "…"
        self.cv.itemconfig(self._id_title,  text=trunc(info["title"],  36))
        self.cv.itemconfig(self._id_artist, text=trunc(info["artist"], 36))
        self.cv.itemconfig(self._id_album,  text=trunc(info["album"],  36))

        self._cur_pp_key   = "pause" if info["is_playing"] else "play"
        self._cur_prev_key = "prev"  if info["can_prev"]   else "prev_dim"
        self._cur_next_key = "next"  if info["can_next"]   else "next_dim"

        if info["thumb"] != self._thumb_bytes or self._thumb_pil is None:
            self._thumb_bytes = info["thumb"]
            self._bg_pil      = make_bg(self._thumb_bytes, W, H)
            self._thumb_pil   = rounded_thumb_img(self._thumb_bytes, THUMB_SIZE)

        self._render_frame()

    def _on_click(self, e):
        self._drag_x = e.x_root - self.root.winfo_x()
        self._drag_y = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _ctx_menu(self, e):
        m = tk.Menu(self.root, tearoff=0, bg="#1e1e2e", fg=TEXT_C,
                    activebackground=ACCENT_C, activeforeground="#1e1e2e",
                    font=("Segoe UI", 9))
        m.add_command(label=f"Always on top {'✓' if self._pinned else ''}",
                      command=self._toggle_pin)
        m.add_separator()
        m.add_command(label="Quit", command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def _toggle_pin(self, *_):
        self._pinned = not self._pinned
        self.root.wm_attributes("-topmost", self._pinned)
        self.cv.itemconfig(self._id_pin, fill=ACCENT_C if self._pinned else DIM_C)

    def _send(self, cmd):
        if self._session:
            threading.Thread(
                target=lambda: sync(send_cmd(self._session, cmd)),
                daemon=True).start()

    def _play_pause(self): self._send("play_pause")
    def _next(self):       self._send("next")
    def _prev(self):       self._send("prev")

    def _schedule_refresh(self):
        if not WINSDK_OK:
            self.cv.itemconfig(self._id_title,  text="⚠ pip install winsdk")
            self.cv.itemconfig(self._id_artist, text="")
            return
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        try:
            info = sync(fetch_now_playing(), timeout=5)
        except Exception:
            info = None
        self.root.after(0, self._update, info)
        self.root.after(self.POLL_MS, self._schedule_refresh)

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Windows only."); sys.exit(1)
    NowPlayingWidget()
