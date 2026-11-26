import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from database import koneksi, verifikasi_password, password_format_baru, hash_password
from antrian import buka_antrian


def main():
    hasil = {"petugas": None}

    login_window = tb.Window(themename="cosmo")
    login_window.title("Login Petugas")
    login_window.geometry("450x420")
    login_window.resizable(False, False)

    def proses_login(event=None):
        username = entry_username.get().strip()
        password = entry_password.get()

        if not username or not password:
            messagebox.showwarning(
                "Peringatan",
                "Username dan password harus diisi!"
            )
            return

        db = koneksi()

        if db is None:
            messagebox.showerror(
                "Error",
                "Database tidak terhubung!"
            )
            return

        cursor = None
        petugas = None

        try:
            cursor = db.cursor()

            cursor.execute("""
                SELECT id_petugas, nama_petugas, password
                FROM petugas
                WHERE username = %s
            """, (username,))

            baris = cursor.fetchone()

            if baris and verifikasi_password(password, baris[2]):
                petugas = (baris[0], baris[1])

                # Upgrade otomatis hash lama (SHA-256 polos) ke PBKDF2
                if not password_format_baru(baris[2]):
                    try:
                        cursor.execute(
                            "UPDATE petugas SET password = %s "
                            "WHERE id_petugas = %s",
                            (hash_password(password), baris[0])
                        )
                        db.commit()
                    except Exception:
                        db.rollback()  # kolom mungkin terlalu pendek; abaikan

        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        finally:
            if cursor:
                cursor.close()
            db.close()

        if petugas:
            hasil["petugas"] = petugas
            login_window.destroy()
        else:
            messagebox.showerror(
                "Login Gagal",
                "Username atau password salah!"
            )

    tb.Label(
        login_window,
        text="MANAJEMEN ANTRIAN",
        font=("Arial", 22, "bold")
    ).pack(pady=(45, 10))

    tb.Label(
        login_window,
        text="Silakan login sebagai petugas"
    ).pack(pady=5)

    tb.Label(
        login_window,
        text="Username"
    ).pack(anchor="w", padx=55, pady=(25, 5))

    entry_username = tb.Entry(login_window, width=42)
    entry_username.pack()

    tb.Label(
        login_window,
        text="Password"
    ).pack(anchor="w", padx=55, pady=(15, 5))

    entry_password = tb.Entry(login_window, width=42, show="*")
    entry_password.pack()

    tb.Button(
        login_window,
        text="LOGIN",
        bootstyle="primary",
        width=30,
        command=proses_login
    ).pack(pady=30)

    entry_username.bind("<Return>", lambda e: entry_password.focus())
    entry_password.bind("<Return>", proses_login)
    entry_username.focus()

    login_window.mainloop()

    # Jendela login sudah ditutup; buka jendela antrian sebagai window baru
    if hasil["petugas"]:
        buka_antrian(hasil["petugas"])


if __name__ == "__main__":
    main()