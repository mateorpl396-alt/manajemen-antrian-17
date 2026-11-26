"""Konfigurasi koneksi MySQL (XAMPP default: user root, password kosong)."""

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "db_antrian",
    # Pakai driver Python murni agar aman saat dijadikan .exe (PyInstaller).
    "use_pure": True,
}