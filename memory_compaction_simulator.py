"""
Memory Compaction Simulator
===========================
A Python/Tkinter port of the HTML Memory Compaction Simulator.

Features:
  - Allocate processes using First Fit / Best Fit / Worst Fit
  - Click a memory block to deallocate that process
  - Animated compaction (shifts used blocks to the left)
  - Process queue (waiting processes auto-placed after compaction)
  - Live stats: Used / Free / Largest Hole / Fragments / Queued
  - Utilisation bar
  - Activity log
  - Timeline charts (Utilisation %, Fragment Count, Largest Hole)
  - Strategy Comparison (runs all 3 strategies on the same random workload)
  - Export plain-text report
  - Adjustable memory size (8–64 blocks)
  - Light / Dark theme toggle

Requirements: Python 3.8+  (tkinter is bundled with most Python installs)
              matplotlib  (pip install matplotlib)

Run: python memory_compaction_simulator.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import random
import time
import datetime
import threading

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ─────────────────────────────────────────────
#  COLOUR PALETTES
# ─────────────────────────────────────────────
PROCESS_COLORS = [
    "#2dd4bf", "#5b8fff", "#c084fc", "#fbbf24",
    "#f87171", "#22d3ee", "#f472b6", "#fb923c",
    "#a3e635", "#e879f9",
]

DARK = dict(
    bg="#080a10", bg2="#0e1118", bg3="#141720", bg4="#1c2030",
    text="#dde2f0", text2="#7c82a0", text3="#474d68",
    green="#2dd4bf", blue="#5b8fff", amber="#fbbf24",
    red="#f87171", purple="#c084fc", cyan="#22d3ee",
    border="#2a2e40",
)
LIGHT = dict(
    bg="#f1f3fa", bg2="#ffffff", bg3="#e8ecf6", bg4="#dde2f0",
    text="#151926", text2="#4a5070", text3="#8890b0",
    green="#0d9488", blue="#3b6ef0", amber="#d97706",
    red="#dc2626", purple="#9333ea", cyan="#0891b2",
    border="#cdd4ea",
)

C = DARK.copy()          # active colour dict (mutated on theme toggle)


def proc_color(pid: int) -> str:
    return PROCESS_COLORS[(pid - 1) % len(PROCESS_COLORS)]


# ─────────────────────────────────────────────
#  CORE LOGIC  (pure Python, no GUI deps)
# ─────────────────────────────────────────────

def get_holes(memory):
    holes = []
    i = 0
    n = len(memory)
    while i < n:
        if memory[i] is None:
            s = i
            while i < n and memory[i] is None:
                i += 1
            holes.append((s, i - s))
        else:
            i += 1
    return holes


def place_into(memory, size, strategy):
    """Return (start, length) of chosen hole, or None."""
    holes = get_holes(memory)
    fits = [(s, l) for s, l in holes if l >= size]
    if not fits:
        return None
    if strategy == "First Fit":
        return fits[0]
    elif strategy == "Best Fit":
        return min(fits, key=lambda x: x[1])
    else:  # Worst Fit
        return max(fits, key=lambda x: x[1])


def compact_memory(memory):
    """Return a new memory list with all processes pushed left."""
    used = [v for v in memory if v is not None]
    return used + [None] * (len(memory) - len(used))


# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────

class MemSimApp(tk.Tk):

    MEM_MIN, MEM_MAX, MEM_DEFAULT = 8, 64, 20

    def __init__(self):
        super().__init__()
        self.title("Memory Compaction Simulator")
        self.geometry("1100x700")
        self.minsize(800, 580)
        self.configure(bg=C["bg"])

        # ── state ──
        self.mem_size = tk.IntVar(value=self.MEM_DEFAULT)
        self.memory: list = [None] * self.MEM_DEFAULT
        self.queue: list = []          # list of dicts {pid, size}
        self.pid = 1
        self.busy = False
        self.paused = False
        self.is_light = False

        # timeline data
        self.tl_util: list = []
        self.tl_frag: list = []
        self.tl_hole: list = []
        self.tl_labels: list = []
        self.op_count = 0

        self._build_ui()
        self._record_timeline()
        self._log("Simulator ready — allocate processes to begin", "system")

    # ──────────────────────────────────────────
    #  UI CONSTRUCTION
    # ──────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_notebook()

    # ── header ──

    def _build_header(self):
        hdr = tk.Frame(self, bg=C["bg2"], pady=8, padx=14)
        hdr.pack(fill="x")

        # logo
        logo = tk.Label(hdr, text="⬛  Memory Compaction Simulator",
                        font=("Helvetica", 14, "bold"),
                        fg=C["blue"], bg=C["bg2"])
        logo.pack(side="left")

        # controls (right side)
        ctrl = tk.Frame(hdr, bg=C["bg2"])
        ctrl.pack(side="right")

        # memory size
        tk.Label(ctrl, text="Memory Size", font=("Helvetica", 8, "bold"),
                 fg=C["text3"], bg=C["bg2"]).grid(row=0, column=0, sticky="w", padx=(0, 2))
        self.mem_slider = tk.Scale(ctrl, from_=self.MEM_MIN, to=self.MEM_MAX,
                                   orient="horizontal", resolution=4,
                                   variable=self.mem_size,
                                   command=self._on_mem_slider,
                                   length=110,
                                   bg=C["bg2"], fg=C["blue"],
                                   troughcolor=C["bg3"],
                                   highlightthickness=0,
                                   showvalue=False, bd=0)
        self.mem_slider.grid(row=1, column=0, padx=(0, 4))
        self.mem_size_lbl = tk.Label(ctrl, text="20", font=("Courier", 11, "bold"),
                                     fg=C["blue"], bg=C["bg2"], width=3)
        self.mem_size_lbl.grid(row=1, column=1, padx=(0, 10))

        # process size
        tk.Label(ctrl, text="Process Size", font=("Helvetica", 8, "bold"),
                 fg=C["text3"], bg=C["bg2"]).grid(row=0, column=2, sticky="w")
        self.size_var = tk.IntVar(value=3)
        self.size_spin = tk.Spinbox(ctrl, from_=1, to=64, textvariable=self.size_var,
                                    width=5, font=("Courier", 11),
                                    bg=C["bg3"], fg=C["text"],
                                    buttonbackground=C["bg4"],
                                    highlightthickness=0, relief="flat")
        self.size_spin.grid(row=1, column=2, padx=(0, 10))

        # strategy
        tk.Label(ctrl, text="Strategy", font=("Helvetica", 8, "bold"),
                 fg=C["text3"], bg=C["bg2"]).grid(row=0, column=3, sticky="w")
        self.strategy_var = tk.StringVar(value="First Fit")
        strat_menu = ttk.Combobox(ctrl, textvariable=self.strategy_var,
                                  values=["First Fit", "Best Fit", "Worst Fit"],
                                  state="readonly", width=12,
                                  font=("Courier", 11))
        strat_menu.grid(row=1, column=3, padx=(0, 12))

        # action buttons
        self.btn_alloc = self._hbtn(ctrl, "＋ Allocate", C["green"], self._allocate, 4)
        self.btn_compact = self._hbtn(ctrl, "⇆ Compact", C["blue"], self._compact, 5)
        self.btn_pause = self._hbtn(ctrl, "⏸ Pause", C["cyan"], self._toggle_pause, 6)
        self._hbtn(ctrl, "↓ Export", C["amber"], self._export_report, 7)
        self._hbtn(ctrl, "↺ Reset", C["red"], self._reset_all, 8)
        self._hbtn(ctrl, "☀ Theme", C["text2"], self._toggle_theme, 9)

    def _hbtn(self, parent, text, color, cmd, col):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=C["bg3"], fg=color,
                      font=("Helvetica", 10, "bold"),
                      relief="flat", padx=8, pady=4, cursor="hand2",
                      activebackground=C["bg4"], activeforeground=color)
        b.grid(row=1, column=col, padx=3)
        return b

    # ── notebook / tabs ──

    def _build_notebook(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["bg2"], foreground=C["text2"],
                        padding=[12, 6], font=("Helvetica", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", C["bg"])],
                  foreground=[("selected", C["blue"])])

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_sim_tab()
        self._build_timeline_tab()
        self._build_compare_tab()

        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    # ── simulator tab ──

    def _build_sim_tab(self):
        self.sim_frame = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.sim_frame, text="  Simulator  ")

        # stats row
        stats_row = tk.Frame(self.sim_frame, bg=C["bg"])
        stats_row.pack(fill="x", padx=16, pady=(10, 4))
        self.stat_used_lbl = self._stat_card(stats_row, "Used", "0", C["green"], 0)
        self.stat_free_lbl = self._stat_card(stats_row, "Free", "20", C["blue"], 1)
        self.stat_hole_lbl = self._stat_card(stats_row, "Largest Hole", "20", C["text"], 2)
        self.stat_frag_lbl = self._stat_card(stats_row, "Fragments", "0", C["amber"], 3)
        self.stat_queue_lbl = self._stat_card(stats_row, "Queued", "0", C["red"], 4)

        for c in range(5):
            stats_row.columnconfigure(c, weight=1)

        # memory grid header
        mem_hdr = tk.Frame(self.sim_frame, bg=C["bg"])
        mem_hdr.pack(fill="x", padx=16, pady=(6, 2))
        self.mem_title_lbl = tk.Label(mem_hdr, text="Main Memory — 20 blocks",
                                      font=("Helvetica", 9, "bold"),
                                      fg=C["text3"], bg=C["bg"])
        self.mem_title_lbl.pack(side="left")
        tk.Label(mem_hdr, text="Click any block to deallocate",
                 font=("Courier", 9), fg=C["text3"], bg=C["bg"]).pack(side="right")

        # memory block grid canvas
        self.grid_frame = tk.Frame(self.sim_frame, bg=C["bg"])
        self.grid_frame.pack(fill="x", padx=16, pady=(0, 4))
        self.cell_buttons: list[tk.Button] = []
        self._build_mem_cells()

        # utilisation bar
        util_wrap = tk.Frame(self.sim_frame, bg=C["bg"])
        util_wrap.pack(fill="x", padx=16, pady=(2, 6))
        util_meta = tk.Frame(util_wrap, bg=C["bg"])
        util_meta.pack(fill="x")
        tk.Label(util_meta, text="Utilisation", font=("Courier", 9),
                 fg=C["text3"], bg=C["bg"]).pack(side="left")
        self.util_pct_lbl = tk.Label(util_meta, text="0%",
                                     font=("Courier", 9, "bold"),
                                     fg=C["blue"], bg=C["bg"])
        self.util_pct_lbl.pack(side="right")
        self.util_canvas = tk.Canvas(util_wrap, height=6, bg=C["bg4"],
                                     highlightthickness=0)
        self.util_canvas.pack(fill="x", pady=(3, 0))
        self.util_bar_id = self.util_canvas.create_rectangle(
            0, 0, 0, 6, fill=C["blue"], outline="")

        # legend
        legend_frame = tk.Frame(self.sim_frame, bg=C["bg"])
        legend_frame.pack(fill="x", padx=16, pady=(0, 4))
        self.legend_frame = legend_frame

        # queue
        q_frame = tk.Frame(self.sim_frame, bg=C["bg2"], padx=14, pady=8)
        q_frame.pack(fill="x", padx=0)
        tk.Label(q_frame, text="PROCESS QUEUE",
                 font=("Helvetica", 8, "bold"), fg=C["text3"], bg=C["bg2"]).pack(anchor="w")
        self.queue_inner = tk.Frame(q_frame, bg=C["bg2"])
        self.queue_inner.pack(fill="x", pady=(4, 0))

        # log
        log_frame = tk.Frame(self.sim_frame, bg=C["bg"])
        log_frame.pack(fill="both", expand=True)
        log_hdr = tk.Frame(log_frame, bg=C["bg2"], padx=14, pady=6)
        log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="ACTIVITY LOG",
                 font=("Helvetica", 8, "bold"), fg=C["text3"], bg=C["bg2"]).pack(side="left")
        tk.Button(log_hdr, text="clear", command=self._clear_log,
                  bg=C["bg2"], fg=C["text3"], relief="flat",
                  font=("Courier", 9), cursor="hand2").pack(side="right")

        log_body = tk.Frame(log_frame, bg=C["bg"])
        log_body.pack(fill="both", expand=True, padx=14, pady=6)
        self.log_text = tk.Text(log_body, font=("Courier", 10),
                                bg=C["bg"], fg=C["text"],
                                relief="flat", wrap="word",
                                state="disabled", height=6)
        scrollbar = ttk.Scrollbar(log_body, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        # tag colours
        self.log_text.tag_configure("alloc",  foreground=C["green"])
        self.log_text.tag_configure("dealloc", foreground=C["red"])
        self.log_text.tag_configure("compact", foreground=C["blue"])
        self.log_text.tag_configure("queue",  foreground=C["amber"])
        self.log_text.tag_configure("system", foreground=C["text3"])
        self.log_text.tag_configure("export", foreground=C["cyan"])

    def _stat_card(self, parent, label, value, color, col):
        frame = tk.Frame(parent, bg=C["bg2"], padx=12, pady=10)
        frame.grid(row=0, column=col, sticky="nsew", padx=4, pady=2)
        tk.Label(frame, text=label.upper(), font=("Helvetica", 7, "bold"),
                 fg=C["text3"], bg=C["bg2"]).pack(anchor="w")
        lbl = tk.Label(frame, text=value, font=("Courier", 22, "bold"),
                       fg=color, bg=C["bg2"])
        lbl.pack(anchor="w")
        return lbl

    def _build_mem_cells(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.cell_buttons = []
        n = len(self.memory)
        for i in range(n):
            btn = tk.Button(self.grid_frame, text="", width=3, height=2,
                            relief="flat", cursor="hand2",
                            font=("Courier", 8, "bold"),
                            command=lambda idx=i: self._deallocate(idx))
            btn.grid(row=0, column=i, padx=1, pady=2, sticky="nsew")
            self.grid_frame.columnconfigure(i, weight=1)
            self.cell_buttons.append(btn)
        self._refresh_cells()

    # ── timeline tab ──

    def _build_timeline_tab(self):
        self.tl_frame = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.tl_frame, text="  Timeline Chart  ")

        if not HAS_MPL:
            tk.Label(self.tl_frame,
                     text="Install matplotlib to view charts:\n  pip install matplotlib",
                     font=("Helvetica", 13), fg=C["amber"], bg=C["bg"]).pack(expand=True)
            return

        self.fig, (self.ax_util, self.ax_frag, self.ax_hole) = plt.subplots(
            3, 1, figsize=(8, 5), facecolor=C["bg"])
        self.fig.tight_layout(pad=2.5)
        self._style_axes()

        self.tl_canvas = FigureCanvasTkAgg(self.fig, master=self.tl_frame)
        self.tl_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def _style_axes(self):
        if not HAS_MPL:
            return
        cfg = [
            (self.ax_util, "Memory Utilisation %", C["blue"]),
            (self.ax_frag, "Fragment Count",        C["amber"]),
            (self.ax_hole, "Largest Hole (blocks)", C["green"]),
        ]
        for ax, title, color in cfg:
            ax.set_facecolor(C["bg2"])
            ax.tick_params(colors=C["text3"], labelsize=8)
            ax.set_title(title, color=C["text2"], fontsize=9, pad=4)
            ax.spines[:].set_color(C["border"])
            ax.title_color = color   # custom attr for draw

    def _draw_charts(self):
        if not HAS_MPL or not self.tl_labels:
            return
        cfg = [
            (self.ax_util, self.tl_util,  C["blue"],  (0, 100)),
            (self.ax_frag, self.tl_frag,  C["amber"], None),
            (self.ax_hole, self.tl_hole,  C["green"], (0, len(self.memory))),
        ]
        for ax, data, color, ylim in cfg:
            ax.clear()
            ax.set_facecolor(C["bg2"])
            ax.tick_params(colors=C["text3"], labelsize=8)
            ax.spines[:].set_color(C["border"])
            if ylim:
                ax.set_ylim(*ylim)
            ax.plot(self.tl_labels, data, color=color, linewidth=1.8)
            ax.fill_between(self.tl_labels, data, alpha=0.15, color=color)
        self.fig.tight_layout(pad=2.5)
        self.tl_canvas.draw_idle()

    # ── compare tab ──

    def _build_compare_tab(self):
        self.cmp_frame = tk.Frame(self.nb, bg=C["bg"])
        self.nb.add(self.cmp_frame, text="  Strategy Comparison  ")

        top = tk.Frame(self.cmp_frame, bg=C["bg2"], padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="How many random processes?",
                 font=("Helvetica", 10), fg=C["text2"], bg=C["bg2"]).pack(side="left")
        self.cmp_count_var = tk.IntVar(value=8)
        tk.Spinbox(top, from_=1, to=30, textvariable=self.cmp_count_var,
                   width=5, font=("Courier", 11),
                   bg=C["bg3"], fg=C["text"],
                   highlightthickness=0, relief="flat").pack(side="left", padx=8)
        self.cmp_status_lbl = tk.Label(top, text="",
                                       font=("Courier", 10), fg=C["cyan"], bg=C["bg2"])
        self.cmp_status_lbl.pack(side="right", padx=8)
        tk.Button(top, text="▶ Run Comparison", command=self._run_compare,
                  bg=C["purple"], fg="#fff", font=("Helvetica", 10, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left")

        # info bar
        info = tk.Frame(self.cmp_frame, bg=C["bg2"], padx=14, pady=6)
        info.pack(fill="x")
        self.cmp_seq_lbl = tk.Label(info, text="",
                                    font=("Courier", 9), fg=C["text2"], bg=C["bg2"],
                                    wraplength=900, justify="left")
        self.cmp_seq_lbl.pack(anchor="w")

        # three columns
        cols_frame = tk.Frame(self.cmp_frame, bg=C["bg"])
        cols_frame.pack(fill="both", expand=True, padx=10, pady=8)
        strats = [
            ("First Fit",  C["blue"],   "FF"),
            ("Best Fit",   C["green"],  "BF"),
            ("Worst Fit",  C["amber"],  "WF"),
        ]
        self.cmp_panels: dict = {}
        for col, (name, color, key) in enumerate(strats):
            card = tk.Frame(cols_frame, bg=C["bg2"],
                            relief="flat", bd=1)
            card.grid(row=0, column=col, sticky="nsew", padx=5)
            cols_frame.columnconfigure(col, weight=1)
            cols_frame.rowconfigure(0, weight=1)

            title_lbl = tk.Label(card, text=name.upper(),
                                 font=("Helvetica", 10, "bold"),
                                 fg=color, bg=C["bg2"], pady=6)
            title_lbl.pack(fill="x")

            # mini memory grid
            grid_f = tk.Frame(card, bg=C["bg2"])
            grid_f.pack(fill="x", padx=8, pady=(0, 4))

            stats_lbl = tk.Label(card, text="", font=("Courier", 10),
                                 fg=C["text2"], bg=C["bg2"],
                                 justify="left", padx=8, pady=4)
            stats_lbl.pack(fill="x")

            holes_lbl = tk.Label(card, text="", font=("Courier", 9),
                                 fg=C["text3"], bg=C["bg2"],
                                 justify="left", padx=8, pady=2,
                                 wraplength=260)
            holes_lbl.pack(fill="x")

            self.cmp_panels[key] = dict(
                card=card, title=title_lbl, grid=grid_f,
                stats=stats_lbl, holes=holes_lbl,
                name=name, color=color
            )

    # ──────────────────────────────────────────
    #  CORE OPERATIONS
    # ──────────────────────────────────────────

    def _allocate(self):
        if self.busy or self.paused:
            return
        try:
            size = int(self.size_var.get())
        except Exception:
            size = 0
        if size < 1 or size > len(self.memory):
            self._flash("Invalid size!", C["red"])
            return
        p = {"pid": self.pid, "size": size}
        chosen = place_into(self.memory, size, self.strategy_var.get())
        if chosen is None:
            self.queue.append(p)
            self._log(f"P{self.pid} queued — no hole large enough (size {size})", "queue")
        else:
            start, _ = chosen
            for i in range(size):
                self.memory[start + i] = self.pid
            self._log(
                f"P{self.pid} allocated — {size} block(s) via {self.strategy_var.get()}", "alloc")
        self.pid += 1
        self._record_timeline()
        self._refresh()

    def _deallocate(self, idx: int):
        if self.memory[idx] is None or self.busy or self.paused:
            return
        p = self.memory[idx]
        for i in range(len(self.memory)):
            if self.memory[i] == p:
                self.memory[i] = None
        self._log(f"P{p} deallocated — blocks freed", "dealloc")
        self._try_queue()
        self._record_timeline()
        self._refresh()

    def _compact(self):
        if self.busy or self.paused:
            return
        self.busy = True
        self.btn_alloc.configure(state="disabled")
        self.btn_compact.configure(state="disabled")
        self._log("Compaction started — consolidating holes…", "compact")
        threading.Thread(target=self._compact_animate, daemon=True).start()

    def _compact_animate(self):
        target = compact_memory(self.memory)
        n = len(self.memory)
        for step in range(n + 1):
            for i in range(step):
                if i < n:
                    self.memory[i] = target[i]
            self.after(0, self._refresh)
            time.sleep(0.05)
        for i in range(n):
            self.memory[i] = target[i]
        self.after(0, self._compact_done)

    def _compact_done(self):
        self._log("Compaction complete", "compact")
        self._try_queue()
        self._record_timeline()
        self._refresh()
        self.busy = False
        self.btn_alloc.configure(state="normal")
        self.btn_compact.configure(state="normal")

    def _try_queue(self):
        remaining = []
        for p in self.queue:
            chosen = place_into(self.memory, p["size"], self.strategy_var.get())
            if chosen is not None:
                start, _ = chosen
                for i in range(p["size"]):
                    self.memory[start + i] = p["pid"]
                self._log(f"P{p['pid']} moved from queue — placed in memory", "alloc")
            else:
                remaining.append(p)
        self.queue = remaining

    def _toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.btn_pause.configure(text="▶ Resume")
            self._log("Simulation paused", "system")
        else:
            self.btn_pause.configure(text="⏸ Pause")
            self._log("Simulation resumed", "system")

    def _reset_all(self):
        if not messagebox.askyesno("Reset", "Reset all memory and queue?"):
            return
        n = self.mem_size.get()
        self.memory = [None] * n
        self.queue = []
        self.pid = 1
        self.busy = False
        self.paused = False
        self.tl_util = []
        self.tl_frag = []
        self.tl_hole = []
        self.tl_labels = []
        self.op_count = 0
        self.btn_pause.configure(text="⏸ Pause")
        self.btn_alloc.configure(state="normal")
        self.btn_compact.configure(state="normal")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log("System reset", "system")
        self._record_timeline()
        self._refresh()

    def _on_mem_slider(self, *_):
        val = self.mem_size.get()
        self.memory = [None] * val
        self.queue = []
        self.pid = 1
        self.busy = False
        self.tl_util = []
        self.tl_frag = []
        self.tl_hole = []
        self.tl_labels = []
        self.op_count = 0
        self.mem_size_lbl.configure(text=str(val))
        self.mem_title_lbl.configure(text=f"Main Memory — {val} blocks")
        self._log(f"Memory resized to {val} blocks", "system")
        self._build_mem_cells()
        self._record_timeline()
        self._refresh()

    # ──────────────────────────────────────────
    #  RENDERING / REFRESH
    # ──────────────────────────────────────────

    def _refresh(self):
        self._refresh_cells()
        self._update_stats()
        self._render_queue()
        self._render_legend()

    def _refresh_cells(self):
        for i, btn in enumerate(self.cell_buttons):
            if i >= len(self.memory):
                break
            pid = self.memory[i]
            if pid is None:
                btn.configure(bg=C["bg3"], fg=C["text3"],
                              text=str(i), activebackground=C["bg4"])
            else:
                color = proc_color(pid)
                btn.configure(bg=color, fg="#fff",
                              text=f"P{pid}", activebackground=color)

    def _update_stats(self):
        n = len(self.memory)
        used = sum(1 for v in self.memory if v is not None)
        free = n - used
        holes = get_holes(self.memory)
        max_hole = max((l for _, l in holes), default=0)
        frags = len(holes)

        self.stat_used_lbl.configure(text=str(used))
        self.stat_free_lbl.configure(text=str(free))
        self.stat_hole_lbl.configure(text=str(max_hole))
        self.stat_frag_lbl.configure(text=str(frags))
        self.stat_queue_lbl.configure(text=str(len(self.queue)))

        pct = round(used / n * 100) if n else 0
        self.util_pct_lbl.configure(text=f"{pct}%")

        # bar
        w = self.util_canvas.winfo_width()
        fill_w = int(w * pct / 100)
        self.util_canvas.coords(self.util_bar_id, 0, 0, fill_w, 6)

    def _render_queue(self):
        for w in self.queue_inner.winfo_children():
            w.destroy()
        if not self.queue:
            tk.Label(self.queue_inner, text="No processes waiting",
                     font=("Courier", 10), fg=C["text3"], bg=C["bg2"]).pack(side="left")
            return
        for p in self.queue:
            color = proc_color(p["pid"])
            tk.Label(self.queue_inner,
                     text=f"P{p['pid']} ({p['size']})",
                     font=("Courier", 10, "bold"),
                     fg="#fff", bg=color,
                     padx=8, pady=2, relief="flat").pack(side="left", padx=3)

    def _render_legend(self):
        for w in self.legend_frame.winfo_children():
            w.destroy()
        pids = sorted(set(v for v in self.memory if v is not None))
        if not pids:
            tk.Label(self.legend_frame, text="No processes loaded",
                     font=("Courier", 9), fg=C["text3"], bg=C["bg"]).pack(side="left")
            return
        for p in pids:
            sz = sum(1 for v in self.memory if v == p)
            color = proc_color(p)
            f = tk.Frame(self.legend_frame, bg=C["bg"])
            f.pack(side="left", padx=6, pady=2)
            tk.Frame(f, bg=color, width=10, height=10).pack(side="left", padx=(0, 4))
            tk.Label(f, text=f"P{p} · {sz}blk",
                     font=("Courier", 9), fg=C["text2"], bg=C["bg"]).pack(side="left")

    # ──────────────────────────────────────────
    #  LOG
    # ──────────────────────────────────────────

    def _log(self, msg: str, kind: str = "system"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{ts}  ", "system")
        self.log_text.insert("end", msg + "\n", kind)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._log("Log cleared", "system")

    # ──────────────────────────────────────────
    #  TIMELINE
    # ──────────────────────────────────────────

    def _record_timeline(self):
        n = len(self.memory)
        used = sum(1 for v in self.memory if v is not None)
        holes = get_holes(self.memory)
        max_hole = max((l for _, l in holes), default=0)
        self.tl_util.append(round(used / n * 100) if n else 0)
        self.tl_frag.append(len(holes))
        self.tl_hole.append(max_hole)
        self.tl_labels.append(self.op_count)
        self.op_count += 1
        # keep last 80
        if len(self.tl_util) > 80:
            self.tl_util.pop(0)
            self.tl_frag.pop(0)
            self.tl_hole.pop(0)
            self.tl_labels.pop(0)

    def _on_tab_change(self, _event=None):
        tab = self.nb.tab(self.nb.select(), "text").strip()
        if "Timeline" in tab and HAS_MPL:
            self._draw_charts()

    # ──────────────────────────────────────────
    #  STRATEGY COMPARISON
    # ──────────────────────────────────────────

    def _run_compare(self):
        count = self.cmp_count_var.get()
        n = len(self.memory)
        sizes = [random.randint(1, max(1, n // 5)) for _ in range(count)]

        seq_str = "Processes: " + "  ".join(f"P{i+1}·{s}blk" for i, s in enumerate(sizes))
        self.cmp_seq_lbl.configure(text=seq_str)

        strats = [
            ("First Fit", "FF"),
            ("Best Fit",  "BF"),
            ("Worst Fit", "WF"),
        ]
        results = []
        for name, key in strats:
            mem = [None] * n
            placed, queued = 0, 0
            log_lines = []
            local_pid = 1
            for size in sizes:
                chosen = place_into(mem, size, name)
                if chosen is not None:
                    start, _ = chosen
                    for i in range(size):
                        mem[start + i] = local_pid
                    log_lines.append(
                        f"✓ P{local_pid}({size}blk)→[{start}–{start+size-1}]")
                    placed += 1
                else:
                    log_lines.append(f"✗ P{local_pid}({size}blk) no hole")
                    queued += 1
                local_pid += 1

            holes = get_holes(mem)
            max_hole = max((l for _, l in holes), default=0)

            # draw mini grid
            panel = self.cmp_panels[key]
            grid_f = panel["grid"]
            for w in grid_f.winfo_children():
                w.destroy()
            cols = min(n, 20)
            for idx, v in enumerate(mem):
                row_i, col_i = divmod(idx, cols)
                color = proc_color(v) if v else C["bg3"]
                tk.Frame(grid_f, bg=color,
                         width=14, height=14,
                         relief="flat").grid(row=row_i, column=col_i,
                                             padx=1, pady=1)

            panel["stats"].configure(
                text=(f"✓ Placed : {placed}\n"
                      f"✗ Queued : {queued}\n"
                      f"Holes    : {len(holes)}\n"
                      f"Max hole : {max_hole}\n\n"
                      + "\n".join(log_lines)))

            hole_txt = (", ".join(f"[{s}–{s+l-1}] ({l})" for s, l in holes)
                        if holes else "No holes — fully packed!")
            panel["holes"].configure(text=f"Free holes: {hole_txt}")

            results.append(dict(key=key, placed=placed, frags=len(holes),
                                max_hole=max_hole))

        # winner: most placed → fewest frags → largest remaining hole
        best = max(results, key=lambda r: (r["placed"], -r["frags"], r["max_hole"]))
        for r in results:
            p = self.cmp_panels[r["key"]]
            name_map = {"FF": "First Fit", "BF": "Best Fit", "WF": "Worst Fit"}
            highlight = C["green"] if r["key"] == best["key"] else C["border"]
            p["card"].configure(highlightbackground=highlight,
                                highlightthickness=2 if r["key"] == best["key"] else 0)

        winner_name = {"FF": "First Fit", "BF": "Best Fit", "WF": "Worst Fit"}[best["key"]]
        self.cmp_status_lbl.configure(
            text=f"🏆 {winner_name} wins — {best['placed']}/{count} placed, {best['frags']} holes")

    # ──────────────────────────────────────────
    #  EXPORT
    # ──────────────────────────────────────────

    def _export_report(self):
        n = len(self.memory)
        used = sum(1 for v in self.memory if v is not None)
        holes = get_holes(self.memory)
        max_hole = max((l for _, l in holes), default=0)
        pids = sorted(set(v for v in self.memory if v is not None))

        lines = [
            "╔═══════════════════════════════════════╗",
            "║   Memory Compaction Simulator Report  ║",
            "╚═══════════════════════════════════════╝",
            f"Generated : {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Memory    : {n} blocks",
            "",
            "── Memory State ──",
            f"Used blocks  : {used}",
            f"Free blocks  : {n - used}",
            f"Utilisation  : {round(used/n*100) if n else 0}%",
            f"Fragments    : {len(holes)}",
            f"Largest hole : {max_hole}",
            f"Queued       : {len(self.queue)}",
            "",
            "── Processes ──",
        ]
        for p in pids:
            blocks = [i for i, v in enumerate(self.memory) if v == p]
            lines.append(f"P{p}: {blocks}")
        lines += ["", "── Holes ──"]
        for s, l in holes:
            lines.append(f"start={s}, size={l}")
        lines += ["", "── Queue ──"]
        for p in self.queue:
            lines.append(f"P{p['pid']} (size {p['size']})")
        lines += ["", "── Activity Log ──"]
        log_content = self.log_text.get("1.0", "end").strip()
        lines.append(log_content)

        report = "\n".join(lines)
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"memsim_report_{int(time.time())}.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            self._log(f"Report exported → {path}", "export")
            self._flash("Report saved!", C["cyan"])

    # ──────────────────────────────────────────
    #  THEME
    # ──────────────────────────────────────────

    def _toggle_theme(self):
        self.is_light = not self.is_light
        new_c = LIGHT if self.is_light else DARK
        C.update(new_c)
        # lightweight rebuild approach: just restart
        self._log("Theme changed — restart the app for full effect.", "system")
        # For a real full re-theme we would iterate all widgets; for simplicity
        # we update the most visible elements.
        self.configure(bg=C["bg"])

    # ──────────────────────────────────────────
    #  UTILS
    # ──────────────────────────────────────────

    def _flash(self, msg: str, color: str):
        """Show a transient status message."""
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        x = self.winfo_x() + self.winfo_width() - 260
        y = self.winfo_y() + self.winfo_height() - 70
        win.geometry(f"240x40+{x}+{y}")
        win.configure(bg=C["bg2"])
        tk.Label(win, text=msg, font=("Helvetica", 11, "bold"),
                 fg=color, bg=C["bg2"]).pack(expand=True)
        self.after(2000, win.destroy)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = MemSimApp()
    app.mainloop()
