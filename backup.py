"""Backup & restore database (Python murni, tanpa mysqldump).

Format backup = file .sql biasa (DROP/CREATE TABLE + INSERT), sehingga masih
bisa dibuka di phpMyAdmin atau editor teks.

Keamanan restore:
  1. File divalidasi LEBIH DAHULU (hanya perintah yang diizinkan, dan harus
     memuat semua tabel aplikasi) sebelum database disentuh.
  2. Backup pengaman otomatis dibuat sebelum data diganti.
  3. Bila restore gagal di tengah jalan, data lama dipulihkan dari backup pengaman.
"""
import os
import re
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import mysql.connector

from config import DB_CONFIG

TABEL_WAJIB = {"antrian", "loket", "petugas"}
# Saat dijadikan .exe (PyInstaller), __file__ menunjuk ke folder sementara yang
# dihapus setelah program ditutup. Karena itu pakai folder tempat .exe berada.
_BASE = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
         else os.path.dirname(os.path.abspath(__file__)))
FOLDER_BACKUP = os.path.join(_BASE, "backup")
_BARIS_PER_INSERT = 200
_PENANDA = "-- Backup Sistem Manajemen Antrian"


class BackupError(Exception):
    """Kesalahan backup/restore dengan pesan yang siap ditampilkan ke pengguna."""


# ------------------------------------------------------------ penulisan SQL
_ESC = str.maketrans({"\\": "\\\\", "'": "\\'", "\n": "\\n", "\r": "\\r",
                      "\0": "\\0", "\x1a": "\\Z"})


def _id(nama):
    return "`" + str(nama).replace("`", "``") + "`"


def literal(v):
    """Nilai Python -> literal SQL (satu baris, aman untuk teks multi-baris)."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, float):
        return "NULL" if v != v or v in (float("inf"), float("-inf")) else repr(v)
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex() if v else "''"
    if isinstance(v, datetime):
        return "'" + v.strftime("%Y-%m-%d %H:%M:%S" + (".%f" if v.microsecond else "")) + "'"
    if isinstance(v, date):
        return "'" + v.strftime("%Y-%m-%d") + "'"
    if isinstance(v, timedelta):
        total = int(v.total_seconds())
        tanda = "-" if total < 0 else ""
        h, sisa = divmod(abs(total), 3600)
        return f"'{tanda}{h:02d}:{sisa // 60:02d}:{sisa % 60:02d}'"
    if isinstance(v, time):
        return "'" + v.strftime("%H:%M:%S") + "'"
    return "'" + str(v).translate(_ESC) + "'"


def tulis_dump(conn, tulis):
    """Tulis seluruh isi database via callback tulis(str). Mengembalikan {tabel: jumlah_baris}."""
    jumlah = {}
    cur = conn.cursor()
    try:
        cur.execute("SELECT DATABASE()")
        nama_db = cur.fetchone()[0]
        tulis(f"{_PENANDA}\n-- Database : {nama_db}\n"
              f"-- Dibuat   : {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
        tulis("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n\n")

        cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tabel = sorted(r[0] for r in cur.fetchall())

        # Snapshot konsisten: semua tabel dibaca pada satu titik waktu.
        try:
            conn.start_transaction(consistent_snapshot=True)
        except Exception:
            pass

        for t in tabel:
            cur.execute(f"SHOW CREATE TABLE {_id(t)}")
            ddl = cur.fetchone()[1].replace("\n", " ")
            tulis(f"-- Tabel {t}\nDROP TABLE IF EXISTS {_id(t)};\n{ddl};\n")

            cur.execute(f"SELECT * FROM {_id(t)}")
            kolom = ", ".join(_id(d[0]) for d in cur.description)
            n = 0
            while True:
                baris = cur.fetchmany(_BARIS_PER_INSERT)
                if not baris:
                    break
                nilai = ",".join("(" + ",".join(literal(v) for v in b) + ")" for b in baris)
                tulis(f"INSERT INTO {_id(t)} ({kolom}) VALUES {nilai};\n")
                n += len(baris)
            tulis("\n")
            jumlah[t] = n
        tulis("SET FOREIGN_KEY_CHECKS=1;\n")
    finally:
        cur.close()
    return jumlah


# ----------------------------------------------------- pembacaan & validasi
def pecah_sql(teks):
    """Pecah teks SQL menjadi pernyataan; paham string, backtick, dan komentar."""
    bagian, awal, i, n, kutip = [], 0, 0, len(teks), None
    while i < n:
        c = teks[i]
        if kutip:
            if c == "\\" and kutip != "`":
                i += 2
            elif c == kutip:
                if teks[i + 1:i + 2] == kutip:      # kutip ganda = kutip literal
                    i += 2
                else:
                    kutip = None
                    i += 1
            else:
                i += 1
            continue
        if c in "'\"`":
            kutip = c
            i += 1
        elif c == "#" or (c == "-" and teks[i:i + 2] == "--"
                          and teks[i + 2:i + 3] in ("", " ", "\t", "\r", "\n")):
            bagian.append(teks[awal:i])
            j = teks.find("\n", i)
            i = n if j == -1 else j
            awal = i
        elif c == "/" and teks[i:i + 2] == "/*":
            bagian.append(teks[awal:i])
            j = teks.find("*/", i + 2)
            i = n if j == -1 else j + 2
            awal = i
        elif c == ";":
            stmt = ("".join(bagian) + teks[awal:i]).strip()
            bagian, awal = [], i + 1
            i += 1
            if stmt:
                yield stmt
        else:
            i += 1
    sisa = ("".join(bagian) + teks[awal:]).strip()
    if sisa:
        yield sisa


# Awalan perintah yang boleh dijalankan saat restore.
_BOLEH = re.compile(
    r"^(INSERT\s+INTO|CREATE\s+TABLE|DROP\s+TABLE\s+IF\s+EXISTS|DROP\s+TABLE|"
    r"ALTER\s+TABLE|LOCK\s+TABLES|UNLOCK\s+TABLES|START\s+TRANSACTION|COMMIT|SET)\b",
    re.IGNORECASE)
_LEWATI = re.compile(r"^(CREATE\s+DATABASE|USE)\b", re.IGNORECASE)
_SET_BERBAHAYA = re.compile(r"\b(GLOBAL|PERSIST|PERSIST_ONLY)\b|@@\s*(global|persist)",
                            re.IGNORECASE)
_NAMA_TABEL = re.compile(r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?",
                         re.IGNORECASE)


def baca_dan_validasi(path):
    """Baca file backup, validasi, dan kembalikan daftar pernyataan siap jalan."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            teks = f.read()
    except UnicodeDecodeError:
        raise BackupError("File bukan teks UTF-8, jadi bukan file backup yang valid.")
    except OSError as e:
        raise BackupError(f"File tidak dapat dibaca: {e}")

    hasil, dibuat = [], set()
    for stmt in pecah_sql(teks):
        if _LEWATI.match(stmt):
            continue
        if not _BOLEH.match(stmt):
            cuplikan = stmt[:60].replace("\n", " ")
            raise BackupError("File berisi perintah SQL yang tidak diizinkan untuk "
                              f"restore:\n\n{cuplikan}...")
        if stmt[:3].upper() == "SET" and _SET_BERBAHAYA.search(stmt):
            raise BackupError(f"Perintah SET berbahaya ditolak:\n\n{stmt[:60]}")
        m = _NAMA_TABEL.match(stmt)
        if m:
            dibuat.add(m.group(1).lower())
        hasil.append(stmt)

    kurang = TABEL_WAJIB - dibuat
    if kurang:
        raise BackupError("File ini bukan backup database antrian: tabel berikut tidak "
                          f"ditemukan: {', '.join(sorted(kurang))}.")
    return hasil


# ------------------------------------------------------------------ operasi
def _sambung():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        raise BackupError(f"Tidak dapat terhubung ke database: {e}")


def buat_backup(path=None):
    """Buat backup ke `path` (default: folder backup/ dengan nama bertanda waktu).

    Mengembalikan dict: path, ukuran (byte), tabel ({nama: jumlah baris}).
    """
    if path is None:
        os.makedirs(FOLDER_BACKUP, exist_ok=True)
        path = os.path.join(
            FOLDER_BACKUP, f"{DB_CONFIG['database']}_{datetime.now():%Y%m%d_%H%M%S}.sql")
    sementara = path + ".tmp"
    conn = _sambung()
    try:
        try:
            with open(sementara, "w", encoding="utf-8", newline="\n") as f:
                jumlah = tulis_dump(conn, f.write)
            baca_dan_validasi(sementara)          # pastikan hasilnya dapat direstore
            os.replace(sementara, path)
        except BackupError:
            raise
        except (OSError, mysql.connector.Error) as e:
            raise BackupError(f"Backup gagal: {e}")
    finally:
        conn.close()
        if os.path.exists(sementara):
            try:
                os.remove(sementara)
            except OSError:
                pass
    return {"path": path, "ukuran": os.path.getsize(path), "tabel": jumlah}


def _jalankan(pernyataan):
    conn = _sambung()
    try:
        cur = conn.cursor()
        cur.execute("SET NAMES utf8mb4")
        cur.execute("SET SESSION sql_mode = REPLACE(@@sql_mode, 'NO_BACKSLASH_ESCAPES', '')")
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for stmt in pernyataan:
            cur.execute(stmt)
        conn.commit()
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        cur.close()
    finally:
        conn.close()


def restore_backup(path):
    """Pulihkan database dari file backup. Mengembalikan path backup pengaman."""
    pernyataan = baca_dan_validasi(path)           # gagal di sini = DB belum disentuh

    os.makedirs(FOLDER_BACKUP, exist_ok=True)
    pengaman = buat_backup(os.path.join(
        FOLDER_BACKUP, f"pengaman_sebelum_restore_{datetime.now():%Y%m%d_%H%M%S}.sql"))["path"]

    try:
        _jalankan(pernyataan)
    except Exception as e:
        # DDL MySQL tidak bisa di-rollback; pulihkan dari backup pengaman.
        try:
            _jalankan(baca_dan_validasi(pengaman))
            pulih = "Data lama sudah dikembalikan seperti semula."
        except Exception as e2:
            pulih = (f"Pemulihan otomatis juga gagal ({e2}). Data lama aman di:\n{pengaman}")
        raise BackupError(f"Restore gagal: {e}\n\n{pulih}")
    return pengaman


def daftar_backup():
    """Daftar file .sql pada folder backup, terbaru di atas."""
    if not os.path.isdir(FOLDER_BACKUP):
        return []
    hasil = []
    for nama in os.listdir(FOLDER_BACKUP):
        p = os.path.join(FOLDER_BACKUP, nama)
        if nama.lower().endswith(".sql") and os.path.isfile(p):
            st = os.stat(p)
            hasil.append({"nama": nama, "path": p, "ukuran": st.st_size,
                          "waktu": datetime.fromtimestamp(st.st_mtime)})
    return sorted(hasil, key=lambda x: x["waktu"], reverse=True)


def fmt_ukuran(b):
    for sat in ("B", "KB", "MB", "GB"):
        if b < 1024 or sat == "GB":
            return f"{b:.0f} {sat}" if sat == "B" else f"{b:.1f} {sat}"
        b /= 1024