"""Lapisan akses data (semua query SQL ada di sini)."""
import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

# Kolom standar untuk menampilkan antrian lengkap dengan nama loket & petugas
BASE_SELECT = """
    SELECT a.id_antrian,
           CONCAT(a.kode, LPAD(a.nomor, 3, '0')) AS nomor_antrian,
           a.tanggal, a.status,
           a.waktu_ambil, a.waktu_panggil, a.waktu_selesai,
           l.nama_loket, p.nama AS nama_petugas
    FROM antrian a
    LEFT JOIN loket   l ON l.id_loket   = a.id_loket
    LEFT JOIN petugas p ON p.id_petugas = a.id_petugas
"""


# ---------- Koneksi & helper -------------------------------------------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def test_connection():
    try:
        get_connection().close()
        return True, "Koneksi berhasil"
    except Error as e:
        return False, str(e)


def _query(sql, params=None, one=False, commit=False):
    """SELECT -> list/dict. INSERT/UPDATE/DELETE (commit=True) -> lastrowid."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        if commit:
            conn.commit()
            return cur.lastrowid
        return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()


# ---------- Autentikasi ------------------------------------------------
def login(username, password):
    return _query(
        "SELECT id_petugas, nama, username FROM petugas "
        "WHERE username=%s AND password=SHA2(%s,256) AND status='aktif'",
        (username, password), one=True)


# ---------- Fitur antrian ----------------------------------------------
def ambil_nomor(kode="A"):
    """Buat nomor baru hari ini. Dikunci agar 2 orang tidak dapat nomor sama."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT COALESCE(MAX(nomor),0) AS terakhir FROM antrian "
            "WHERE tanggal=CURDATE() AND kode=%s FOR UPDATE", (kode,))
        nomor = cur.fetchone()["terakhir"] + 1
        cur.execute(
            "INSERT INTO antrian (kode, nomor, tanggal, waktu_ambil, status) "
            "VALUES (%s, %s, CURDATE(), NOW(), 'menunggu')", (kode, nomor))
        conn.commit()
        return f"{kode}{nomor:03d}"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def panggil_berikutnya(id_loket, id_petugas):
    """Selesaikan antrian lama di loket ini, lalu panggil nomor menunggu berikutnya."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "UPDATE antrian SET status='selesai', waktu_selesai=NOW() "
            "WHERE tanggal=CURDATE() AND id_loket=%s AND status='dipanggil'", (id_loket,))
        cur.execute(
            "SELECT id_antrian FROM antrian WHERE tanggal=CURDATE() "
            "AND status='menunggu' ORDER BY nomor LIMIT 1 FOR UPDATE")
        row = cur.fetchone()
        if not row:
            conn.commit()
            return None
        cur.execute(
            "UPDATE antrian SET status='dipanggil', id_loket=%s, id_petugas=%s, "
            "waktu_panggil=NOW() WHERE id_antrian=%s",
            (id_loket, id_petugas, row["id_antrian"]))
        conn.commit()
        cur.execute(BASE_SELECT + " WHERE a.id_antrian=%s", (row["id_antrian"],))
        return cur.fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def selesaikan(id_loket):
    return _query(
        "UPDATE antrian SET status='selesai', waktu_selesai=NOW() "
        "WHERE tanggal=CURDATE() AND id_loket=%s AND status='dipanggil'",
        (id_loket,), commit=True)


def get_sedang_dilayani():
    return _query(BASE_SELECT + " WHERE a.tanggal=CURDATE() AND a.status='dipanggil' "
                                "ORDER BY a.waktu_panggil DESC")


def get_menunggu():
    return _query(BASE_SELECT + " WHERE a.tanggal=CURDATE() AND a.status='menunggu' "
                                "ORDER BY a.nomor")


def get_riwayat(tanggal, keyword=""):
    like = f"%{keyword}%"
    return _query(
        BASE_SELECT + " WHERE a.tanggal=%s AND (CONCAT(a.kode, LPAD(a.nomor,3,'0')) LIKE %s "
                      "OR a.status LIKE %s OR l.nama_loket LIKE %s OR p.nama LIKE %s) "
                      "ORDER BY a.nomor",
        (tanggal, like, like, like, like))


def get_statistik():
    rows = _query("SELECT status, COUNT(*) AS jml FROM antrian "
                  "WHERE tanggal=CURDATE() GROUP BY status")
    hasil = {"menunggu": 0, "dipanggil": 0, "selesai": 0, "batal": 0}
    for r in rows:
        hasil[r["status"]] = r["jml"]
    return hasil


def reset_harian():
    """Hapus semua antrian hari ini sehingga nomor kembali mulai dari 001."""
    return _query("DELETE FROM antrian WHERE tanggal=CURDATE()", commit=True)


# ---------- CRUD Loket -------------------------------------------------
def loket_list(only_active=False):
    sql = "SELECT id_loket, nama_loket, status FROM loket"
    if only_active:
        sql += " WHERE status='aktif'"
    return _query(sql + " ORDER BY id_loket")


def loket_add(d):
    return _query("INSERT INTO loket (nama_loket, status) VALUES (%s,%s)",
                  (d["nama_loket"], d["status"] or "aktif"), commit=True)


def loket_update(id_, d):
    return _query("UPDATE loket SET nama_loket=%s, status=%s WHERE id_loket=%s",
                  (d["nama_loket"], d["status"] or "aktif", id_), commit=True)


def loket_delete(id_):
    return _query("DELETE FROM loket WHERE id_loket=%s", (id_,), commit=True)


# ---------- CRUD Petugas -----------------------------------------------
def petugas_list():
    return _query("SELECT id_petugas, nama, username, status FROM petugas ORDER BY id_petugas")


def petugas_add(d):
    if not d.get("password"):
        raise ValueError("Password wajib diisi untuk petugas baru.")
    return _query("INSERT INTO petugas (nama, username, password, status) "
                  "VALUES (%s,%s,SHA2(%s,256),%s)",
                  (d["nama"], d["username"], d["password"], d["status"] or "aktif"),
                  commit=True)


def petugas_update(id_, d):
    if d.get("password"):
        return _query("UPDATE petugas SET nama=%s, username=%s, password=SHA2(%s,256), "
                      "status=%s WHERE id_petugas=%s",
                      (d["nama"], d["username"], d["password"], d["status"], id_), commit=True)
    return _query("UPDATE petugas SET nama=%s, username=%s, status=%s WHERE id_petugas=%s",
                  (d["nama"], d["username"], d["status"], id_), commit=True)


def petugas_delete(id_):
    return _query("DELETE FROM petugas WHERE id_petugas=%s", (id_,), commit=True)