"""
Claude Token Widget
Recebe o % de uso do plano via extensão Chrome (claude.ai)
e exibe em tempo real com as cores do Claude.
"""

import tkinter as tk
import json
import threading
import pathlib
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Config ───────────────────────────────────────────────────────────────────
SERVER_PORT = 9847

WINDOW_W = 300
WINDOW_H = 90
BG       = "#1a1714"
BAR_BG   = "#2e2926"
FG_MAIN  = "#f0e6d3"
FG_DIM   = "#5c5248"
FG_TITLE = "#9c8a7a"
COL_LOW    = "#c8a882"   # 0–50%
COL_MID    = "#d97756"   # 50–80%
COL_HIGH   = "#e03e1a"   # 80–100%
# ─────────────────────────────────────────────────────────────────────────────

# Estado compartilhado entre o servidor HTTP e a UI
_state = {"pct": None, "resetIn": None}
_state_lock = threading.Lock()


class UsageHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/usage":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body)
                with _state_lock:
                    _state["pct"]     = data.get("pct")
                    _state["resetIn"] = data.get("resetIn")
            except Exception:
                pass
        self.send_response(204)
        self.end_headers()

    def do_OPTIONS(self):
        # CORS para o fetch da extensão
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass   # silencia logs no terminal


def start_server():
    server = HTTPServer(("localhost", SERVER_PORT), UsageHandler)
    server.serve_forever()


class TokenWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Claude Tokens")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.93)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()

        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{sw - WINDOW_W - 20}+20")

        self.root.after(50, self._force_taskbar)
        self.root.after(500, self._poll)

    def _force_taskbar(self):
        import ctypes
        GWL_EXSTYLE     = -20
        WS_EX_APPWINDOW = 0x00040000
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_APPWINDOW)
            self.root.wm_withdraw()
            self.root.after(10, self.root.wm_deiconify)
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self.root, bg="#30363d", padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=BG)
        inner.pack(fill="both", expand=True)

        # Drag bar
        drag = tk.Frame(inner, bg=BG, height=22, cursor="fleur")
        drag.pack(fill="x")

        self.lbl_title = tk.Label(drag, text="claude  •  aguardando extensão…",
                                  bg=BG, fg=FG_TITLE, font=("Segoe UI", 7))
        self.lbl_title.pack(side="left", padx=10, pady=4)

        close = tk.Label(drag, text="×", bg=BG, fg=FG_DIM,
                         font=("Segoe UI", 11, "bold"), cursor="hand2")
        close.pack(side="right", padx=8, pady=2)
        close.bind("<Button-1>", lambda e: self.root.destroy())
        close.bind("<Enter>",    lambda e: close.config(fg=COL_HIGH))
        close.bind("<Leave>",    lambda e: close.config(fg=FG_DIM))

        for w in (drag, self.lbl_title):
            w.bind("<Button-1>",  self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # % label
        self.lbl_pct = tk.Label(inner, text="—%  usado",
                                bg=BG, fg=FG_MAIN,
                                font=("Segoe UI", 18, "bold"))
        self.lbl_pct.pack(pady=(4, 0))

        # Progress bar
        self.canvas = tk.Canvas(inner, bg=BG, height=10,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="x", padx=12, pady=(4, 0))

        # Reset label
        self.lbl_reset = tk.Label(inner, text="",
                                  bg=BG, fg=FG_DIM, font=("Segoe UI", 7))
        self.lbl_reset.pack(pady=(3, 5))

    # ── Poll ──────────────────────────────────────────────────────────────────

    def _poll(self):
        with _state_lock:
            pct      = _state["pct"]
            reset_in = _state["resetIn"]

        if pct is not None:
            self._update_display(pct, reset_in)
        else:
            self._draw_bar(0, COL_LOW)   # barra vazia enquanto aguarda

        self.root.after(1000, self._poll)

    # ── Display ───────────────────────────────────────────────────────────────

    def _update_display(self, pct: int, reset_in: str | None):
        ratio = pct / 100

        if ratio < 0.5:
            color = COL_LOW
        elif ratio < 0.8:
            color = COL_MID
        else:
            color = COL_HIGH

        self.lbl_title.config(text="claude  •  plano Pro")
        self.lbl_pct.config(text=f"{pct}%  usado", fg=color)
        self.lbl_reset.config(
            text=f"reseta em {reset_in}" if reset_in else ""
        )
        self._draw_bar(ratio, color)

    def _draw_bar(self, ratio: float, color: str):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or (WINDOW_W - 24)
        h = 10
        r = 5

        self._rounded_rect(0, 0, w, h, r, fill=BAR_BG)
        fill_w = max(0, int(w * ratio))
        if fill_w > r:
            self._rounded_rect(0, 0, fill_w, h, r, fill=color)
        elif fill_w > 0:
            self.canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1+r, y1,  x2-r, y1,
            x2,   y1,  x2,   y1+r,
            x2,   y2-r, x2,  y2,
            x2-r, y2,  x1+r, y2,
            x1,   y2,  x1,   y2-r,
            x1,   y1+r, x1,  y1,
        ]
        self.canvas.create_polygon(pts, smooth=True, outline="", **kw)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Sobe o servidor HTTP em thread separada (não bloqueia a UI)
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    TokenWidget().run()
