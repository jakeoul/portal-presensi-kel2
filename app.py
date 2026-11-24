import html
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import pymysql
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse


def get_db_config():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": parsed.username or "root",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/") or "portal_presensi",
        }
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "portal_presensi"),
    }


def get_connection():
    cfg = get_db_config()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kegiatan (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    judul VARCHAR(150) NOT NULL,
                    tanggal VARCHAR(60) NOT NULL,
                    lokasi VARCHAR(150) NOT NULL,
                    deskripsi TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS presensi (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    kegiatan_id INT NOT NULL,
                    nama_anggota VARCHAR(120) NOT NULL,
                    divisi VARCHAR(100) NOT NULL,
                    status ENUM('Hadir', 'Izin') NOT NULL DEFAULT 'Hadir',
                    catatan VARCHAR(255) DEFAULT '',
                    waktu_absen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_kegiatan
                        FOREIGN KEY (kegiatan_id) REFERENCES kegiatan(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
            cur.execute("SELECT COUNT(*) AS total FROM kegiatan")
            row = cur.fetchone()
            if row and row["total"] == 0:
                cur.execute(
                    """
                    INSERT INTO kegiatan (judul, tanggal, lokasi, deskripsi) VALUES
                    ('Rapat Koordinasi Program Kerja', 'Sabtu, 21 Nov 2026 • 09:00 WIB', 'Aula Sekretariat / Ruang OSIS', 'Pembahasan agenda kegiatan bulanan dan pembagian panitia.'),
                    ('Kerja Bakti & Bakti Sosial Lingkungan', 'Minggu, 29 Nov 2026 • 07:30 WIB', 'Balai Warga RW 04', 'Kegiatan bersih lingkungan bersama anggota Karang Taruna dan warga.');
                    """
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Portal Presensi & Kegiatan Organisasi", lifespan=lifespan)


def render_page(kegiatan_list, presensi_list, msg: str = "") -> str:
    alert_html = ""
    if msg:
        alert_html = f"""
        <div class="mb-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800 font-medium">
            {html.escape(msg)}
        </div>
        """

    options_html = ""
    kegiatan_cards = ""
    for k in kegiatan_list:
        kid = k["id"]
        judul = html.escape(k["judul"])
        tanggal = html.escape(k["tanggal"])
        lokasi = html.escape(k["lokasi"])
        deskripsi = html.escape(k.get("deskripsi") or "")
        jumlah_hadir = k.get("total_hadir", 0)

        options_html += f'<option value="{kid}">{judul} ({tanggal})</option>'
        kegiatan_cards += f"""
        <div class="rounded-2xl bg-white p-4 shadow-sm border border-slate-200">
            <div class="flex items-start justify-between gap-2">
                <h3 class="font-semibold text-slate-900 text-base">{judul}</h3>
                <span class="shrink-0 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
                    {jumlah_hadir} Hadir
                </span>
            </div>
            <p class="mt-1 text-xs text-slate-500">Waktu: {tanggal}</p>
            <p class="text-xs text-slate-500">Lokasi: {lokasi}</p>
            {f'<p class="mt-2 text-sm text-slate-600">{deskripsi}</p>' if deskripsi else ''}
        </div>
        """

    if not kegiatan_cards:
        kegiatan_cards = '<p class="text-sm text-slate-500">Belum ada jadwal kegiatan.</p>'

    presensi_rows = ""
    for p in presensi_list:
        nama = html.escape(p["nama_anggota"])
        divisi = html.escape(p["divisi"])
        keg = html.escape(p["judul_kegiatan"])
        status = html.escape(p["status"])
        waktu = html.escape(str(p["waktu_absen"]))
        badge = (
            "bg-emerald-100 text-emerald-800"
            if status == "Hadir"
            else "bg-amber-100 text-amber-800"
        )
        presensi_rows += f"""
        <tr class="border-b border-slate-100 last:border-0">
            <td class="py-2.5 pr-3">
                <div class="font-medium text-slate-900">{nama}</div>
                <div class="text-xs text-slate-500">{divisi} • {keg}</div>
            </td>
            <td class="py-2.5 px-2 text-right">
                <span class="inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold {badge}">{status}</span>
                <div class="text-[11px] text-slate-400 mt-0.5">{waktu[:16]}</div>
            </td>
        </tr>
        """

    if not presensi_rows:
        presensi_rows = '<tr><td class="py-4 text-center text-sm text-slate-500">Belum ada data presensi.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Portal Presensi & Kegiatan Organisasi</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen">
    <header class="bg-slate-900 text-white py-5 px-4 shadow-sm">
        <div class="max-w-xl mx-auto">
            <p class="text-xs uppercase tracking-wider text-blue-300 font-semibold">Kelompok 2 • Dokploy PaaS</p>
            <h1 class="text-xl font-bold mt-0.5">Portal Informasi & Presensi</h1>
            <p class="text-xs text-slate-300 mt-1">OSIS / Karang Taruna — Akses Cepat via Ponsel</p>
        </div>
    </header>

    <main class="max-w-xl mx-auto px-4 py-5 space-y-6">
        {alert_html}

        <section class="rounded-2xl bg-white p-5 shadow-sm border border-slate-200">
            <h2 class="text-base font-bold text-slate-900 mb-3">Isi Presensi Kehadiran</h2>
            <form method="post" action="/presensi" class="space-y-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Pilih Kegiatan</label>
                    <select name="kegiatan_id" required class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                        {options_html}
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Nama Lengkap Anggota</label>
                    <input type="text" name="nama_anggota" required placeholder="Contoh: Zaki Rojabi" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Divisi / Kelas</label>
                        <input type="text" name="divisi" required placeholder="Sekbid 10 / XII SIJA" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Status</label>
                        <select name="status" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="Hadir">Hadir</option>
                            <option value="Izin">Izin</option>
                        </select>
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Catatan (Opsional)</label>
                    <input type="text" name="catatan" placeholder="Keterangan jika izin atau terlambat" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <button type="submit" class="w-full rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 text-sm transition">
                    Kirim Presensi
                </button>
            </form>
        </section>

        <section class="space-y-3">
            <h2 class="text-base font-bold text-slate-900">Jadwal Kegiatan Organisasi</h2>
            {kegiatan_cards}
        </section>

        <section class="rounded-2xl bg-white p-5 shadow-sm border border-slate-200">
            <h2 class="text-base font-bold text-slate-900 mb-3">Rekap Presensi Terbaru</h2>
            <table class="w-full text-sm">
                <tbody>{presensi_rows}</tbody>
            </table>
        </section>

        <section class="rounded-2xl bg-white p-5 shadow-sm border border-slate-200">
            <h2 class="text-base font-bold text-slate-900 mb-3">Tambah Kegiatan (Pengurus)</h2>
            <form method="post" action="/kegiatan" class="space-y-3">
                <input type="text" name="judul" required placeholder="Judul Kegiatan" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" />
                <input type="text" name="tanggal" required placeholder="Hari, Tanggal & Jam (mis: Sabtu, 5 Des 2026 • 09:00)" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" />
                <input type="text" name="lokasi" required placeholder="Lokasi Kegiatan" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm" />
                <textarea name="deskripsi" rows="2" placeholder="Deskripsi singkat kegiatan" class="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"></textarea>
                <button type="submit" class="w-full rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-semibold py-2.5 text-sm transition">
                    Simpan Jadwal Kegiatan
                </button>
            </form>
        </section>
    </main>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home(msg: str = ""):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT k.*,
                       SUM(CASE WHEN p.status = 'Hadir' THEN 1 ELSE 0 END) AS total_hadir
                FROM kegiatan k
                LEFT JOIN presensi p ON p.kegiatan_id = k.id
                GROUP BY k.id
                ORDER BY k.id DESC
                """
            )
            kegiatan_list = cur.fetchall()

            cur.execute(
                """
                SELECT p.*, k.judul AS judul_kegiatan
                FROM presensi p
                JOIN kegiatan k ON k.id = p.kegiatan_id
                ORDER BY p.id DESC
                LIMIT 20
                """
            )
            presensi_list = cur.fetchall()

    return render_page(kegiatan_list, presensi_list, msg=msg)


@app.post("/presensi")
def submit_presensi(
    kegiatan_id: int = Form(...),
    nama_anggota: str = Form(...),
    divisi: str = Form(...),
    status: str = Form("Hadir"),
    catatan: str = Form(""),
):
    safe_status = "Izin" if status == "Izin" else "Hadir"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO presensi (kegiatan_id, nama_anggota, divisi, status, catatan)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (kegiatan_id, nama_anggota.strip(), divisi.strip(), safe_status, catatan.strip()),
            )
    return RedirectResponse(url="/?msg=Presensi+berhasil+dicatat!", status_code=303)


@app.post("/kegiatan")
def create_kegiatan(
    judul: str = Form(...),
    tanggal: str = Form(...),
    lokasi: str = Form(...),
    deskripsi: str = Form(""),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kegiatan (judul, tanggal, lokasi, deskripsi)
                VALUES (%s, %s, %s, %s)
                """,
                (judul.strip(), tanggal.strip(), lokasi.strip(), deskripsi.strip()),
            )
    return RedirectResponse(url="/?msg=Kegiatan+baru+berhasil+ditambahkan!", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok"}