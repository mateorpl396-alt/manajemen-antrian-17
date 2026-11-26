"""Aplikasi Manajemen Antrian - Python 3 + ttkbootstrap + MySQL (tampilan v2)."""
import csv
import os
import sys
from datetime import date, datetime
from tkinter import BooleanVar, StringVar, filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

import database as db
from panels import BackupPanel, DashboardPanel, LaporanPanel

# ------------------------------------------------------------ konstanta
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
TEMA = ["flatly", "cosmo", "litera", "minty", "morph", "darkly", "superhero"]
FONT = "Segoe UI"
CENTER_KEYS = {"nomor_antrian", "tanggal", "status", "id_loket", "id_petugas",
               "waktu_ambil", "waktu_panggil", "waktu_selesai"}
ALL_TREES = []  # daftar semua Treeview (untuk pewarnaan status)


# ---------------------------------------------------------------- helper
def fmt(v):
    """Ubah nilai database menjadi teks yang enak dibaca."""
    if v is None:
        return "-"
    if isinstance(v, datetime):
        return v.strftime("%H:%M:%S")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    return v


def fill_tree(tree, rows, keys, tag_key=None):
    """Isi Treeview. Jika tag_key diberikan, baris diberi warna sesuai nilainya."""
    tree.delete(*tree.get_children())
    for r in rows:
        tags = (r.get(tag_key),) if tag_key else ()
        tree.insert("", END, values=[fmt(r.get(k)) for k in keys], tags=tags)


def make_tree(parent, columns, height=8):
    """columns: list of (key, judul, lebar). Mengembalikan frame + Treeview."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns],
                        show="headings", height=height, bootstyle=PRIMARY)
    for key, judul, lebar in columns:
        tree.heading(key, text=judul)
        tree.column(key, width=lebar, anchor=CENTER if key in CENTER_KEYS else W)
    sb = ttk.Scrollbar(frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    sb.pack(side=RIGHT, fill=Y)
    ALL_TREES.append(tree)
    return frame, tree


# ---------------------------------------------------------- panel CRUD
class CrudPanel(ttk.Labelframe):
    """Panel CRUD generik: form + tombol + Treeview."""

    def __init__(self, master, title, columns, fields, list_fn, add_fn,
                 update_fn, delete_fn, on_change=None):
        super().__init__(master, text=f" {title} ", padding=15)
        self.columns, self.fields = columns, fields
        self.list_fn, self.add_fn = list_fn, add_fn
        self.update_fn, self.delete_fn = update_fn, delete_fn
        self.on_change = on_change
        self.id_key = columns[0][0]
        self.rows = {}
        self.vars = {}

        form = ttk.Frame(self)
        form.pack(fill=X)
        for i, (key, label, kind, opts) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky=W, pady=4)
            var = StringVar()
            self.vars[key] = var
            if kind == "combo":
                w = ttk.Combobox(form, textvariable=var, values=opts,
                                 state="readonly", width=24)
                var.set(opts[0])
            else:
                w = ttk.Entry(form, textvariable=var, width=27,
                              show="*" if kind == "password" else "")
            w.grid(row=i, column=1, padx=10, pady=4, sticky=W)

        btns = ttk.Frame(self)
        btns.pack(fill=X, pady=10)
        for text, cmd, style in [("Tambah", self.add, SUCCESS), ("Ubah", self.update, WARNING),
                                 ("Hapus", self.delete, DANGER), ("Bersih", self.clear_form, SECONDARY)]:
            ttk.Button(btns, text=text, command=cmd, bootstyle=style, width=8).pack(side=LEFT, padx=3)

        frame, self.tree = make_tree(self, columns, height=7)
        frame.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.reload()

    # -- util
    def data(self):
        return {k: v.get().strip() for k, v in self.vars.items()}

    def validate(self, d):
        for key, label, kind, opts in self.fields:
            if kind == "entry" and not d[key]:
                messagebox.showwarning("Validasi", f"{label} tidak boleh kosong.")
                return False
        return True

    def selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Pilih data", "Pilih data pada tabel terlebih dahulu.")
            return None
        return self.tree.item(sel[0])["values"][0]

    def reload(self):
        self.rows = {}
        self.tree.delete(*self.tree.get_children())
        for r in self.list_fn():
            self.rows[r[self.id_key]] = r
            self.tree.insert("", END, values=[r[c[0]] for c in self.columns])

    def clear_form(self):
        for (key, label, kind, opts) in self.fields:
            self.vars[key].set(opts[0] if kind == "combo" else "")
        self.tree.selection_remove(self.tree.selection())

    def on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.rows.get(self.tree.item(sel[0])["values"][0], {})
        for key, label, kind, opts in self.fields:
            self.vars[key].set("" if kind == "password" else str(r.get(key, "")))

    def _run(self, fn, *args):
        try:
            fn(*args)
            self.reload()
            self.clear_form()
            if self.on_change:
                self.on_change()
        except Exception as e:
            messagebox.showerror("Gagal", str(e))

    # -- aksi
    def add(self):
        d = self.data()
        if self.validate(d):
            self._run(self.add_fn, d)

    def update(self):
        id_ = self.selected_id()
        d = self.data()
        if id_ is not None and self.validate(d):
            self._run(self.update_fn, id_, d)

    def delete(self):
        id_ = self.selected_id()
        if id_ is not None and messagebox.askyesno("Konfirmasi", "Hapus data ini?"):
            self._run(self.delete_fn, id_)


# ------------------------------------------------------------ aplikasi
class App(ttk.Window):
    REFRESH_MS = 3000

    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Sistem Manajemen Antrian")
        self.user = None
        self._after_id = None
        self._clock_id = None
        try:
            names = list(self.style.theme_names())
        except Exception:
            names = []
        self.tema_list = [t for t in TEMA if t in names] or ["flatly"]
        self.var_tema = StringVar(value="flatly")
        self.show_login()

    # ------------------------------------------------------------ util
    def set_size(self, w, h):
        """Atur ukuran jendela dan letakkan di tengah layar."""
        x = max((self.winfo_screenwidth() - w) // 2, 0)
        y = max((self.winfo_screenheight() - h) // 2 - 30, 0)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def clear(self):
        for attr in ("_after_id", "_clock_id"):
            aid = getattr(self, attr)
            if aid:
                self.after_cancel(aid)
                setattr(self, attr, None)
        self.unbind("<Return>")
        for w in self.winfo_children():
            w.destroy()

    def safe(self, fn, *args):
        """Jalankan fungsi DB; tampilkan pesan jika error."""
        try:
            return True, fn(*args)
        except Exception as e:
            messagebox.showerror("Kesalahan database", str(e))
            return False, None

    def apply_styles(self):
        """Tinggi baris, font tabel, dan warna status pada semua Treeview."""
        st, c = self.style, self.style.colors
        for name in ("Treeview", "primary.Treeview"):
            st.configure(name, rowheight=30, font=(FONT, 10))
        for name in ("Treeview.Heading", "primary.Treeview.Heading"):
            st.configure(name, font=(FONT, 10, "bold"))
        warna = {"menunggu": c.warning, "dipanggil": c.info,
                 "selesai": c.success, "batal": c.danger}
        for tree in ALL_TREES:
            try:
                for tag, color in warna.items():
                    tree.tag_configure(tag, foreground=color, font=(FONT, 10, "bold"))
            except Exception:
                pass

    def ganti_tema(self, _=None):
        try:
            self.style.theme_use(self.var_tema.get())
        except Exception as e:
            messagebox.showerror("Tema", f"Tema tidak dapat dipakai: {e}")
            return
        self.after(80, self.apply_styles)

    def tick(self):
        now = datetime.now()
        self.lbl_jam.config(text=f"{HARI[now.weekday()]}, {now.day} {BULAN[now.month - 1]} "
                                 f"{now.year}   |   {now.strftime('%H:%M:%S')}")
        self._clock_id = self.after(1000, self.tick)

    # ------------------------------------------------------------ login
    def show_login(self):
        self.clear()
        self.user = None
        self.set_size(800, 460)

        wrap = ttk.Frame(self)
        wrap.pack(fill=BOTH, expand=True)
        wrap.columnconfigure((0, 1), weight=1, uniform="l")
        wrap.rowconfigure(0, weight=1)

        # panel kiri (berwarna)
        kiri = ttk.Frame(wrap, bootstyle=PRIMARY)
        kiri.grid(row=0, column=0, sticky=NSEW)
        box = ttk.Frame(kiri, bootstyle=PRIMARY)
        box.place(relx=0.5, rely=0.5, anchor=CENTER)
        ttk.Label(box, text="SISTEM\nMANAJEMEN\nANTRIAN", bootstyle="inverse-primary",
                  font=(FONT, 26, "bold"), justify=LEFT).pack(anchor=W)
        ttk.Label(box, text="Layanan & operasional\nNomor antrian otomatis",
                  bootstyle="inverse-primary", font=(FONT, 11), justify=LEFT).pack(anchor=W, pady=(12, 0))

        # panel kanan (form)
        kanan = ttk.Frame(wrap, padding=30)
        kanan.grid(row=0, column=1, sticky=NSEW)
        form = ttk.Frame(kanan)
        form.place(relx=0.5, rely=0.5, anchor=CENTER)
        ttk.Label(form, text="Selamat datang", font=(FONT, 20, "bold")).pack(anchor=W)
        ttk.Label(form, text="Silakan login untuk melanjutkan", bootstyle=SECONDARY).pack(anchor=W, pady=(0, 20))

        self.var_user, self.var_pass = StringVar(), StringVar()
        ttk.Label(form, text="Username").pack(anchor=W)
        e1 = ttk.Entry(form, textvariable=self.var_user, width=30, font=(FONT, 11))
        e1.pack(pady=(2, 12), ipady=3)
        e1.focus()
        ttk.Label(form, text="Password").pack(anchor=W)
        self.ent_pass = ttk.Entry(form, textvariable=self.var_pass, show="*", width=30, font=(FONT, 11))
        self.ent_pass.pack(pady=(2, 6), ipady=3)

        self.var_show = BooleanVar(value=False)
        ttk.Checkbutton(form, text="Tampilkan password", variable=self.var_show, bootstyle="round-toggle",
                        command=lambda: self.ent_pass.config(show="" if self.var_show.get() else "*")
                        ).pack(anchor=W, pady=(0, 16))
        ttk.Button(form, text="MASUK", command=self.do_login, bootstyle=PRIMARY).pack(fill=X, ipady=6)
        ttk.Label(form, text="Default: admin / admin123", bootstyle=SECONDARY,
                  font=(FONT, 9)).pack(pady=(12, 0))
        self.bind("<Return>", lambda e: self.do_login())

    def do_login(self):
        u, p = self.var_user.get().strip(), self.var_pass.get()
        if not u or not p:
            messagebox.showwarning("Validasi", "Username dan password wajib diisi.")
            return
        ok, user = self.safe(db.login, u, p)
        if not ok:
            return
        if not user:
            messagebox.showerror("Login gagal", "Username/password salah atau akun nonaktif.")
            return
        self.user = user
        self.show_main()

    # ------------------------------------------------------- halaman utama
    def show_main(self):
        self.clear()
        ALL_TREES.clear()
        self.set_size(1120, 760)
        self.minsize(980, 660)

        # ---- banner atas
        head = ttk.Frame(self, bootstyle=PRIMARY, padding=(22, 14))
        head.pack(fill=X)
        kiri = ttk.Frame(head, bootstyle=PRIMARY)
        kiri.pack(side=LEFT)
        ttk.Label(kiri, text="SISTEM MANAJEMEN ANTRIAN", bootstyle="inverse-primary",
                  font=(FONT, 19, "bold")).pack(anchor=W)
        self.lbl_jam = ttk.Label(kiri, text="", bootstyle="inverse-primary", font=(FONT, 10))
        self.lbl_jam.pack(anchor=W)

        kanan = ttk.Frame(head, bootstyle=PRIMARY)
        kanan.pack(side=RIGHT)
        ttk.Label(kanan, text=f"Petugas: {self.user['nama']}", bootstyle="inverse-primary",
                  font=(FONT, 11, "bold")).pack(side=LEFT, padx=(0, 15))
        ttk.Label(kanan, text="Tema:", bootstyle="inverse-primary").pack(side=LEFT)
        cb = ttk.Combobox(kanan, textvariable=self.var_tema, values=self.tema_list,
                          state="readonly", width=10)
        cb.pack(side=LEFT, padx=(5, 15))
        cb.bind("<<ComboboxSelected>>", self.ganti_tema)
        ttk.Button(kanan, text="Logout", bootstyle="light", command=self.show_login).pack(side=LEFT)

        # ---- kartu statistik
        strip = ttk.Frame(self, padding=(16, 14, 16, 0))
        strip.pack(fill=X)
        strip.columnconfigure((0, 1, 2), weight=1, uniform="t")
        for i, (judul, style, attr) in enumerate([
                ("MENUNGGU", "warning", "tile_menunggu"),
                ("SEDANG DILAYANI", "info", "tile_dilayani"),
                ("SELESAI HARI INI", "success", "tile_selesai")]):
            tile = ttk.Frame(strip, bootstyle=style, padding=(20, 10))
            tile.grid(row=0, column=i, sticky=EW, padx=6)
            ttk.Label(tile, text=judul, bootstyle=f"inverse-{style}",
                      font=(FONT, 10, "bold")).pack(anchor=W)
            lbl = ttk.Label(tile, text="0", bootstyle=f"inverse-{style}", font=(FONT, 30, "bold"))
            lbl.pack(anchor=W)
            setattr(self, attr, lbl)

        # ---- status bar bawah
        foot = ttk.Frame(self, padding=(16, 5))
        foot.pack(side=BOTTOM, fill=X)
        self.lbl_koneksi = ttk.Label(foot, text="●  Terhubung ke database db_antrian",
                                     bootstyle=SUCCESS, font=(FONT, 9))
        self.lbl_koneksi.pack(side=LEFT)
        ttk.Label(foot, text="Paket 17  •  Manajemen Antrian", bootstyle=SECONDARY,
                  font=(FONT, 9)).pack(side=RIGHT)

        # ---- tab
        nb = ttk.Notebook(self, bootstyle=PRIMARY)
        nb.pack(fill=BOTH, expand=True, padx=16, pady=12)
        tabs = {}
        for name in ("Ambil Nomor", "Panel Petugas", "Riwayat", "Dashboard",
                     "Laporan PDF", "Data Master", "Backup & Restore"):
            tabs[name] = ttk.Frame(nb, padding=18)
            nb.add(tabs[name], text=f"   {name}   ")

        self.build_tab_ambil(tabs["Ambil Nomor"])
        self.build_tab_petugas(tabs["Panel Petugas"])
        self.build_tab_riwayat(tabs["Riwayat"])
        self.build_tab_master(tabs["Data Master"])
        DashboardPanel(tabs["Dashboard"]).pack(fill=BOTH, expand=True)
        LaporanPanel(tabs["Laporan PDF"],
                     get_petugas=lambda: self.user["nama"]).pack(fill=BOTH, expand=True)
        BackupPanel(tabs["Backup & Restore"],
                    on_restored=self.setelah_restore).pack(fill=BOTH, expand=True)

        self.apply_styles()
        self.tick()
        self.refresh_all()

    # -------------------------------------------------- tab 1: ambil nomor
    def build_tab_ambil(self, tab):
        tab.columnconfigure(0, weight=2, uniform="c")
        tab.columnconfigure(1, weight=3, uniform="c")
        tab.rowconfigure(0, weight=1)

        kiri = ttk.Labelframe(tab, text=" Ambil Nomor ", padding=25)
        kiri.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        ttk.Label(kiri, text="Selamat Datang", font=(FONT, 22, "bold")).pack(pady=(8, 2))
        ttk.Label(kiri, text="Tekan tombol di bawah untuk\nmengambil nomor antrian",
                  justify=CENTER, bootstyle=SECONDARY).pack()
        ttk.Button(kiri, text="AMBIL NOMOR ANTRIAN", bootstyle=SUCCESS,
                   command=self.ambil_nomor).pack(fill=X, pady=22, ipady=14)
        ttk.Separator(kiri).pack(fill=X)
        ttk.Label(kiri, text="Nomor Anda", font=(FONT, 12)).pack(pady=(16, 0))
        self.lbl_nomor_anda = ttk.Label(kiri, text="-", font=(FONT, 56, "bold"), bootstyle=PRIMARY)
        self.lbl_nomor_anda.pack()
        self.lbl_nomor_info = ttk.Label(kiri, text="Belum ada nomor yang diambil", bootstyle=SECONDARY)
        self.lbl_nomor_info.pack()

        kanan = ttk.Frame(tab)
        kanan.grid(row=0, column=1, sticky=NSEW)
        kanan.rowconfigure((0, 1), weight=1)
        kanan.columnconfigure(0, weight=1)

        atas = ttk.Labelframe(kanan, text=" Sedang Dilayani ", padding=12)
        atas.grid(row=0, column=0, sticky=NSEW, pady=(0, 10))
        frame, self.tree_layani = make_tree(
            atas, [("nomor_antrian", "Nomor", 120), ("nama_loket", "Loket", 160),
                   ("waktu_panggil", "Dipanggil", 140)], height=5)
        frame.pack(fill=BOTH, expand=True)

        bawah = ttk.Labelframe(kanan, text=" Antrian Berikutnya ", padding=12)
        bawah.grid(row=1, column=0, sticky=NSEW)
        frame, self.tree_next = make_tree(
            bawah, [("nomor_antrian", "Nomor", 120), ("waktu_ambil", "Jam Ambil", 140)], height=6)
        frame.pack(fill=BOTH, expand=True)

    def ambil_nomor(self):
        ok, nomor = self.safe(db.ambil_nomor, "A")
        if ok:
            self.lbl_nomor_anda.config(text=nomor)
            self.lbl_nomor_info.config(text=f"Diambil pukul {datetime.now().strftime('%H:%M:%S')}")
            self.refresh_all()

    # ------------------------------------------------- tab 2: panel petugas
    def build_tab_petugas(self, tab):
        tab.columnconfigure(0, weight=2, uniform="p")
        tab.columnconfigure(1, weight=3, uniform="p")
        tab.rowconfigure(0, weight=1)

        kiri = ttk.Labelframe(tab, text=" Kontrol Loket ", padding=20)
        kiri.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        ttk.Button(kiri, text="↻   Reset Antrian Harian", bootstyle=(DANGER, OUTLINE),
                   command=self.reset).pack(side=BOTTOM, fill=X, ipady=4)
        ttk.Label(kiri, text="Pilih loket").pack(anchor=W)
        self.var_loket = StringVar()
        self.cb_loket = ttk.Combobox(kiri, textvariable=self.var_loket, state="readonly")
        self.cb_loket.pack(fill=X, pady=(4, 14))
        ttk.Button(kiri, text="▶   Panggil Berikutnya", bootstyle=PRIMARY,
                   command=self.panggil).pack(fill=X, pady=4, ipady=8)
        ttk.Button(kiri, text="✔   Selesai Dilayani", bootstyle=SUCCESS,
                   command=self.selesai).pack(fill=X, pady=4, ipady=8)

        now = ttk.Frame(kiri, bootstyle=PRIMARY, padding=12)
        now.pack(fill=X, pady=10)
        ttk.Label(now, text="SEDANG DIPANGGIL", bootstyle="inverse-primary",
                  font=(FONT, 10, "bold")).pack()
        self.lbl_dipanggil = ttk.Label(now, text="-", bootstyle="inverse-primary",
                                       font=(FONT, 40, "bold"))
        self.lbl_dipanggil.pack()
        self.lbl_info_loket = ttk.Label(now, text="Belum ada yang dipanggil",
                                        bootstyle="inverse-primary", font=(FONT, 10))
        self.lbl_info_loket.pack()


        kanan = ttk.Labelframe(tab, text=" Daftar Menunggu Hari Ini ", padding=12)
        kanan.grid(row=0, column=1, sticky=NSEW)
        frame, self.tree_menunggu = make_tree(
            kanan, [("nomor_antrian", "Nomor", 160), ("waktu_ambil", "Jam Ambil", 160)], height=12)
        frame.pack(fill=BOTH, expand=True)
        self.reload_loket_combo()

    def reload_loket_combo(self):
        ok, rows = self.safe(db.loket_list, True)
        vals = [f"{r['id_loket']} - {r['nama_loket']}" for r in rows] if ok else []
        self.cb_loket["values"] = vals
        if vals and self.var_loket.get() not in vals:
            self.var_loket.set(vals[0])

    def loket_id(self):
        if not self.var_loket.get():
            messagebox.showwarning("Validasi", "Pilih loket terlebih dahulu.")
            return None
        return int(self.var_loket.get().split(" - ")[0])

    def panggil(self):
        id_loket = self.loket_id()
        if id_loket is None:
            return
        ok, row = self.safe(db.panggil_berikutnya, id_loket, self.user["id_petugas"])
        if ok and row is None:
            messagebox.showinfo("Antrian kosong", "Tidak ada antrian yang menunggu.")
        self.refresh_all()

    def selesai(self):
        id_loket = self.loket_id()
        if id_loket is not None and self.safe(db.selesaikan, id_loket)[0]:
            self.refresh_all()

    def reset(self):
        if messagebox.askyesno("Reset harian",
                               "Hapus SEMUA antrian hari ini dan mulai lagi dari nomor 001?\n"
                               "Tindakan ini tidak bisa dibatalkan."):
            if self.safe(db.reset_harian)[0]:
                self.lbl_nomor_anda.config(text="-")
                self.lbl_nomor_info.config(text="Belum ada nomor yang diambil")
                self.refresh_all()

    # ------------------------------------------------------ tab 3: riwayat
    def build_tab_riwayat(self, tab):
        top = ttk.Frame(tab)
        top.pack(fill=X, pady=(0, 12))
        self.var_tgl = StringVar(value=date.today().strftime("%Y-%m-%d"))
        self.var_cari = StringVar()
        ttk.Label(top, text="Tanggal (YYYY-MM-DD):").pack(side=LEFT)
        ttk.Entry(top, textvariable=self.var_tgl, width=12).pack(side=LEFT, padx=6)
        ttk.Label(top, text="Cari:").pack(side=LEFT, padx=(12, 0))
        e = ttk.Entry(top, textvariable=self.var_cari, width=20)
        e.pack(side=LEFT, padx=6)
        e.bind("<Return>", lambda ev: self.load_riwayat())
        ttk.Button(top, text="Cari", bootstyle=PRIMARY, command=self.load_riwayat).pack(side=LEFT, padx=3)
        ttk.Button(top, text="Hari Ini", bootstyle=SECONDARY, command=self.riwayat_hari_ini).pack(side=LEFT, padx=3)
        ttk.Button(top, text="Ekspor CSV", bootstyle=SUCCESS, command=self.export_csv).pack(side=RIGHT)

        self.riwayat_cols = [("nomor_antrian", "Nomor", 90), ("tanggal", "Tanggal", 100),
                             ("status", "Status", 90), ("nama_loket", "Loket", 90),
                             ("nama_petugas", "Petugas", 150), ("waktu_ambil", "Ambil", 90),
                             ("waktu_panggil", "Panggil", 90), ("waktu_selesai", "Selesai", 90)]
        card = ttk.Labelframe(tab, text=" Riwayat Pelayanan ", padding=12)
        card.pack(fill=BOTH, expand=True)
        self.lbl_total = ttk.Label(card, text="Total: 0 data", bootstyle=SECONDARY)
        self.lbl_total.pack(side=BOTTOM, anchor=E, pady=(6, 0))
        frame, self.tree_riwayat = make_tree(card, self.riwayat_cols, height=14)
        frame.pack(fill=BOTH, expand=True)
        self.riwayat_rows = []
        self.load_riwayat()

    def riwayat_hari_ini(self):
        self.var_tgl.set(date.today().strftime("%Y-%m-%d"))
        self.var_cari.set("")
        self.load_riwayat()

    def load_riwayat(self):
        tgl = self.var_tgl.get().strip()
        try:
            datetime.strptime(tgl, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Validasi", "Format tanggal harus YYYY-MM-DD.")
            return
        ok, rows = self.safe(db.get_riwayat, tgl, self.var_cari.get().strip())
        if ok:
            self.riwayat_rows = rows
            fill_tree(self.tree_riwayat, rows, [c[0] for c in self.riwayat_cols], tag_key="status")
            self.lbl_total.config(text=f"Total: {len(rows)} data")

    def export_csv(self):
        if not self.riwayat_rows:
            messagebox.showinfo("Ekspor", "Tidak ada data untuk diekspor.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialdir=os.path.expanduser("~"),
            initialfile=f"riwayat_{self.var_tgl.get()}.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow([c[1] for c in self.riwayat_cols])
                for r in self.riwayat_rows:
                    w.writerow([fmt(r.get(c[0])) for c in self.riwayat_cols])
        except PermissionError:
            messagebox.showerror(
                "Ekspor gagal",
                "File tidak bisa disimpan di lokasi ini.\n"
                "Tutup file jika sedang terbuka di Excel, atau pilih folder lain "
                "(misalnya Desktop atau Documents).")
            return
        messagebox.showinfo("Ekspor", f"Berhasil disimpan:\n{path}")

    # ---------------------------------------------------- tab 4: data master
    def build_tab_master(self, tab):
        tab.columnconfigure((0, 1), weight=1, uniform="a")
        tab.rowconfigure(0, weight=1)
        CrudPanel(
            tab, "Data Loket",
            columns=[("id_loket", "ID", 40), ("nama_loket", "Nama Loket", 130), ("status", "Status", 80)],
            fields=[("nama_loket", "Nama Loket", "entry", None),
                    ("status", "Status", "combo", ["aktif", "nonaktif"])],
            list_fn=db.loket_list, add_fn=db.loket_add,
            update_fn=db.loket_update, delete_fn=db.loket_delete,
            on_change=self.reload_loket_combo,
        ).grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        CrudPanel(
            tab, "Data Petugas",
            columns=[("id_petugas", "ID", 40), ("nama", "Nama", 120),
                     ("username", "Username", 90), ("status", "Status", 70)],
            fields=[("nama", "Nama", "entry", None), ("username", "Username", "entry", None),
                    ("password", "Password*", "password", None),
                    ("status", "Status", "combo", ["aktif", "nonaktif"])],
            list_fn=db.petugas_list, add_fn=db.petugas_add,
            update_fn=db.petugas_update, delete_fn=db.petugas_delete,
        ).grid(row=0, column=1, sticky=NSEW)
        ttk.Label(tab, text="*Saat mengubah petugas, kosongkan password jika tidak ingin menggantinya.",
                  bootstyle=SECONDARY).grid(row=1, column=0, columnspan=2, sticky=W, pady=8)

    def setelah_restore(self):
        """Data petugas bisa berubah setelah restore, jadi pengguna login ulang."""
        messagebox.showinfo("Login ulang", "Silakan login kembali dengan data hasil restore.")
        self.show_login()

    # -------------------------------------------------------- auto refresh
    def refresh_all(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        try:
            layani = db.get_sedang_dilayani()
            menunggu = db.get_menunggu()
            stat = db.get_statistik()

            fill_tree(self.tree_layani, layani, ["nomor_antrian", "nama_loket", "waktu_panggil"], "status")
            fill_tree(self.tree_next, menunggu[:8], ["nomor_antrian", "waktu_ambil"], "status")
            fill_tree(self.tree_menunggu, menunggu, ["nomor_antrian", "waktu_ambil"], "status")

            self.tile_menunggu.config(text=str(stat["menunggu"]))
            self.tile_dilayani.config(text=str(stat["dipanggil"]))
            self.tile_selesai.config(text=str(stat["selesai"]))

            # Nomor yang sedang dilayani di loket terpilih
            teks, info = "-", "Belum ada yang dipanggil di loket ini"
            if self.var_loket.get():
                nama = self.var_loket.get().split(" - ", 1)[1]
                for r in layani:
                    if r["nama_loket"] == nama:
                        teks, info = r["nomor_antrian"], f"Sedang dilayani di {nama}"
                        break
            self.lbl_dipanggil.config(text=teks)
            self.lbl_info_loket.config(text=info)
            self.lbl_koneksi.config(text="●  Terhubung ke database db_antrian", bootstyle=SUCCESS)
        except Exception as e:  # koneksi putus sementara dsb.
            print("Refresh gagal:", e)
            try:
                self.lbl_koneksi.config(text="●  Koneksi database terputus", bootstyle=DANGER)
            except Exception:
                pass
        self._after_id = self.after(self.REFRESH_MS, self.refresh_all)


if __name__ == "__main__":
    ok, msg = db.test_connection()
    if not ok:
        messagebox.showerror("Koneksi MySQL gagal",
                             "Pastikan MySQL di XAMPP sudah di-Start dan database "
                             f"db_antrian sudah di-import.\n\nDetail: {msg}")
        sys.exit(1)
    App().mainloop()