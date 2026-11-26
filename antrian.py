import re
from contextlib import contextmanager
from tkinter import StringVar
from tkinter import messagebox
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from database import koneksi


@contextmanager
def sesi_db(parent=None):
    """Membuka koneksi DB dan menutupnya otomatis.
    Menghasilkan None (setelah menampilkan pesan error) jika gagal."""
    db = koneksi()

    if db is None:
        messagebox.showerror(
            "Error",
            "Database tidak terhubung!",
            parent=parent
        )
        yield None
        return

    try:
        yield db
    finally:
        db.close()


def teks(nilai):
    return "-" if nilai is None else str(nilai)


def buat_tabel(parent, kolom, lebar, tinggi=12):
    frame = tb.Frame(parent)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tabel = ttk.Treeview(
        frame,
        columns=kolom,
        show="headings",
        height=tinggi,
        selectmode="browse"
    )

    scroll = ttk.Scrollbar(frame, orient="vertical", command=tabel.yview)
    tabel.configure(yscrollcommand=scroll.set)

    for nama_kolom, w in zip(kolom, lebar):
        tabel.heading(nama_kolom, text=nama_kolom)
        tabel.column(nama_kolom, width=w, anchor="center")

    tabel.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    return tabel


def buka_antrian(petugas=None):

    window = tb.Window(themename="cosmo")
    window.title("Sistem Manajemen Antrian")
    window.geometry("1100x780")

    id_petugas = petugas[0] if petugas else None
    nama_petugas = petugas[1] if petugas else "Petugas"

    var_loket = StringVar()
    var_layani = StringVar(value="-")
    var_menunggu = StringVar(value="Menunggu: 0")
    loket_map = {}   # nama loket -> id loket

    tb.Label(
        window,
        text="SISTEM MANAJEMEN ANTRIAN",
        font=("Arial", 23, "bold")
    ).pack(pady=(15, 5))

    tb.Label(
        window,
        text=f"Selamat datang, {nama_petugas}",
        font=("Arial", 13)
    ).pack(pady=2)

    # ---------------------------------------------------------
    # PANEL: ANTRIAN YANG SEDANG DILAYANI
    # ---------------------------------------------------------
    panel = tb.Labelframe(window, text="Sedang Dilayani", padding=10)
    panel.pack(fill="x", padx=20, pady=8)

    tb.Label(
        panel,
        textvariable=var_layani,
        font=("Arial", 15, "bold"),
        bootstyle="primary",
        justify="left"
    ).pack(anchor="w")

    tb.Label(
        panel,
        textvariable=var_menunggu,
        font=("Arial", 11)
    ).pack(anchor="w", pady=(6, 0))

    # ---------------------------------------------------------
    # HELPER
    # ---------------------------------------------------------
    def pilih_loket():
        id_loket = loket_map.get(var_loket.get())

        if id_loket is None:
            messagebox.showwarning(
                "Peringatan",
                "Pilih loket terlebih dahulu!\n"
                "(Pastikan tabel loket sudah terisi.)"
            )

        return id_loket

    def muat_loket():
        hasil = []

        with sesi_db() as db:
            if db is None:
                return

            cursor = db.cursor()

            try:
                cursor.execute("""
                    SELECT id_loket, nama_loket
                    FROM loket
                    ORDER BY id_loket
                """)
                hasil = cursor.fetchall()

            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            finally:
                cursor.close()

        loket_map.clear()

        for id_loket, nama_loket in hasil:
            loket_map[nama_loket] = id_loket

        combo_loket["values"] = list(loket_map)

        if loket_map and var_loket.get() not in loket_map:
            var_loket.set(next(iter(loket_map)))

    # ---------------------------------------------------------
    # REFRESH SEMUA DATA (tabel hari ini, riwayat, panel layanan)
    # ---------------------------------------------------------
    def refresh():

        for t in (tabel, tabel_riwayat):
            for item in t.get_children():
                t.delete(item)

        antrian_hari_ini = []
        riwayat = []
        sedang_dilayani = []
        jumlah_menunggu = 0

        with sesi_db() as db:
            if db is None:
                return

            cursor = db.cursor()

            try:
                cursor.execute("""
                    SELECT a.id_antrian, a.nomor_antrian, p.nama_pasien,
                           COALESCE(l.nama_loket, '-'),
                           a.waktu_daftar, a.status
                    FROM antrian a
                    JOIN pasien p ON a.id_pasien = p.id_pasien
                    LEFT JOIN loket l ON a.id_loket = l.id_loket
                    WHERE a.tanggal = CURDATE() AND a.direset = 0
                    ORDER BY a.id_antrian ASC
                """)
                antrian_hari_ini = cursor.fetchall()

                cursor.execute("""
                    SELECT a.id_antrian, a.nomor_antrian, p.nama_pasien,
                           a.tanggal,
                           COALESCE(l.nama_loket, '-'),
                           COALESCE(pt.nama_petugas, '-'),
                           a.waktu_daftar, a.waktu_panggil, a.waktu_selesai
                    FROM antrian a
                    JOIN pasien p ON a.id_pasien = p.id_pasien
                    LEFT JOIN loket l ON a.id_loket = l.id_loket
                    LEFT JOIN petugas pt ON a.id_petugas = pt.id_petugas
                    WHERE a.status = 'Selesai'
                    ORDER BY a.tanggal DESC, a.id_antrian DESC
                    LIMIT 500
                """)
                riwayat = cursor.fetchall()

                cursor.execute("""
                    SELECT l.nama_loket, a.nomor_antrian, p.nama_pasien
                    FROM loket l
                    LEFT JOIN antrian a
                        ON a.id_loket = l.id_loket
                        AND a.tanggal = CURDATE()
                        AND a.direset = 0
                        AND a.status = 'Dipanggil'
                    LEFT JOIN pasien p ON a.id_pasien = p.id_pasien
                    ORDER BY l.id_loket
                """)
                sedang_dilayani = cursor.fetchall()

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM antrian
                    WHERE tanggal = CURDATE()
                    AND direset = 0
                    AND status = 'Menunggu'
                """)
                jumlah_menunggu = cursor.fetchone()[0]

            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            finally:
                cursor.close()

        for baris in antrian_hari_ini:
            tabel.insert(
                "", END,
                iid=str(baris[0]),   # id_antrian disimpan sebagai iid
                values=[teks(v) for v in baris[1:]]
            )

        for baris in riwayat:
            tabel_riwayat.insert(
                "", END,
                values=[teks(v) for v in baris[1:]]
            )

        baris_layani = []
        for nama_loket, nomor, nama_pasien in sedang_dilayani:
            if nomor:
                baris_layani.append(f"{nama_loket}  →  {nomor}  ({nama_pasien})")
            else:
                baris_layani.append(f"{nama_loket}  →  (kosong)")

        var_layani.set("\n".join(baris_layani) if baris_layani else "-")
        var_menunggu.set(f"Menunggu: {jumlah_menunggu} antrian")

    # ---------------------------------------------------------
    # 1. PENDAFTARAN / AMBIL NOMOR ANTRIAN
    # ---------------------------------------------------------
    def daftar_pasien():

        form = tb.Toplevel(window)
        form.title("Pendaftaran Antrian")
        form.geometry("450x450")
        form.transient(window)
        form.grab_set()

        tb.Label(
            form,
            text="PENDAFTARAN ANTRIAN",
            font=("Arial", 18, "bold")
        ).pack(pady=20)

        tb.Label(form, text="Nama Pasien").pack()
        entry_nama = tb.Entry(form, width=40)
        entry_nama.pack(pady=5)

        tb.Label(form, text="Nomor HP").pack()
        entry_hp = tb.Entry(form, width=40)
        entry_hp.pack(pady=5)

        tb.Label(form, text="Alamat").pack()
        entry_alamat = tb.Entry(form, width=40)
        entry_alamat.pack(pady=5)

        entry_nama.focus()

        def ambil_nomor():

            nama = entry_nama.get().strip()
            hp = entry_hp.get().strip()
            alamat = entry_alamat.get().strip()

            if not nama:
                messagebox.showwarning(
                    "Peringatan",
                    "Nama pasien harus diisi!",
                    parent=form
                )
                return

            if hp and not re.fullmatch(r"[0-9+\-\s]{8,15}", hp):
                messagebox.showwarning(
                    "Peringatan",
                    "Nomor HP tidak valid (8-15 digit angka)!",
                    parent=form
                )
                return

            nomor = None

            with sesi_db(form) as db:
                if db is None:
                    return

                cursor = db.cursor()

                try:
                    # Nomor tertinggi hari ini (sejak reset terakhir)
                    cursor.execute("""
                        SELECT COALESCE(
                            MAX(CAST(SUBSTRING(nomor_antrian, 2) AS UNSIGNED)), 0
                        )
                        FROM antrian
                        WHERE tanggal = CURDATE() AND direset = 0
                    """)

                    nomor = f"A{int(cursor.fetchone()[0]) + 1:03d}"

                    cursor.execute("""
                        INSERT INTO pasien
                        (nama_pasien, no_hp, alamat)
                        VALUES (%s, %s, %s)
                    """, (
                        nama,
                        hp if hp else None,
                        alamat if alamat else None
                    ))

                    id_pasien = cursor.lastrowid

                    cursor.execute("""
                        INSERT INTO antrian
                        (id_pasien, nomor_antrian, tanggal,
                         waktu_daftar, status)
                        VALUES (%s, %s, CURDATE(),
                                CURTIME(), 'Menunggu')
                    """, (id_pasien, nomor))

                    db.commit()

                except Exception as e:
                    db.rollback()
                    messagebox.showerror("Error", str(e), parent=form)
                    return

                finally:
                    cursor.close()

            messagebox.showinfo(
                "Berhasil",
                f"Pendaftaran berhasil!\n\n"
                f"Nama: {nama}\n"
                f"Nomor Antrian: {nomor}\n"
                f"Status: Menunggu",
                parent=form
            )

            form.destroy()
            refresh()

        tb.Button(
            form,
            text="AMBIL NOMOR ANTRIAN",
            bootstyle="success",
            width=30,
            command=ambil_nomor
        ).pack(pady=25)

    # ---------------------------------------------------------
    # 2. PANGGIL NOMOR BERIKUTNYA
    # ---------------------------------------------------------
    def panggil_berikutnya():

        id_loket = pilih_loket()

        if id_loket is None:
            return

        pesan = None

        with sesi_db() as db:
            if db is None:
                return

            cursor = db.cursor()

            try:
                # Satu loket hanya melayani satu antrian pada satu waktu
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM antrian
                    WHERE tanggal = CURDATE() AND direset = 0
                    AND status = 'Dipanggil' AND id_loket = %s
                """, (id_loket,))

                if cursor.fetchone()[0] > 0:
                    messagebox.showwarning(
                        "Peringatan",
                        "Loket ini masih melayani antrian.\n"
                        "Selesaikan dulu sebelum memanggil berikutnya!"
                    )
                    return

                cursor.execute("""
                    SELECT id_antrian, nomor_antrian
                    FROM antrian
                    WHERE tanggal = CURDATE() AND direset = 0
                    AND status = 'Menunggu'
                    ORDER BY id_antrian ASC
                    LIMIT 1
                    FOR UPDATE
                """)

                baris = cursor.fetchone()

                if baris is None:
                    db.rollback()
                    messagebox.showinfo(
                        "Informasi",
                        "Tidak ada antrian yang sedang menunggu."
                    )
                    return

                cursor.execute("""
                    UPDATE antrian
                    SET status = 'Dipanggil',
                        id_loket = %s,
                        id_petugas = %s,
                        waktu_panggil = CURTIME()
                    WHERE id_antrian = %s
                """, (id_loket, id_petugas, baris[0]))

                db.commit()
                pesan = f"Nomor {baris[1]} dipanggil ke {var_loket.get()}!"

            except Exception as e:
                db.rollback()
                messagebox.showerror("Error", str(e))
                return

            finally:
                cursor.close()

        messagebox.showinfo("Berhasil", pesan)
        refresh()

    # ---------------------------------------------------------
    # 3. SELESAIKAN ANTRIAN
    #    Pakai baris yang dipilih; jika tidak ada yang dipilih,
    #    selesaikan antrian yang sedang dilayani di loket terpilih.
    # ---------------------------------------------------------
    def selesaikan_antrian():

        pilihan = tabel.selection()
        id_antrian = int(pilihan[0]) if pilihan else None
        nomor = tabel.item(pilihan[0], "values")[0] if pilihan else None
        id_loket = None

        if id_antrian is None:
            id_loket = pilih_loket()

            if id_loket is None:
                return

        pesan = None

        with sesi_db() as db:
            if db is None:
                return

            cursor = db.cursor()

            try:
                if id_antrian is None:
                    cursor.execute("""
                        SELECT id_antrian, nomor_antrian
                        FROM antrian
                        WHERE tanggal = CURDATE() AND direset = 0
                        AND status = 'Dipanggil' AND id_loket = %s
                        LIMIT 1
                    """, (id_loket,))

                    baris = cursor.fetchone()

                    if baris is None:
                        messagebox.showwarning(
                            "Peringatan",
                            "Tidak ada antrian yang sedang dilayani "
                            "di loket ini!"
                        )
                        return

                    id_antrian, nomor = baris

                cursor.execute("""
                    UPDATE antrian
                    SET status = 'Selesai',
                        waktu_selesai = CURTIME()
                    WHERE id_antrian = %s
                    AND status = 'Dipanggil'
                """, (id_antrian,))

                if cursor.rowcount > 0:
                    db.commit()
                    pesan = f"Nomor {nomor} sudah selesai dilayani!"
                else:
                    db.rollback()
                    messagebox.showwarning(
                        "Peringatan",
                        "Antrean harus dipanggil terlebih dahulu!"
                    )
                    return

            except Exception as e:
                db.rollback()
                messagebox.showerror("Error", str(e))
                return

            finally:
                cursor.close()

        messagebox.showinfo("Berhasil", pesan)
        refresh()

    # ---------------------------------------------------------
    # 4. RESET ANTRIAN HARIAN
    #    - yang masih Menunggu/Dipanggil -> Dibatalkan
    #    - nomor kembali mulai dari A001
    #    - riwayat yang sudah Selesai tetap tersimpan
    # ---------------------------------------------------------
    def reset_harian():

        yakin = messagebox.askyesno(
            "Konfirmasi Reset",
            "Reset antrian hari ini?\n\n"
            "• Antrian yang masih menunggu/dipanggil akan DIBATALKAN\n"
            "• Nomor antrian kembali mulai dari A001\n"
            "• Riwayat pelayanan yang sudah selesai tetap tersimpan",
            icon="warning"
        )

        if not yakin:
            return

        with sesi_db() as db:
            if db is None:
                return

            cursor = db.cursor()

            try:
                cursor.execute("""
                    UPDATE antrian
                    SET status = 'Dibatalkan'
                    WHERE tanggal = CURDATE() AND direset = 0
                    AND status IN ('Menunggu', 'Dipanggil')
                """)

                cursor.execute("""
                    UPDATE antrian
                    SET direset = 1
                    WHERE tanggal = CURDATE() AND direset = 0
                """)

                db.commit()

            except Exception as e:
                db.rollback()
                messagebox.showerror("Error", str(e))
                return

            finally:
                cursor.close()

        messagebox.showinfo("Berhasil", "Antrian hari ini sudah direset.")
        refresh()

    # ---------------------------------------------------------
    # BARIS TOMBOL
    # ---------------------------------------------------------
    bar = tb.Frame(window)
    bar.pack(pady=8)

    tb.Label(bar, text="Loket:", font=("Arial", 11, "bold")).pack(
        side="left", padx=(0, 5)
    )

    combo_loket = tb.Combobox(
        bar,
        textvariable=var_loket,
        state="readonly",
        width=12
    )
    combo_loket.pack(side="left", padx=(0, 15))

    tb.Button(
        bar, text="PENDAFTARAN", bootstyle="success",
        width=16, command=daftar_pasien
    ).pack(side="left", padx=4)

    tb.Button(
        bar, text="PANGGIL BERIKUTNYA", bootstyle="warning",
        width=20, command=panggil_berikutnya
    ).pack(side="left", padx=4)

    tb.Button(
        bar, text="SELESAIKAN", bootstyle="success",
        width=14, command=selesaikan_antrian
    ).pack(side="left", padx=4)

    tb.Button(
        bar, text="REFRESH", bootstyle="info",
        width=10, command=refresh
    ).pack(side="left", padx=4)

    tb.Button(
        bar, text="RESET HARIAN", bootstyle="danger",
        width=14, command=reset_harian
    ).pack(side="left", padx=4)

    # ---------------------------------------------------------
    # TAB: ANTRIAN HARI INI & RIWAYAT PELAYANAN
    # ---------------------------------------------------------
    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=20, pady=(5, 15))

    tab_hari_ini = tb.Frame(notebook)
    tab_riwayat = tb.Frame(notebook)

    notebook.add(tab_hari_ini, text="  Antrian Hari Ini  ")
    notebook.add(tab_riwayat, text="  Riwayat Pelayanan  ")

    tabel = buat_tabel(
        tab_hari_ini,
        ("Nomor Antrian", "Nama Pasien", "Loket", "Waktu Daftar", "Status"),
        (170, 270, 150, 170, 150)
    )

    tabel_riwayat = buat_tabel(
        tab_riwayat,
        ("Nomor", "Nama Pasien", "Tanggal", "Loket", "Petugas",
         "Daftar", "Panggil", "Selesai"),
        (80, 200, 110, 100, 150, 90, 90, 90)
    )

    muat_loket()
    refresh()

    window.mainloop()


if __name__ == "__main__":
    buka_antrian()