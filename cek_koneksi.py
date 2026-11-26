from database import koneksi


def cek():
    db = koneksi()

    if db and db.is_connected():
        print("BERHASIL! Database terhubung.")
        db.close()
    else:
        print("GAGAL! Database belum terhubung.")


if __name__ == "__main__":
    cek()