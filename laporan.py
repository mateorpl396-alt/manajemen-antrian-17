"""Pembuat laporan PDF (reportlab). Tidak bergantung pada Tkinter/database."""
from datetime import date, datetime
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from statistik import fmt_durasi, isi_hari_kosong, tgl_id

BIRU = colors.HexColor("#2c3e50")
HIJAU = colors.HexColor("#18bc9c")
ABU = colors.HexColor("#f2f4f6")
GARIS = colors.HexColor("#d5d9dd")
WARNA_STATUS = {"menunggu": "#b9770e", "dipanggil": "#2471a3",
                "selesai": "#117a65", "batal": "#c0392b"}

_ss = getSampleStyleSheet()
H_JUDUL = ParagraphStyle("judul", parent=_ss["Title"], fontSize=18, textColor=BIRU,
                         alignment=0, spaceAfter=2)
H_SUB = ParagraphStyle("sub", parent=_ss["Normal"], fontSize=10, textColor=colors.grey)
H_BAB = ParagraphStyle("bab", parent=_ss["Heading2"], fontSize=12, textColor=BIRU,
                       spaceBefore=14, spaceAfter=6)
P_SEL = ParagraphStyle("sel", parent=_ss["Normal"], fontSize=8, leading=10)
P_KOSONG = ParagraphStyle("kosong", parent=_ss["Normal"], fontSize=9,
                          textColor=colors.grey)


# ----------------------------------------------------------------- tabel
def _tabel(data, lebar, rata_tengah=(), zebra=True):
    t = Table(data, colWidths=lebar, repeatRows=1)
    gaya = [("BACKGROUND", (0, 0), (-1, 0), BIRU),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, GARIS),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if zebra:
        gaya.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ABU]))
    for k in rata_tengah:
        gaya.append(("ALIGN", (k, 0), (k, -1), "CENTER"))
    t.setStyle(TableStyle(gaya))
    return t


def _ringkasan(r):
    selesai_pct = f"{r['selesai'] * 100 / r['total']:.1f}%" if r["total"] else "-"
    sel = [["Total antrian", str(r["total"]), "Rata-rata waktu tunggu", fmt_durasi(r["rata_tunggu"])],
           ["Selesai", str(r["selesai"]), "Waktu tunggu terlama", fmt_durasi(r["tunggu_terlama"])],
           ["Dipanggil / dilayani", str(r["dipanggil"]), "Rata-rata durasi layanan", fmt_durasi(r["rata_layanan"])],
           ["Menunggu", str(r["menunggu"]), "Tingkat penyelesaian", selesai_pct],
           ["Batal", str(r["batal"]), "", ""]]
    t = Table(sel, colWidths=[4.2 * cm, 2.3 * cm, 5.2 * cm, 3.8 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, -1), ABU),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GARIS),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


# --------------------------------------------------------------- grafik
def _grafik_batang(judul, label, seri, nama_seri, warna, lebar=17 * cm, tinggi=5.2 * cm):
    d = Drawing(lebar, tinggi)
    d.add(String(0, tinggi - 10, judul, fontName="Helvetica-Bold", fontSize=9,
                 fillColor=BIRU))
    c = VerticalBarChart()
    c.x, c.y = 28, 28
    c.width, c.height = lebar - 40, tinggi - 55
    c.data = seri
    c.categoryAxis.categoryNames = label
    c.categoryAxis.labels.fontSize = 7
    if len(label) > 12:
        c.categoryAxis.labels.angle = 45
        c.categoryAxis.labels.boxAnchor = "ne"
        c.categoryAxis.labels.dy = -2
    c.valueAxis.valueMin = 0
    maks = max((v for s in seri for v in s), default=0)
    c.valueAxis.valueMax = max(maks + max(1, maks * 0.1), 1)
    c.valueAxis.valueStep = max(1, round(c.valueAxis.valueMax / 5))
    c.valueAxis.labels.fontSize = 7
    c.valueAxis.visibleGrid = True
    c.valueAxis.gridStrokeColor = GARIS
    c.barWidth = 6 if len(label) > 12 else 10
    c.groupSpacing = 6
    for i, wr in enumerate(warna):
        c.bars[i].fillColor = wr
        c.bars[i].strokeColor = None
    d.add(c)
    if len(seri) > 1:
        lg = Legend()
        lg.x, lg.y = lebar - 130, tinggi - 6
        lg.fontSize = 7
        lg.alignment = "right"
        lg.columnMaximum = 1
        lg.deltax = 55
        lg.colorNamePairs = list(zip(warna, nama_seri))
        d.add(lg)
    return d


def _data_periode(stat):
    """Per hari (maks 31 hari) atau per bulan untuk rentang yang lebih panjang."""
    hari = isi_hari_kosong(stat["per_hari"], stat["d1"], stat["d2"])
    if len(hari) <= 31:
        return [h["tanggal"].strftime("%d/%m") for h in hari], \
               [h["total"] for h in hari], [h["selesai"] for h in hari], "per hari"
    bulan = {}
    for h in hari:
        k = h["tanggal"].strftime("%m/%Y")
        t, s = bulan.get(k, (0, 0))
        bulan[k] = (t + h["total"], s + h["selesai"])
    return list(bulan), [v[0] for v in bulan.values()], \
           [v[1] for v in bulan.values()], "per bulan"


# ------------------------------------------------------ halaman & isi
def _halaman(canvas, doc):
    canvas.saveState()
    w, _ = A4
    canvas.setStrokeColor(GARIS)
    canvas.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1 * cm, "Sistem Manajemen Antrian")
    canvas.drawRightString(w - 2 * cm, 1 * cm, f"Halaman {doc.page}")
    canvas.restoreState()


def _tabel_kinerja(judul, baris, kolom_nama):
    isi = [[kolom_nama, "Dilayani", "Selesai", "Rata-rata layanan"]]
    for x in baris:
        isi.append([Paragraph(escape(str(x["nama"])), P_SEL), x["jumlah"], x["selesai"],
                    fmt_durasi(x["rata_layanan"])])
    return KeepTogether([Paragraph(judul, H_BAB),
                         _tabel(isi, [7 * cm, 3 * cm, 3 * cm, 4 * cm], rata_tengah=(1, 2, 3))])


def _paragraf_status(status):
    wr = WARNA_STATUS.get(status, "#000000")
    return Paragraph(f'<font color="{wr}"><b>{escape(str(status or "-"))}</b></font>', P_SEL)


def _jam(v):
    return v.strftime("%H:%M:%S") if isinstance(v, datetime) else "-"


def buat_laporan_pdf(path, stat, rincian=None, petugas="-", dicetak=None):
    """Tulis laporan PDF ke `path`.

    stat     : hasil statistik.ambil_statistik(d1, d2)
    rincian  : hasil statistik.ambil_rincian(d1, d2), atau None (tanpa tabel rincian)
    petugas  : nama pencetak laporan
    """
    d1, d2 = stat["d1"], stat["d2"]
    r = stat["ringkasan"]
    dicetak = dicetak or datetime.now()
    periode = tgl_id(d1) if d1 == d2 else f"{tgl_id(d1)}  s/d  {tgl_id(d2)}"

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2.2 * cm,
                            title="Laporan Manajemen Antrian", author=str(petugas))
    s = [Paragraph("LAPORAN MANAJEMEN ANTRIAN", H_JUDUL),
         Paragraph(f"Periode: <b>{periode}</b>", H_SUB),
         Paragraph(f"Dicetak: {dicetak.strftime('%d-%m-%Y %H:%M')} &nbsp;|&nbsp; "
                   f"oleh: {escape(str(petugas))}", H_SUB),
         Spacer(1, 6), Paragraph("Ringkasan", H_BAB), _ringkasan(r)]

    if r["total"] == 0:
        s += [Spacer(1, 14), Paragraph("Tidak ada data antrian pada periode ini.", P_KOSONG)]
        doc.build(s, onFirstPage=_halaman, onLaterPages=_halaman)
        return path

    label, total, selesai, satuan = _data_periode(stat)
    s += [Paragraph("Grafik", H_BAB),
          _grafik_batang(f"Jumlah antrian {satuan}", label, [total, selesai],
                         ["Total", "Selesai"], [BIRU, HIJAU])]
    if stat["per_jam"]:
        jam = list(range(min(stat["per_jam"]), max(stat["per_jam"]) + 1))
        s += [Spacer(1, 6),
              _grafik_batang("Jam pengambilan nomor", [f"{j:02d}" for j in jam],
                             [[stat["per_jam"].get(j, 0) for j in jam]], ["Jumlah"],
                             [colors.HexColor("#3498db")])]
    if stat["per_loket"]:
        s.append(_tabel_kinerja("Kinerja per Loket", stat["per_loket"], "Loket"))
    if stat["per_petugas"]:
        s.append(_tabel_kinerja("Kinerja per Petugas", stat["per_petugas"], "Petugas"))

    if rincian:
        s.append(Paragraph(f"Rincian Antrian ({len(rincian)} data)", H_BAB))
        isi = [["Nomor", "Tanggal", "Status", "Loket", "Petugas", "Ambil", "Panggil", "Selesai"]]
        for x in rincian:
            isi.append([x["nomor_antrian"],
                        x["tanggal"].strftime("%d-%m-%Y") if isinstance(x["tanggal"], date) else x["tanggal"],
                        _paragraf_status(x["status"]),
                        Paragraph(escape(x["nama_loket"] or "-"), P_SEL),
                        Paragraph(escape(x["nama_petugas"] or "-"), P_SEL),
                        _jam(x["waktu_ambil"]), _jam(x["waktu_panggil"]), _jam(x["waktu_selesai"])])
        s.append(_tabel(isi, [1.5 * cm, 2.1 * cm, 1.9 * cm, 1.9 * cm, 3.4 * cm,
                              2.0 * cm, 2.1 * cm, 2.1 * cm], rata_tengah=(0, 1, 5, 6, 7)))

    doc.build(s, onFirstPage=_halaman, onLaterPages=_halaman)
    return path