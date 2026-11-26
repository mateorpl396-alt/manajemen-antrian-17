import mysql.connector
import hashlib
from getpass import getpass

# Membuat akun petugas pertama
nama = input("Nama petugas: ")
username = input("Username: ")
password = getpass("Password: ")

password_hash = hashlib.sha256(
    password.encode()
).hexdigest()

try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_manajemen_antrian"
    )

    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO petugas
        (nama_petugas, username, password)
        VALUES (%s, %s, %s)
    """, (nama, username, password_hash))

    db.commit()

    print("Akun petugas berhasil dibuat!")

    cursor.close()
    db.close()

except mysql.connector.Error as e:
    print("Gagal membuat akun:", e)
