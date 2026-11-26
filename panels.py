"""Panel UI tambahan: Dashboard, Laporan PDF, Backup & Restore."""
import os
import subprocess
import sys
from datetime import date, datetime
from tkinter import StringVar, BooleanVar, filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import backup
import statistik
from grafik import gambar_dashboard

FONT = "Segoe UI"


def buka_path(path):
    """Buka file/folder dengan aplikasi bawaan sistem operasi."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)                      # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Gagal membuka", str(e))


def _parse_tgl(teks, nama):
    try:
        return datetime.strptime(teks.strip(), "%Y-%m-%d").date()
    except ValueError:
        messagebox.showwarning("Validasi", f"{nama}: format tanggal harus YYYY-MM-DD.")
        return None


# ============================================================== DASHBOARD
class DashboardPanel(ttk.Frame):
    """Kartu ringkasan + 4 grafik. Diperbarui saat tab dibuka atau tombol ditekan."""
    PILIHAN = ["Hari ini", "7 hari terakhir", "30 hari terakhir", "Bulan ini"]

    def __init__(self, master):
        super().__init__(master)
        top = ttk.Frame(self)
        top.pack(fill=X, pady=(0, 10))
        ttk.Label(top, text="Rentang waktu:").pack(side=LEFT)
        self.var_rentang = StringVar(value="7 hari terakhir")
        cb = ttk.Combobox(top, textvariable=self.var_rentang, values=self.PILIHAN,
                          state="readonly", width=18)
        cb.pack(side=LEFT, padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="↻  Perbarui", bootstyle=PRIMARY,
                   command=self.refresh).pack(side=LEFT)
        self.lbl_status = ttk.Label(top, text="", bootstyle=SECONDARY)
        self.lbl_status.pack(side=RIGHT)

        strip = ttk.Frame(self)
        strip.pack(fill=X, pady=(0, 10))
        strip.columnconfigure(tuple(range(5)), weight=1, uniform="k")
        self.kpi = {}
        for i, (kunci, judul, style) in enumerate([
                ("total", "TOTAL ANTRIAN", "primary"), ("selesai", "SELESAI", "success"),
                ("batal", "BATAL", "danger"), ("rata_tunggu", "RATA-RATA TUNGGU", "warning"),
                ("rata_layanan", "RATA-RATA LAYANAN", "info")]):
            tile = ttk.Frame(strip, bootstyle=style, padding=(14, 8))
            tile.grid(row=0, column=i, sticky=EW, padx=4)
            ttk.Label(tile, text=judul, bootstyle=f"inverse-{style}",
                      font=(FONT, 8, "bold")).pack(anchor=W)
            lbl = ttk.Label(tile, text="-", bootstyle=f"inverse-{style}",
                            font=(FONT, 18, "bold"))
            lbl.pack(anchor=W)
            self.kpi[kunci] = lbl

        self.fig = Figure(figsize=(9, 5), dpi=100, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)
        self.bind("<Map>", self._saat_tampil)

    def _saat_tampil(self, event):
        if event.widget is self:                    # tab dibuka -> data terbaru
            self.refresh()

    def refresh(self):
        d1, d2 = statistik.rentang(self.var_rentang.get())
        try:
            stat = statistik.ambil_statistik(d1, d2)
        except Exception as e:
            self.lbl_status.config(text=f"Gagal memuat data: {e}", bootstyle=DANGER)
            return
        r = stat["ringkasan"]
        self.kpi["total"].config(text=str(r["total"]))
        self.kpi["selesai"].config(text=str(r["selesai"]))
        self.kpi["batal"].config(text=str(r["batal"]))
        self.kpi["rata_tunggu"].config(text=statistik.fmt_durasi(r["rata_tunggu"]))
        self.kpi["rata_layanan"].config(text=statistik.fmt_durasi(r["rata_layanan"]))
        try:
            warna = ttk.Style().colors
        except Exception:
            warna = None
        gambar_dashboard(self.fig, stat, warna)
        self.canvas.draw_idle()
        self.lbl_status.config(
            text=f"Diperbarui {datetime.now():%H:%M:%S}  •  "
                 f"{statistik.tgl_id(d1)} – {statistik.tgl_id(d2)}", bootstyle=SECONDARY)


# ================================================================ LAPORAN
class LaporanPanel(ttk.Labelframe):
    def __init__(self, master, get_petugas):
        super().__init__(master, text=" Laporan PDF ", padding=20)
        self.get_petugas = get_petugas
        hari_ini = date.today().strftime("%Y-%m-%d")
        self.var_d1, self.var_d2 = StringVar(value=hari_ini), StringVar(value=hari_ini)
        self.var_rincian = BooleanVar(value=True)

        ttk.Label(self, text="Buat laporan PDF berisi ringkasan, grafik, kinerja loket & petugas, "
                             "serta rincian antrian.", bootstyle=SECONDARY).pack(anchor=W, pady=(0, 16))

        form = ttk.Frame(self)
        form.pack(anchor=W)
        ttk.Label(form, text="Dari tanggal").grid(row=0, column=0, sticky=W, pady=5)
        ttk.Entry(form, textvariable=self.var_d1, width=14).grid(row=0, column=1, padx=10)
        ttk.Label(form, text="Sampai tanggal").grid(row=1, column=0, sticky=W, pady=5)
        ttk.Entry(form, textvariable=self.var_d2, width=14).grid(row=1, column=1, padx=10)
        ttk.Label(form, text="(format YYYY-MM-DD)", bootstyle=SECONDARY).grid(row=0, column=2, rowspan=2)

        cepat = ttk.Frame(self)
        cepat.pack(anchor=W, pady=12)
        ttk.Label(cepat, text="Pilih cepat:").pack(side=LEFT, padx=(0, 8))
        for nama in ("Hari ini", "7 hari terakhir", "30 hari terakhir", "Bulan ini"):
            ttk.Button(cepat, text=nama, bootstyle=(SECONDARY, OUTLINE),
                       command=lambda n=nama: self.set_rentang(n)).pack(side=LEFT, padx=3)

        ttk.Checkbutton(self, text="Sertakan tabel rincian antrian", variable=self.var_rincian,
                        bootstyle="round-toggle").pack(anchor=W, pady=(4, 18))
        ttk.Button(self, text="📄   Buat Laporan PDF", bootstyle=SUCCESS,
                   command=self.buat).pack(anchor=W, ipady=8, ipadx=14)
        self.lbl_hasil = ttk.Label(self, text="", bootstyle=SECONDARY)
        self.lbl_hasil.pack(anchor=W, pady=14)

    def set_rentang(self, nama):
        d1, d2 = statistik.rentang(nama)
        self.var_d1.set(d1.strftime("%Y-%m-%d"))
        self.var_d2.set(d2.strftime("%Y-%m-%d"))

    def buat(self):
        d1, d2 = _parse_tgl(self.var_d1.get(), "Dari tanggal"), _parse_tgl(self.var_d2.get(), "Sampai tanggal")
        if d1 is None or d2 is None:
            return
        if d1 > d2:
            messagebox.showwarning("Validasi", "Tanggal awal tidak boleh setelah tanggal akhir.")
            return
        try:
            import laporan
        except ImportError:
            messagebox.showerror("Modul belum terpasang",
                                 "Library reportlab belum terpasang.\nJalankan: pip install reportlab")
            return
        try:
            stat = statistik.ambil_statistik(d1, d2)
            rincian = statistik.ambil_rincian(d1, d2) if self.var_rincian.get() else None
        except Exception as e:
            messagebox.showerror("Kesalahan database", str(e))
            return
        nama_file = (f"laporan_antrian_{d1:%Y%m%d}.pdf" if d1 == d2
                     else f"laporan_antrian_{d1:%Y%m%d}_{d2:%Y%m%d}.pdf")
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialdir=os.path.expanduser("~"),
            initialfile=nama_file, filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            laporan.buat_laporan_pdf(path, stat, rincian, petugas=self.get_petugas())
        except PermissionError:
            messagebox.showerror("Gagal menyimpan",
                                 "File tidak bisa ditulis. Tutup file jika sedang terbuka di "
                                 "aplikasi PDF, atau pilih folder lain.")
            return
        except Exception as e:
            messagebox.showerror("Gagal membuat laporan", str(e))
            return
        self.lbl_hasil.config(text=f"Tersimpan: {path}")
        if messagebox.askyesno("Laporan dibuat", f"Laporan berhasil disimpan:\n{path}\n\nBuka sekarang?"):
            buka_path(path)


# ================================================================= BACKUP
class BackupPanel(ttk.Frame):
    def __init__(self, master, on_restored=None):
        super().__init__(master)
        self.on_restored = on_restored

        atas = ttk.Labelframe(self, text=" Backup ", padding=15)
        atas.pack(fill=X)
        ttk.Label(atas, text=f"Folder backup otomatis:  {backup.FOLDER_BACKUP}",
                  bootstyle=SECONDARY).pack(anchor=W, pady=(0, 10))
        baris = ttk.Frame(atas)
        baris.pack(fill=X)
        ttk.Button(baris, text="💾  Backup Sekarang", bootstyle=SUCCESS,
                   command=self.backup_sekarang).pack(side=LEFT, padx=(0, 6), ipady=4)
        ttk.Button(baris, text="Simpan Backup Ke...", bootstyle=(SUCCESS, OUTLINE),
                   command=self.backup_ke).pack(side=LEFT, padx=6, ipady=4)
        ttk.Button(baris, text="Buka Folder", bootstyle=(SECONDARY, OUTLINE),
                   command=self.buka_folder).pack(side=RIGHT, ipady=4)

        tengah = ttk.Labelframe(self, text=" Restore ", padding=15)
        tengah.pack(fill=BOTH, expand=True, pady=12)
        ttk.Label(tengah, text="⚠  Restore MENGGANTI seluruh data (antrian, loket, petugas) dengan isi backup. "
                               "Backup pengaman dibuat otomatis sebelumnya.",
                  bootstyle=WARNING, wraplength=900, justify=LEFT).pack(anchor=W, pady=(0, 10))
        baris = ttk.Frame(tengah)
        baris.pack(fill=X, pady=(0, 8))
        ttk.Button(baris, text="Restore dari Daftar", bootstyle=DANGER,
                   command=self.restore_daftar).pack(side=LEFT, padx=(0, 6), ipady=4)
        ttk.Button(baris, text="Restore dari File...", bootstyle=(DANGER, OUTLINE),
                   command=self.restore_file).pack(side=LEFT, padx=6, ipady=4)

        kolom = [("nama", "Nama File", 380), ("ukuran", "Ukuran", 90), ("waktu", "Dibuat", 170)]
        frame = ttk.Frame(tengah)
        frame.pack(fill=BOTH, expand=True)
        self.tree = ttk.Treeview(frame, columns=[k[0] for k in kolom], show="headings",
                                 height=8, bootstyle=PRIMARY)
        for k, judul, lebar in kolom:
            self.tree.heading(k, text=judul)
            self.tree.column(k, width=lebar, anchor=W if k == "nama" else CENTER)
        sb = ttk.Scrollbar(frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)
        self.files = {}
        self.muat_daftar()

    # -- util
    def _sibuk(self, aktif):
        self.winfo_toplevel().config(cursor="watch" if aktif else "")
        self.update_idletasks()

    def muat_daftar(self):
        self.tree.delete(*self.tree.get_children())
        self.files = {}
        for f in backup.daftar_backup():
            iid = self.tree.insert("", END, values=(
                f["nama"], backup.fmt_ukuran(f["ukuran"]), f["waktu"].strftime("%Y-%m-%d %H:%M:%S")))
            self.files[iid] = f["path"]

    def buka_folder(self):
        os.makedirs(backup.FOLDER_BACKUP, exist_ok=True)
        buka_path(backup.FOLDER_BACKUP)

    # -- backup
    def _jalankan_backup(self, path=None):
        self._sibuk(True)
        try:
            info = backup.buat_backup(path)
        except backup.BackupError as e:
            messagebox.showerror("Backup gagal", str(e))
            return
        finally:
            self._sibuk(False)
        total = sum(info["tabel"].values())
        messagebox.showinfo("Backup berhasil",
                            f"Tersimpan:\n{info['path']}\n\n"
                            f"{len(info['tabel'])} tabel, {total} baris, "
                            f"{backup.fmt_ukuran(info['ukuran'])}")
        self.muat_daftar()

    def backup_sekarang(self):
        self._jalankan_backup()

    def backup_ke(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".sql", initialdir=os.path.expanduser("~"),
            initialfile=f"backup_antrian_{datetime.now():%Y%m%d_%H%M%S}.sql",
            filetypes=[("File SQL", "*.sql")])
        if path:
            self._jalankan_backup(path)

    # -- restore
    def restore_daftar(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Pilih backup", "Pilih file backup pada daftar terlebih dahulu.")
            return
        self._restore(self.files[sel[0]])

    def restore_file(self):
        path = filedialog.askopenfilename(
            initialdir=backup.FOLDER_BACKUP if os.path.isdir(backup.FOLDER_BACKUP)
            else os.path.expanduser("~"),
            filetypes=[("File SQL", "*.sql"), ("Semua file", "*.*")])
        if path:
            self._restore(path)

    def _restore(self, path):
        # Validasi dulu supaya pengguna tahu file tidak cocok SEBELUM diminta konfirmasi.
        try:
            backup.baca_dan_validasi(path)
        except backup.BackupError as e:
            messagebox.showerror("File tidak valid", str(e))
            return
        if not messagebox.askyesno(
                "Konfirmasi Restore",
                f"Seluruh data saat ini akan DIGANTI dengan isi:\n{os.path.basename(path)}\n\n"
                "Backup pengaman dibuat otomatis lebih dulu.\n"
                "Setelah restore Anda harus login ulang.\n\nLanjutkan?",
                icon="warning", default="no"):
            return
        self._sibuk(True)
        try:
            pengaman = backup.restore_backup(path)
        except backup.BackupError as e:
            messagebox.showerror("Restore gagal", str(e))
            return
        finally:
            self._sibuk(False)
        self.muat_daftar()
        messagebox.showinfo("Restore berhasil",
                            f"Data berhasil dipulihkan.\n\nBackup pengaman data sebelumnya:\n{pengaman}")
        if self.on_restored:
            self.on_restored()