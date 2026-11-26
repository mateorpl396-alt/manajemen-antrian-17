"""Penggambar grafik dashboard (matplotlib). Tidak bergantung pada Tkinter."""
from matplotlib.ticker import MaxNLocator

from statistik import isi_hari_kosong

WARNA_DEFAULT = {"bg": "#ffffff", "fg": "#212529", "border": "#dee2e6",
                 "primary": "#2c3e50", "success": "#18bc9c",
                 "info": "#3498db", "warning": "#f39c12", "danger": "#e74c3c"}


def _warna(c):
    """Ambil warna dari objek tema ttkbootstrap (atau dict); fallback default."""
    hasil = dict(WARNA_DEFAULT)
    for k in hasil:
        try:
            v = c[k] if isinstance(c, dict) else getattr(c, k)
            if v:
                hasil[k] = v
        except Exception:
            pass
    return hasil


def _gaya(ax, w, judul):
    ax.set_facecolor(w["bg"])
    ax.set_title(judul, fontsize=10, fontweight="bold", color=w["fg"], loc="left")
    ax.tick_params(colors=w["fg"], labelsize=8)
    for sisi in ("top", "right"):
        ax.spines[sisi].set_visible(False)
    for sisi in ("left", "bottom"):
        ax.spines[sisi].set_color(w["border"])
    ax.yaxis.grid(True, color=w["border"], linewidth=0.6)
    ax.set_axisbelow(True)


def _kosong(ax, w, judul):
    ax.set_facecolor(w["bg"])
    ax.set_title(judul, fontsize=10, fontweight="bold", color=w["fg"], loc="left")
    ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center",
            color=w["fg"], alpha=0.6, transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _bilangan_bulat(ax, sumbu="y"):
    getattr(ax, f"{sumbu}axis").set_major_locator(MaxNLocator(integer=True))


def gambar_dashboard(fig, stat, warna=None):
    """Gambar 4 grafik pada Figure `fig` dari hasil statistik.ambil_statistik()."""
    w = _warna(warna)
    fig.clear()
    fig.set_facecolor(w["bg"])
    ax1, ax2, ax3, ax4 = fig.subplots(2, 2).flatten()
    r = stat["ringkasan"]

    # 1) Jumlah antrian per hari ------------------------------------------
    hari = isi_hari_kosong(stat["per_hari"], stat["d1"], stat["d2"])
    if r["total"] == 0:
        _kosong(ax1, w, "Antrian per Hari")
    else:
        _gaya(ax1, w, "Antrian per Hari")
        x = list(range(len(hari)))
        lebar = 0.4
        ax1.bar([i - lebar / 2 for i in x], [h["total"] for h in hari],
                lebar, color=w["primary"], label="Total")
        ax1.bar([i + lebar / 2 for i in x], [h["selesai"] for h in hari],
                lebar, color=w["success"], label="Selesai")
        langkah = max(1, len(hari) // 8)
        ax1.set_xticks(x[::langkah])
        ax1.set_xticklabels([h["tanggal"].strftime("%d/%m") for h in hari][::langkah])
        _bilangan_bulat(ax1)
        ax1.legend(fontsize=8, frameon=False, labelcolor=w["fg"])

    # 2) Komposisi status ---------------------------------------------------
    ax2.set_facecolor(w["bg"])
    ax2.set_title("Status Antrian", fontsize=10, fontweight="bold",
                  color=w["fg"], loc="left")
    warna_status = {"menunggu": w["warning"], "dipanggil": w["info"],
                    "selesai": w["success"], "batal": w["danger"]}
    item = [(k, r[k]) for k in warna_status if r[k] > 0]
    if not item:
        _kosong(ax2, w, "Status Antrian")
    else:
        wedges, _ = ax2.pie([v for _, v in item],
                            colors=[warna_status[k] for k, _ in item],
                            startangle=90, counterclock=False,
                            wedgeprops={"width": 0.42, "edgecolor": w["bg"]})
        ax2.text(0, 0, str(r["total"]), ha="center", va="center",
                 fontsize=18, fontweight="bold", color=w["fg"])
        ax2.legend(wedges, [f"{k.capitalize()} ({v})" for k, v in item],
                   loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8,
                   frameon=False, labelcolor=w["fg"])

    # 3) Jam sibuk ----------------------------------------------------------
    if not stat["per_jam"]:
        _kosong(ax3, w, "Jam Pengambilan Nomor")
    else:
        _gaya(ax3, w, "Jam Pengambilan Nomor")
        jam = list(range(min(stat["per_jam"]), max(stat["per_jam"]) + 1))
        ax3.bar(jam, [stat["per_jam"].get(j, 0) for j in jam], 0.7, color=w["info"])
        ax3.set_xticks(jam)
        ax3.set_xticklabels([f"{j:02d}" for j in jam])
        _bilangan_bulat(ax3)

    # 4) Beban per loket ----------------------------------------------------
    if not stat["per_loket"]:
        _kosong(ax4, w, "Antrian Dilayani per Loket")
    else:
        _gaya(ax4, w, "Antrian Dilayani per Loket")
        ax4.yaxis.grid(False)
        ax4.xaxis.grid(True, color=w["border"], linewidth=0.6)
        nama = [x["nama"] for x in stat["per_loket"]]
        nilai = [x["jumlah"] for x in stat["per_loket"]]
        bars = ax4.barh(nama, nilai, color=w["primary"])
        ax4.invert_yaxis()
        ax4.bar_label(bars, padding=3, fontsize=8, color=w["fg"])
        ax4.margins(x=0.15)
        _bilangan_bulat(ax4, "x")