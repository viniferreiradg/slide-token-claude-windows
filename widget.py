"""
Claude Token Widget
Lê automaticamente o arquivo de sessão mais recente do Claude Code
e exibe o uso do contexto em tempo real.
"""

import tkinter as tk
import json
import os
import glob
import pathlib
import ctypes
import ctypes.wintypes

# ── Config ───────────────────────────────────────────────────────────────────
MAX_TOKENS   = 200_000
POLL_MS      = 1_500        # atualiza a cada 1.5s
SESSIONS_DIR = pathlib.Path.home() / ".claude" / "projects"

WINDOW_W = 300
WINDOW_H = 90
BG       = "#1a1714"   # fundo quente escuro, no tom Claude
BAR_BG   = "#2e2926"
FG_MAIN  = "#f0e6d3"   # creme Claude
FG_DIM   = "#5c5248"
FG_TITLE = "#9c8a7a"
COL_GREEN  = "#c8a882"  # areia/creme — contexto folgado
COL_YELLOW = "#d97756"  # coral Claude — atenção
COL_RED    = "#e03e1a"  # vermelho quente — quase no limite
# ─────────────────────────────────────────────────────────────────────────────


def find_latest_session() -> pathlib.Path | None:
    """Retorna o .jsonl mais recentemente modificado em ~/.claude/projects/."""
    files = glob.glob(str(SESSIONS_DIR / "**" / "*.jsonl"), recursive=True)
    if not files:
        return None
    return pathlib.Path(max(files, key=os.path.getmtime))


def read_token_usage(path: pathlib.Path) -> dict:
    """
    Lê a última entrada de assistente do JSONL e retorna o uso de tokens.
    Retorna dict com: input, cache_read, cache_creation, output, total
    """
    last_usage = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "assistant":
                    usage = entry.get("message", {}).get("usage")
                    if usage:
                        last_usage = usage
    except (OSError, PermissionError):
        return {}

    if not last_usage:
        return {}

    inp   = last_usage.get("input_tokens", 0)
    cr    = last_usage.get("cache_read_input_tokens", 0)
    cc    = last_usage.get("cache_creation_input_tokens", 0)
    out   = last_usage.get("output_tokens", 0)
    total = inp + cr + cc + out

    return {"input": inp, "cache_read": cr, "cache_creation": cc,
            "output": out, "total": total}


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
        self._last_path: pathlib.Path | None = None

        self._build_ui()

        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{sw - WINDOW_W - 20}+20")

        self.root.after(50, self._force_taskbar)
        self._poll()   # inicia o loop de leitura

    def _force_taskbar(self):
        """Faz o widget aparecer na taskbar do Windows mesmo sem título nativo."""
        GWL_EXSTYLE    = -20
        WS_EX_APPWINDOW = 0x00040000
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_APPWINDOW)
            # Recicla a janela para o Windows registrar na taskbar
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

        # ── Drag bar ─────────────────────────────────────────────────────────
        drag = tk.Frame(inner, bg=BG, height=22, cursor="fleur")
        drag.pack(fill="x")

        self.lbl_title = tk.Label(drag, text="claude tokens  •  aguardando sessão…",
                                  bg=BG, fg=FG_TITLE, font=("Segoe UI", 7))
        self.lbl_title.pack(side="left", padx=10, pady=4)

        close = tk.Label(drag, text="×", bg=BG, fg=FG_DIM,
                         font=("Segoe UI", 11, "bold"), cursor="hand2")
        close.pack(side="right", padx=8, pady=2)
        close.bind("<Button-1>", lambda e: self.root.destroy())
        close.bind("<Enter>",    lambda e: close.config(fg=COL_RED))
        close.bind("<Leave>",    lambda e: close.config(fg=FG_DIM))

        for w in (drag, self.lbl_title):
            w.bind("<Button-1>",  self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # ── Token label ───────────────────────────────────────────────────────
        self.lbl_tokens = tk.Label(inner, text="— / 200,000  (0%)",
                                   bg=BG, fg=FG_MAIN,
                                   font=("Segoe UI", 10, "bold"))
        self.lbl_tokens.pack(pady=(2, 0))

        # ── Progress bar ──────────────────────────────────────────────────────
        self.canvas = tk.Canvas(inner, bg=BG, height=10,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="x", padx=12, pady=(4, 0))

        # ── Detalhe (cache etc) ───────────────────────────────────────────────
        self.lbl_detail = tk.Label(inner, text="",
                                   bg=BG, fg=FG_DIM, font=("Segoe UI", 7))
        self.lbl_detail.pack(pady=(3, 5))

    # ── Poll ──────────────────────────────────────────────────────────────────

    def _poll(self):
        path = find_latest_session()
        if path:
            usage = read_token_usage(path)
            if usage:
                # Atualiza o título com o slug/nome da sessão
                session_label = path.parent.name[:30] + "…" if len(path.parent.name) > 30 else path.parent.name
                self.lbl_title.config(text=f"claude tokens  •  {session_label}")
                self._update_display(usage)
            else:
                self.lbl_title.config(text="claude tokens  •  sessão vazia")
        else:
            self.lbl_title.config(text="claude tokens  •  nenhuma sessão encontrada")

        self.root.after(POLL_MS, self._poll)

    # ── Display ───────────────────────────────────────────────────────────────

    def _update_display(self, usage: dict):
        total = usage.get("total", 0)
        pct   = min(total / MAX_TOKENS, 1.0)

        if pct < 0.5:
            color = COL_GREEN
        elif pct < 0.8:
            color = COL_YELLOW
        else:
            color = COL_RED

        self.lbl_tokens.config(
            text=f"{total:,} / {MAX_TOKENS:,}  ({pct * 100:.0f}%)",
            fg=color
        )

        cr  = usage.get("cache_read", 0)
        cc  = usage.get("cache_creation", 0)
        out = usage.get("output", 0)
        self.lbl_detail.config(
            text=f"cache lido {cr:,}  •  novo {cc:,}  •  output {out:,}"
        )

        self._draw_bar(pct, color)

    def _draw_bar(self, pct: float, color: str):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or (WINDOW_W - 24)
        h = 10
        r = 5

        self._rounded_rect(0, 0, w, h, r, fill=BAR_BG)

        fill_w = max(0, int(w * pct))
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

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TokenWidget().run()
