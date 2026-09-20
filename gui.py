import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from datetime import datetime
import threading
import time
import sys
import os

# Add the project root so BackEnd/ and Database/ can be imported
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from BackEnd.AutomatedMsg import send_whatsapp_message
from Database.database import db_init, db_all, db_add, db_delete, db_search

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_OK = True
except ImportError:
    TWILIO_OK = False

# ─────────────────────────────────────────────
# PALETTE
# ─────────────────────────────────────────────
BG        = "#0A0F0D"
SURFACE   = "#111A15"
CARD      = "#162019"
BORDER    = "#1E3325"
ACCENT    = "#25D366"
ACCENT_DK = "#128C4E"
TEXT      = "#E8F5EC"
MUTED     = "#5A7A62"
DIM       = "#2A4030"
RED       = "#E05252"
AMBER     = "#D4A843"
BLUE      = "#4A9ECC"

FONT_BODY = "Segoe UI" if sys.platform == "win32" else "Helvetica Neue"
FONT_MONO = "Consolas" if sys.platform == "win32" else "Menlo"


# ─────────────────────────────────────────────
# STYLED ENTRY
# ─────────────────────────────────────────────
class StyledEntry(tk.Frame):
    def __init__(self, master, placeholder="", secret=False, **kw):
        super().__init__(master, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        self._ph = placeholder
        self._secret = secret
        self._visible = not secret
        self.var = tk.StringVar()

        self.entry = tk.Entry(
            self, textvariable=self.var,
            font=(FONT_BODY, 11), bg=SURFACE, fg=MUTED,
            insertbackground=ACCENT, relief="flat", bd=8, **kw
        )
        self.entry.pack(side="left", fill="x", expand=True)

        if secret:
            self._eye = tk.Label(self, text="◎", font=(FONT_BODY, 14),
                                 bg=SURFACE, fg=MUTED, cursor="hand2", padx=8)
            self._eye.pack(side="right")
            self._eye.bind("<Button-1>", self._toggle)
            self.entry.config(show="•")

        self._put_placeholder()
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<FocusIn>",
                        lambda e: self.config(highlightbackground=ACCENT), add="+")
        self.entry.bind("<FocusOut>",
                        lambda e: self.config(highlightbackground=BORDER), add="+")

    def _put_placeholder(self):
        if not self.var.get():
            self.entry.insert(0, self._ph)
            self.entry.config(fg=MUTED)

    def _focus_in(self, _):
        if self.entry.get() == self._ph:
            self.entry.delete(0, "end")
            self.entry.config(fg=TEXT)
            if self._secret:
                self.entry.config(show="•" if not self._visible else "")

    def _focus_out(self, _):
        if not self.entry.get():
            if self._secret:
                self.entry.config(show="")
            self.entry.insert(0, self._ph)
            self.entry.config(fg=MUTED)

    def _toggle(self, _):
        self._visible = not self._visible
        if self.entry.get() != self._ph:
            self.entry.config(show="" if self._visible else "•")
        self._eye.config(fg=ACCENT if self._visible else MUTED,
                         text="◉" if self._visible else "◎")

    def get(self):
        val = self.entry.get().strip()
        return "" if val == self._ph else val

    def set(self, val):
        self.entry.config(fg=TEXT)
        self.entry.delete(0, "end")
        self.entry.insert(0, val)


# ─────────────────────────────────────────────
# PILL BUTTON
# ─────────────────────────────────────────────
class PillBtn(tk.Button):
    def __init__(self, master, text, command, color=ACCENT, fg_color="#000", **kw):
        self._on = color
        self._off = self._dim(color)
        super().__init__(
            master, text=text, command=command,
            font=(FONT_BODY, 11, "bold"),
            bg=color, fg=fg_color,
            activebackground=self._off, activeforeground=fg_color,
            relief="flat", bd=0, cursor="hand2",
            padx=20, pady=10, **kw
        )
        self.bind("<Enter>", lambda e: self.config(bg=self._off) if str(self["state"]) != "disabled" else None)
        self.bind("<Leave>", lambda e: self.config(bg=self._on) if str(self["state"]) != "disabled" else None)

    def _dim(self, hex_color):
        r = max(0, int(hex_color[1:3], 16) - 20)
        g = max(0, int(hex_color[3:5], 16) - 20)
        b = max(0, int(hex_color[5:7], 16) - 20)
        return f"#{r:02x}{g:02x}{b:02x}"

    def disable(self):
        self.config(state="disabled", bg=DIM, fg=MUTED)

    def enable(self):
        self.config(state="normal", bg=self._on)


# ─────────────────────────────────────────────
# CONTACTS MANAGER WINDOW
# ─────────────────────────────────────────────
class ContactsWindow(tk.Toplevel):
    def __init__(self, master, on_select=None):
        super().__init__(master)
        self.title("Contacts")
        self.geometry("480x560")
        self.configure(bg=BG)
        self.resizable(False, True)
        self.on_select = on_select  # callback(name, number)
        self._build()
        self._refresh()

    def _build(self):
        # ── Title
        tk.Label(self, text="📒 Contacts", font=(FONT_BODY, 14, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=20, pady=(18, 6))

        # ── Search bar
        sf = tk.Frame(self, bg=CARD, highlightthickness=1,
                      highlightbackground=BORDER)
        sf.pack(fill="x", padx=20, pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        tk.Entry(sf, textvariable=self.search_var,
                 font=(FONT_BODY, 11), bg=SURFACE, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", bd=8).pack(fill="x")

        # ── Contact list (treeview)
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("C.Treeview",
                        background=SURFACE, fieldbackground=SURFACE,
                        foreground=TEXT, rowheight=32,
                        borderwidth=0, font=(FONT_BODY, 10))
        style.configure("C.Treeview.Heading",
                        background=CARD, foreground=MUTED,
                        font=(FONT_BODY, 9, "bold"), relief="flat")
        style.map("C.Treeview", background=[("selected", ACCENT_DK)],
                  foreground=[("selected", TEXT)])

        frame = tk.Frame(self, bg=SURFACE)
        frame.pack(fill="both", expand=True, padx=20)
        self.tree = ttk.Treeview(frame, columns=("name", "number"),
                                 show="headings", style="C.Treeview",
                                 selectmode="browse")
        self.tree.heading("name", text="Name")
        self.tree.heading("number", text="Phone Number")
        self.tree.column("name", width=180, anchor="w")
        self.tree.column("number", width=180, anchor="w")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double)

        # ── Add new contact
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=10)
        tk.Label(self, text="Add New Contact", font=(FONT_BODY, 10, "bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", padx=20)

        add_row = tk.Frame(self, bg=BG)
        add_row.pack(fill="x", padx=20, pady=6)

        nf = tk.Frame(add_row, bg=CARD, highlightthickness=1,
                      highlightbackground=BORDER)
        nf.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.add_name = tk.Entry(nf, font=(FONT_BODY, 11), bg=SURFACE, fg=TEXT,
                                 insertbackground=ACCENT, relief="flat", bd=6)
        self.add_name.pack(fill="x")

        pf = tk.Frame(add_row, bg=CARD, highlightthickness=1,
                      highlightbackground=BORDER)
        pf.pack(side="left", fill="x", expand=True)
        self.add_num = tk.Entry(pf, font=(FONT_BODY, 11), bg=SURFACE, fg=TEXT,
                                insertbackground=ACCENT, relief="flat", bd=6)
        self.add_num.pack(fill="x")

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=20, pady=(0, 16))
        PillBtn(btn_row, "➕ Add", self._add_contact,
                color=ACCENT, fg_color="#000").pack(side="left", padx=(0, 8))
        PillBtn(btn_row, "🗑 Delete Selected", self._delete_contact,
                color=RED, fg_color="#fff").pack(side="left")
        if self.on_select:
            PillBtn(btn_row, "✔ Use Selected", self._use_selected,
                    color=BLUE, fg_color="#fff").pack(side="right")

    def _refresh(self):
        q = self.search_var.get() if hasattr(self, "search_var") else ""
        rows = db_search(q) if q else db_all()
        self.tree.delete(*self.tree.get_children())
        for cid, name, number in rows:
            self.tree.insert("", "end", iid=str(cid), values=(name, number))

    def _add_contact(self):
        name = self.add_name.get().strip()
        number = self.add_num.get().strip()
        if not name or not number:
            messagebox.showerror("Missing", "Enter both name and number.", parent=self)
            return
        if not number.startswith("+"):
            messagebox.showerror("Format", "Number must start with + and country code.", parent=self)
            return
        db_add(name, number)
        self.add_name.delete(0, "end")
        self.add_num.delete(0, "end")
        self._refresh()

    def _delete_contact(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a contact to delete.", parent=self)
            return
        if messagebox.askyesno("Confirm", "Delete selected contact?", parent=self):
            db_delete(int(sel[0]))
            self._refresh()

    def _use_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a contact first.", parent=self)
            return
        vals = self.tree.item(sel[0])["values"]
        if self.on_select:
            self.on_select(vals[0], vals[1])
        self.destroy()

    def _on_double(self, _):
        if self.on_select:
            self._use_selected()


# ─────────────────────────────────────────────
# SCHEDULED JOB (one row in the queue panel)
# ─────────────────────────────────────────────
class ScheduledJob:
    def __init__(self, job_id, name, number, body, sched, cancel_evt):
        self.job_id = job_id
        self.name = name
        self.number = number
        self.body = body
        self.sched = sched
        self.cancel_evt = cancel_evt
        self.status = "pending"  # pending | sent | failed | cancelled


# ─────────────────────────────────────────────
# APPLICATION
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WhatsApp Scheduler")
        self.geometry("720x980")
        self.minsize(620, 820)
        self.configure(bg=BG)
        db_init()
        self._jobs: list[ScheduledJob] = []
        self._next_id = 1
        self._setup_scroll()
        self._build()

    # ── SCROLLABLE WRAPPER ────────────────────
    def _setup_scroll(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical",
                          command=self._canvas.yview, bg=BG)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self._canvas, bg=BG)
        self._win = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>",
                       lambda e: self._canvas.configure(
                           scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._win, width=e.width))
        self._canvas.bind_all(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ── FULL UI ───────────────────────────────
    def _build(self):
        p = self.body

        # ── Header
        hdr = tk.Frame(p, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(28, 0))
        ic = tk.Canvas(hdr, width=50, height=50, bg=BG, highlightthickness=0)
        ic.create_oval(1, 1, 49, 49, fill=ACCENT, outline="")
        ic.create_text(25, 25, text="✉", font=(FONT_BODY, 20, "bold"), fill="#000")
        ic.pack(side="left")
        txt = tk.Frame(hdr, bg=BG)
        txt.pack(side="left", padx=12)
        tk.Label(txt, text="WhatsApp Scheduler",
                 font=(FONT_BODY, 20, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(txt, text="· Schedule messages · Manage contacts · Multi-queue",
                 font=(FONT_BODY, 10), bg=BG, fg=MUTED).pack(anchor="w")
        # Contacts button top-right
        PillBtn(hdr, "📒 Contacts", self._open_contacts,
                color=DIM, fg_color=TEXT).pack(side="right", padx=(0, 0))

        self._hr()

        if not TWILIO_OK:
            warn = tk.Frame(p, bg="#2A1A0A",
                            highlightthickness=1, highlightbackground=AMBER)
            warn.pack(fill="x", padx=28, pady=(0, 4))
            tk.Label(warn,
                     text="⚠ twilio package not found — run: pip install twilio",
                     font=(FONT_BODY, 10), bg="#2A1A0A", fg=AMBER,
                     pady=8, padx=12).pack(anchor="w")

        # ── Recipient
        self._stitle("👤 Recipient")
        rec = self._card()
        row = tk.Frame(rec, bg=CARD)
        row.pack(fill="x")

        lf = tk.Frame(row, bg=CARD)
        lf.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._lbl(lf, "Name")
        name_row = tk.Frame(lf, bg=CARD)
        name_row.pack(fill="x")
        self.w_name = StyledEntry(name_row, placeholder="e.g. Rahul")
        self.w_name.pack(side="left", fill="x", expand=True, padx=(0, 6))
        PillBtn(name_row, "📒", self._open_contacts,
                color=DIM, fg_color=MUTED).pack(side="left")

        rf = tk.Frame(row, bg=CARD)
        rf.pack(side="left", fill="x", expand=True)
        self._lbl(rf, "Phone Number (with country code)")
        self.w_num = StyledEntry(rf, placeholder="+91XXXXXXXXXX")
        self.w_num.pack(fill="x")

        # ── Message
        self._stitle("💬 Message")
        msg_card = self._card()
        self._lbl(msg_card, "Message Body")
        msg_wrap = tk.Frame(msg_card, bg=CARD,
                            highlightthickness=1, highlightbackground=BORDER)
        msg_wrap.pack(fill="x", pady=(0, 4))
        self.w_msg = scrolledtext.ScrolledText(
            msg_wrap, height=5, wrap="word",
            font=(FONT_BODY, 11), bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=8, undo=True
        )
        self.w_msg.pack(fill="x")
        self.char_var = tk.StringVar(value="0 chars")
        char_lbl = tk.Label(msg_card, textvariable=self.char_var,
                            font=(FONT_MONO, 9), bg=CARD, fg=MUTED)
        char_lbl.pack(anchor="e")

        def _count(_=None):
            n = len(self.w_msg.get("1.0", "end-1c"))
            self.char_var.set(f"{n} / 1600 chars")
            char_lbl.config(fg=RED if n > 1600 else MUTED)

        self.w_msg.bind("<KeyRelease>", _count)

        # ── Schedule
        self._stitle("🕐 Schedule")
        sch = self._card()
        sr = tk.Frame(sch, bg=CARD)
        sr.pack(fill="x")

        dl = tk.Frame(sr, bg=CARD)
        dl.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._lbl(dl, "Date (YYYY-MM-DD)")
        self.w_date = StyledEntry(dl, placeholder="YYYY-MM-DD")
        self.w_date.pack(fill="x")

        dr = tk.Frame(sr, bg=CARD)
        dr.pack(side="left", fill="x", expand=True)
        self._lbl(dr, "Time (HH:MM 24-hour)")
        self.w_time = StyledEntry(dr, placeholder="HH:MM")
        self.w_time.pack(fill="x")

        # ── Action buttons
        self._hr()
        btns = tk.Frame(p, bg=BG)
        btns.pack(fill="x", padx=28, pady=(0, 14))
        self.btn_add = PillBtn(btns, " ➕ Add to Queue ",
                               self._on_add_to_queue, color=ACCENT, fg_color="#000")
        self.btn_add.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_send_all = PillBtn(btns, " ✈ Send All Queued ",
                                    self._on_send_all, color=BLUE, fg_color="#fff")
        self.btn_send_all.pack(side="left", fill="x", expand=True)

        self._hr(pady=(0, 0))

        # ── Message Queue
        self._stitle("📨 Message Queue")
        self.queue_frame = self._card(padx=0, pady=0)
        self._queue_empty_lbl = tk.Label(
            self.queue_frame,
            text="No messages queued yet. Add recipients above.",
            font=(FONT_BODY, 10), bg=CARD, fg=MUTED, pady=14)
        self._queue_empty_lbl.pack()

        # ── Log
        self._hr()
        self._stitle("📋 Activity Log")
        log_card = self._card(padx=0, pady=0)
        self.log = scrolledtext.ScrolledText(
            log_card, height=7, wrap="word", state="disabled",
            font=(FONT_MONO, 10), bg=BG, fg=MUTED,
            insertbackground=MUTED, relief="flat", bd=12
        )
        self.log.pack(fill="both")
        self.log.tag_config("ok", foreground=ACCENT)
        self.log.tag_config("err", foreground=RED)
        self.log.tag_config("info", foreground=AMBER)
        self.log.tag_config("ts", foreground=DIM)

        tk.Label(p, text="· WhatsApp Scheduler",
                 font=(FONT_BODY, 9), bg=BG, fg=DIM).pack(pady=(10, 24))

        self._write_log("Ready — add recipients to the queue, then send all.", "info")

    # ── CONTACTS ─────────────────────────────
    def _open_contacts(self):
        ContactsWindow(self, on_select=self._fill_from_contact)

    def _fill_from_contact(self, name, number):
        self.w_name.set(name)
        self.w_num.set(number)

    # ── QUEUE ─────────────────────────────────
    def _on_add_to_queue(self):
        result = self._validate()
        if result is None:
            return
        name, number, body, sched, delay = result

        job = ScheduledJob(
            job_id=self._next_id,
            name=name, number=number, body=body,
            sched=sched, cancel_evt=threading.Event()
        )
        self._next_id += 1
        self._jobs.append(job)
        self._render_queue()
        self._write_log(
            f"[#{job.job_id}] Queued → {name} ({number}) "
            f"at {sched.strftime('%Y-%m-%d %H:%M')}", "info"
        )

        # Offer to save contact
        self._maybe_save_contact(name, number)

    def _maybe_save_contact(self, name, number):
        existing = [r for r in db_all() if r[2] == number]
        if not existing:
            if messagebox.askyesno("Save Contact?",
                                   f"Save {name} ({number}) to contacts?",
                                   parent=self):
                db_add(name, number)

    def _remove_job(self, job_id):
        job = next((j for j in self._jobs if j.job_id == job_id), None)
        if job:
            job.cancel_evt.set()
            self._jobs = [j for j in self._jobs if j.job_id != job_id]
            self._render_queue()
            self._write_log(f"[#{job_id}] Removed from queue.", "err")

    def _render_queue(self):
        for w in self.queue_frame.winfo_children():
            w.destroy()

        pending = [j for j in self._jobs if j.status in ("pending",)]
        done = [j for j in self._jobs if j.status in ("sent", "failed", "cancelled")]

        if not self._jobs:
            tk.Label(self.queue_frame,
                     text="No messages queued yet. Add recipients above.",
                     font=(FONT_BODY, 10), bg=CARD, fg=MUTED, pady=14).pack()
            return

        for job in pending + done:
            self._render_job_row(job)

    def _render_job_row(self, job: ScheduledJob):
        status_color = {
            "pending": AMBER,
            "sent": ACCENT,
            "failed": RED,
            "cancelled": DIM,
        }.get(job.status, MUTED)

        row = tk.Frame(self.queue_frame, bg=SURFACE,
                       highlightthickness=1, highlightbackground=BORDER)
        row.pack(fill="x", padx=0, pady=2)

        info = tk.Frame(row, bg=SURFACE)
        info.pack(side="left", fill="x", expand=True, padx=12, pady=8)

        top = tk.Frame(info, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text=f"#{job.job_id} {job.name}",
                 font=(FONT_BODY, 11, "bold"), bg=SURFACE, fg=TEXT).pack(side="left")
        tk.Label(top, text=f"  {job.number}",
                 font=(FONT_MONO, 10), bg=SURFACE, fg=MUTED).pack(side="left")

        preview = job.body[:60] + ("…" if len(job.body) > 60 else "")
        tk.Label(info, text=preview,
                 font=(FONT_BODY, 9), bg=SURFACE, fg=MUTED).pack(anchor="w")

        meta = tk.Frame(info, bg=SURFACE)
        meta.pack(fill="x")
        tk.Label(meta, text=f"⏰ {job.sched.strftime('%Y-%m-%d %H:%M')}",
                 font=(FONT_MONO, 9), bg=SURFACE, fg=AMBER).pack(side="left")

        # Countdown label (only for pending)
        if job.status == "pending":
            job._cdown_var = tk.StringVar()
            tk.Label(meta, textvariable=job._cdown_var,
                     font=(FONT_MONO, 9), bg=SURFACE, fg=MUTED).pack(side="left", padx=8)
            self._tick_job(job)

        right = tk.Frame(row, bg=SURFACE)
        right.pack(side="right", padx=10)
        tk.Label(right, text=job.status.upper(),
                 font=(FONT_BODY, 9, "bold"), bg=SURFACE,
                 fg=status_color).pack(anchor="e")
        if job.status == "pending":
            PillBtn(right, "✕", lambda jid=job.job_id: self._remove_job(jid),
                    color=DIM, fg_color=MUTED).pack(anchor="e", pady=(4, 0))

    def _tick_job(self, job: ScheduledJob):
        if job.status != "pending":
            return
        rem = (job.sched - datetime.now()).total_seconds()
        if rem <= 0:
            if hasattr(job, "_cdown_var"):
                job._cdown_var.set("⏳ Sending…")
            return
        h, r = divmod(int(rem), 3600)
        m, s = divmod(r, 60)
        if hasattr(job, "_cdown_var"):
            job._cdown_var.set(f"  {h:02d}h {m:02d}m {s:02d}s")
        self.after(1000, self._tick_job, job)

    # ── SEND ALL ─────────────────────────────
    def _on_send_all(self):
        pending = [j for j in self._jobs if j.status == "pending"]
        if not pending:
            messagebox.showinfo("Empty", "No pending messages in queue.", parent=self)
            return
        if not TWILIO_OK:
            messagebox.showerror("Missing package",
                                 "Run: pip install twilio then restart.",
                                 parent=self)
            return
        self._write_log(f"Starting {len(pending)} scheduled job(s)…", "info")
        for job in pending:
            threading.Thread(
                target=self._worker, args=(job,), daemon=True
            ).start()

    # ── WORKER ───────────────────────────────
    def _worker(self, job: ScheduledJob):
        delay = (job.sched - datetime.now()).total_seconds()
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            remaining = delay - elapsed
            if job.cancel_evt.is_set():
                job.status = "cancelled"
                self.after(0, self._render_queue)
                self.after(0, self._write_log,
                           f"[#{job.job_id}] Cancelled.", "err")
                return
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))

        self.after(0, self._write_log,
                   f"[#{job.job_id}] Connecting to Twilio for {job.name}…", "info")
        try:
            send_whatsapp_message(job.number, job.body)
            job.status = "sent"
            self.after(0, self._render_queue)
            self.after(0, self._write_log,
                       f"[#{job.job_id}] ✅ Delivered to {job.name}!", "ok")
        except Exception as exc:
            job.status = "failed"
            self.after(0, self._render_queue)
            self.after(0, self._write_log,
                       f"[#{job.job_id}] ❌ Twilio error: {exc}", "err")

    # ── VALIDATE ─────────────────────────────
    def _validate(self):
        name = self.w_name.get()
        number = self.w_num.get()
        body = self.w_msg.get("1.0", "end-1c").strip()
        date_s = self.w_date.get()
        time_s = self.w_time.get()

        errors = []
        if not name:
            errors.append("• Recipient name is required.")
        if not number.startswith("+"):
            errors.append("• Phone number must include country code, e.g. +91…")
        if not body:
            errors.append("• Message body is empty.")
        if errors:
            messagebox.showerror("Fix these issues", "\n".join(errors), parent=self)
            return None

        try:
            sched = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Bad date/time",
                                 "Use YYYY-MM-DD for date and HH:MM (24-hr) for time.",
                                 parent=self)
            return None

        delay = (sched - datetime.now()).total_seconds()
        if delay <= 0:
            messagebox.showerror("Past time",
                                 "That time has already passed — pick a future time.",
                                 parent=self)
            return None

        return name, number, body, sched, delay

    # ── HELPERS ───────────────────────────────
    def _hr(self, pady=(12, 12)):
        tk.Frame(self.body, bg=BORDER, height=1).pack(fill="x", padx=28, pady=pady)

    def _stitle(self, t):
        tk.Label(self.body, text=t, font=(FONT_BODY, 11, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=28, pady=(16, 6))

    def _card(self, padx=16, pady=14):
        f = tk.Frame(self.body, bg=CARD, padx=padx, pady=pady,
                     highlightthickness=1, highlightbackground=BORDER)
        f.pack(fill="x", padx=28, pady=(0, 2))
        return f

    def _lbl(self, p, t):
        tk.Label(p, text=t, font=(FONT_BODY, 9), bg=CARD,
                 fg=MUTED).pack(anchor="w", pady=(6, 2))

    def _write_log(self, msg, tag=""):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert("end", f"[{ts}] ", "ts")
        self.log.insert("end", f"{msg}\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    App().mainloop()
