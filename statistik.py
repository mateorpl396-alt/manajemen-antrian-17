"""Query statistik & data laporan. Modul ini HANYA membaca database."""
from contextlib import contextmanager
from datetime import date, timedelta

import mysql.connector

from config import DB_CONFIG

HARI_STATUS = ("menunggu", "dipanggil", "selesai", "batal")
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

# Nomor tampil, mis. A001 (sama dengan format di aplikasi utama)
_NOMOR = "CONCAT(a.kode, LPAD(a.nomor, 3, '0'))"
_TUNGGU = "TIMESTAMPDIFF(SECOND, a.waktu_ambil, a.waktu_panggil)"
_LAYANAN = "TIMESTAMPDIFF(SECOND, a.waktu_panggil, a.waktu_selesai)"


# ---------------------------------------------------------------- helper
def tgl_id(d):
    """date -> '07 Januari 2026'."""
    return f"{d.day:02d} {BULAN[d.month - 1]} {d.year}"


def fmt_durasi(detik):
    """Detik -> '5 mnt 12 dtk' (None -> '-')."""
    if detik is None:
        return "-"
    detik = int(round(detik))
    m, s = divmod(detik, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h} jam {m} mnt"
    return f"{m} mnt {s:02d} dtk" if m else f"{s} dtk"


def rentang(nama, hari_ini=None):
    """Nama rentang cepat -> (tanggal_awal, tanggal_akhir)."""
    t = hari_ini or date.today()
    if nama == "Hari ini":
        return t, t
    if nama == "7 hari terakhir":
        return t - timedelta(days=6), t
    if nama == "30 hari terakhir":
        return t - timedelta(days=29), t
    if nama == "Bulan ini":
        return t.replace(day=1), t
    raise ValueError(f"Rentang tidak dikenal: {nama}")


def _num(v, tipe=float):
    return None if v is None else tipe(v)


@contextmanager
def _kursor():
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
        finally:
            cur.close()
    finally:
        conn.close()


# ----------------------------------------------------------- query utama
def ambil_statistik(d1, d2):
    """Statistik agregat antrian untuk tanggal d1..d2 (inklusif)."""
    p = (d1, d2)
    with _kursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*)                                   AS total,
                   COALESCE(SUM(a.status = 'menunggu'), 0)    AS menunggu,
                   COALESCE(SUM(a.status = 'dipanggil'), 0)   AS dipanggil,
                   COALESCE(SUM(a.status = 'selesai'), 0)     AS selesai,
                   COALESCE(SUM(a.status = 'batal'), 0)       AS batal,
                   AVG({_TUNGGU})                             AS rata_tunggu,
                   MAX({_TUNGGU})                             AS tunggu_terlama,
                   AVG({_LAYANAN})                            AS rata_layanan
            FROM antrian a WHERE a.tanggal BETWEEN %s AND %s""", p)
        r = cur.fetchone() or {}
        ringkasan = {k: int(r.get(k) or 0) for k in ("total", *HARI_STATUS)}
        for k in ("rata_tunggu", "tunggu_terlama", "rata_layanan"):
            ringkasan[k] = _num(r.get(k))

        cur.execute("""
            SELECT a.tanggal, COUNT(*) AS total,
                   COALESCE(SUM(a.status = 'selesai'), 0) AS selesai,
                   COALESCE(SUM(a.status = 'batal'), 0)   AS batal
            FROM antrian a WHERE a.tanggal BETWEEN %s AND %s
            GROUP BY a.tanggal ORDER BY a.tanggal""", p)
        per_hari = [{"tanggal": x["tanggal"], "total": int(x["total"]),
                     "selesai": int(x["selesai"]), "batal": int(x["batal"])}
                    for x in cur.fetchall()]

        cur.execute("""
            SELECT HOUR(a.waktu_ambil) AS jam, COUNT(*) AS jumlah
            FROM antrian a WHERE a.tanggal BETWEEN %s AND %s
            GROUP BY HOUR(a.waktu_ambil) ORDER BY jam""", p)
        per_jam = {int(x["jam"]): int(x["jumlah"]) for x in cur.fetchall()}

        cur.execute(f"""
            SELECT l.nama_loket AS nama, COUNT(*) AS jumlah,
                   COALESCE(SUM(a.status = 'selesai'), 0) AS selesai,
                   AVG({_LAYANAN}) AS rata_layanan
            FROM antrian a JOIN loket l ON l.id_loket = a.id_loket
            WHERE a.tanggal BETWEEN %s AND %s
            GROUP BY l.id_loket, l.nama_loket ORDER BY l.nama_loket""", p)
        per_loket = [{"nama": x["nama"], "jumlah": int(x["jumlah"]),
                      "selesai": int(x["selesai"]),
                      "rata_layanan": _num(x["rata_layanan"])}
                     for x in cur.fetchall()]

        cur.execute(f"""
            SELECT pt.nama AS nama, COUNT(*) AS jumlah,
                   COALESCE(SUM(a.status = 'selesai'), 0) AS selesai,
                   AVG({_LAYANAN}) AS rata_layanan
            FROM antrian a JOIN petugas pt ON pt.id_petugas = a.id_petugas
            WHERE a.tanggal BETWEEN %s AND %s
            GROUP BY pt.id_petugas, pt.nama ORDER BY pt.nama""", p)
        per_petugas = [{"nama": x["nama"], "jumlah": int(x["jumlah"]),
                        "selesai": int(x["selesai"]),
                        "rata_layanan": _num(x["rata_layanan"])}
                       for x in cur.fetchall()]

    return {"d1": d1, "d2": d2, "ringkasan": ringkasan, "per_hari": per_hari,
            "per_jam": per_jam, "per_loket": per_loket,
            "per_petugas": per_petugas}


def ambil_rincian(d1, d2):
    """Daftar antrian lengkap untuk tanggal d1..d2 (untuk tabel laporan)."""
    with _kursor() as cur:
        cur.execute(f"""
            SELECT {_NOMOR} AS nomor_antrian, a.tanggal, a.status,
                   l.nama_loket, pt.nama AS nama_petugas,
                   a.waktu_ambil, a.waktu_panggil, a.waktu_selesai
            FROM antrian a
            LEFT JOIN loket   l  ON l.id_loket     = a.id_loket
            LEFT JOIN petugas pt ON pt.id_petugas  = a.id_petugas
            WHERE a.tanggal BETWEEN %s AND %s
            ORDER BY a.tanggal, a.kode, a.nomor""", (d1, d2))
        return cur.fetchall()


def isi_hari_kosong(per_hari, d1, d2):
    """Lengkapi hari tanpa antrian dengan nol agar grafik tidak bolong."""
    ada = {r["tanggal"]: r for r in per_hari}
    hasil, t = [], d1
    while t <= d2:
        hasil.append(ada.get(t, {"tanggal": t, "total": 0, "selesai": 0, "batal": 0}))
        t += timedelta(days=1)
    return hasil