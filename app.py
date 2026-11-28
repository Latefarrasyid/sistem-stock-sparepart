import io
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(
    page_title="Sistem Stock Sparepart",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="auto",
)

# =========================================================
# KONFIGURASI
# =========================================================
def get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return os.getenv(key, default).strip()


GAS_URL = get_secret("GAS_URL")
API_KEY = get_secret("API_KEY")
ADMIN_USER = get_secret("ADMIN_USER", "admin")
ADMIN_PASS = get_secret("ADMIN_PASS", "admin123")
VIEWER_USER = get_secret("VIEWER_USER", "user")
VIEWER_PASS = get_secret("VIEWER_PASS", "user123")

KRITIS_MAX = 2
NUM_COLS = ["STOCK AWAL", "KELUAR", "MASUK", "PRICELIST", "NOMINAL TOTAL", "STOCK AKHIR"]

# Palet warna ala SB Admin 2
C_PRIMARY, C_SUCCESS, C_INFO, C_WARNING, C_DANGER = "#4e73df", "#1cc88a", "#36b9cc", "#f6c23e", "#e74a3b"
PALETTE = [C_PRIMARY, C_SUCCESS, C_INFO, C_WARNING, C_DANGER, "#858796", "#6f42c1", "#fd7e14", "#20c9a6", "#e83e8c"]


def is_valid_gas_url(url: str) -> bool:
    return url.startswith("https://script.google.com/macros/s/") and url.endswith("/exec")


def now_wib() -> datetime:
    return datetime.utcnow() + timedelta(hours=7)


def rp(x) -> str:
    try:
        return "Rp " + f"{float(x):,.0f}".replace(",", ".")
    except Exception:
        return "Rp 0"


def num(x) -> str:
    try:
        return f"{int(float(x)):,}".replace(",", ".")
    except Exception:
        return "0"


# =========================================================
# TAMPILAN (CSS ala SB Admin 2, responsif)
# =========================================================
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Nunito', sans-serif; }}
.stApp {{ background: #f8f9fc; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 1rem 1.5rem 3rem 1.5rem; max-width: 1500px; }}

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {C_PRIMARY} 10%, #224abe 100%);
  border-right: none;
}}
section[data-testid="stSidebar"] * {{ color: #fff; }}
.sb-brand {{ display:flex; align-items:center; gap:.6rem; padding:.4rem .2rem 1rem;
  border-bottom:1px solid rgba(255,255,255,.2); margin-bottom:1rem; }}
.sb-brand .ic {{ font-size:1.8rem; transform: rotate(-12deg); }}
.sb-brand .tx {{ font-weight:800; font-size:1.05rem; letter-spacing:.05rem; text-transform:uppercase; line-height:1.1; }}
.sb-brand small {{ display:block; font-weight:600; opacity:.7; font-size:.65rem; letter-spacing:.1rem; }}
.sb-user {{ background:rgba(255,255,255,.12); border-radius:.6rem; padding:.7rem .8rem;
  margin-bottom:1rem; display:flex; align-items:center; gap:.7rem; }}
.sb-user .av {{ width:38px; height:38px; border-radius:50%; background:#fff; color:{C_PRIMARY} !important;
  display:flex; align-items:center; justify-content:center; font-weight:800; }}
.sb-user .av {{ color:{C_PRIMARY}; }}
.sb-user b {{ display:block; font-size:.9rem; }}
.sb-user span {{ font-size:.7rem; opacity:.8; text-transform:uppercase; letter-spacing:.06rem; }}
.sb-label {{ font-size:.65rem; font-weight:800; text-transform:uppercase; letter-spacing:.1rem;
  opacity:.6; margin:.6rem 0 .3rem .3rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:.15rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
  padding:.7rem .9rem; border-radius:.5rem; width:100%; cursor:pointer; transition:.15s;
  margin:0; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{ background:rgba(255,255,255,.15); }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {{ display:none; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label p {{ font-weight:700; font-size:.92rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
  background:#fff; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {{ color:{C_PRIMARY} !important; }}
section[data-testid="stSidebar"] .stButton > button {{
  background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.3); color:#fff; width:100%;
  border-radius:.5rem; font-weight:700; }}
section[data-testid="stSidebar"] .stButton > button:hover {{ background:#fff; color:{C_PRIMARY}; }}

/* ---------- TOPBAR ---------- */
.topbar {{ background:#fff; border-radius:.75rem; box-shadow:0 .15rem 1.75rem rgba(58,59,69,.12);
  padding:.9rem 1.3rem; margin-bottom:1.3rem; display:flex; justify-content:space-between;
  align-items:center; flex-wrap:wrap; gap:.6rem; }}
.topbar h1 {{ font-size:1.35rem; font-weight:800; margin:0; color:#5a5c69; }}
.topbar .crumb {{ font-size:.75rem; color:#858796; }}
.topbar .chip {{ background:#eaecf4; border-radius:2rem; padding:.35rem .9rem; font-size:.78rem;
  font-weight:700; color:#5a5c69; margin-left:.4rem; display:inline-block; }}
.topbar .chip.role {{ background:{C_PRIMARY}; color:#fff; }}

/* ---------- KPI CARDS ---------- */
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; margin-bottom:1.3rem; }}
.kpi {{ background:#fff; border-radius:.75rem; padding:1.1rem 1.25rem; border-left:.3rem solid var(--c);
  box-shadow:0 .15rem 1.75rem rgba(58,59,69,.12); display:flex; justify-content:space-between; align-items:center; }}
.kpi .lb {{ font-size:.7rem; font-weight:800; text-transform:uppercase; color:var(--c); letter-spacing:.05rem; }}
.kpi .vl {{ font-size:1.45rem; font-weight:800; color:#5a5c69; margin-top:.2rem; word-break:break-word; }}
.kpi .ic {{ font-size:2rem; opacity:.25; }}

/* ---------- PANEL ---------- */
.panel-title {{ font-weight:800; color:{C_PRIMARY}; font-size:1rem; margin:.2rem 0 .4rem; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ background:#fff; border-radius:.75rem;
  box-shadow:0 .15rem 1.75rem rgba(58,59,69,.08); border:none; }}
.partcard {{ background:linear-gradient(135deg,#f0f4ff,#fff); border:1px solid #d9e2ff; border-radius:.75rem;
  padding:1rem 1.2rem; margin:.6rem 0 1rem; }}
.partcard h3 {{ margin:0 0 .6rem; color:{C_PRIMARY}; font-size:1.1rem; font-weight:800; }}
.partcard .g {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.6rem; }}
.partcard .g div small {{ display:block; color:#858796; font-size:.68rem; font-weight:800; text-transform:uppercase; }}
.partcard .g div b {{ color:#5a5c69; }}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius:.5rem; font-weight:700; }}
.stFormSubmitButton > button[kind="primary"], .stButton > button[kind="primary"] {{
  background:{C_PRIMARY}; border-color:{C_PRIMARY}; }}
.login-wrap {{ text-align:center; margin:3vh 0 1rem; }}
.login-wrap .logo {{ font-size:3.2rem; }}
.login-wrap h2 {{ font-weight:800; color:#5a5c69; margin:.3rem 0; }}
.login-wrap p {{ color:#858796; }}

@media (max-width: 768px) {{
  .block-container {{ padding:.6rem .7rem 3rem; }}
  .topbar h1 {{ font-size:1.1rem; }}
  .kpi .vl {{ font-size:1.2rem; }}
  .kpi-grid {{ grid-template-columns:1fr 1fr; gap:.6rem; }}
  .kpi {{ padding:.8rem; }}
  .kpi .ic {{ display:none; }}
}}
@media (max-width: 480px) {{ .kpi-grid {{ grid-template-columns:1fr; }} }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =========================================================
# SWEETALERT (notifikasi)
# =========================================================
def swal(icon: str, title: str, text: str = ""):
    """Tampilkan SweetAlert2 (icon: success|error|warning|info|question)."""
    components.html(
        f"""
<script>
(function() {{
  const p = window.parent, d = p.document;
  const opts = {{ icon: {json.dumps(icon)}, title: {json.dumps(title)}, text: {json.dumps(text)},
    confirmButtonColor: '{C_PRIMARY}', confirmButtonText: 'OK' }};
  function go() {{ p.Swal.fire(opts); }}
  if (p.Swal) {{ go(); }}
  else {{
    const s = d.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
    s.onload = go; d.head.appendChild(s);
  }}
}})();
</script>
""",
        height=0,
    )


def flash(icon: str, title: str, text: str = ""):
    """Simpan notifikasi agar tampil setelah st.rerun()."""
    st.session_state["_flash"] = (icon, title, text)


def show_flash():
    f = st.session_state.pop("_flash", None)
    if f:
        swal(*f)


# =========================================================
# LOGIN
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = ""


def login_page():
    st.markdown(
        """<style>.stApp{background:linear-gradient(135deg,#4e73df 0%,#224abe 100%);}
        section[data-testid="stSidebar"]{display:none;}
        .login-wrap h2,.login-wrap p{color:#fff !important;}</style>
        <div class="login-wrap"><div class="logo">📦</div><h2>Sistem Stock Sparepart</h2>
        <p>Silakan login untuk melanjutkan</p></div>""",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        with st.container(border=True):
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Masukkan username")
                password = st.text_input("Password", type="password", placeholder="Masukkan password")
                ok = st.form_submit_button("Masuk", use_container_width=True, type="primary")
            if ok:
                if username == ADMIN_USER and password == ADMIN_PASS:
                    st.session_state.update(logged_in=True, role="admin", username=username)
                    flash("success", "Login berhasil", f"Selamat datang, {username}!")
                    st.rerun()
                elif username == VIEWER_USER and password == VIEWER_PASS:
                    st.session_state.update(logged_in=True, role="user", username=username)
                    flash("success", "Login berhasil", f"Selamat datang, {username}!")
                    st.rerun()
                else:
                    swal("error", "Login gagal", "Username atau password salah.")


if not is_valid_gas_url(GAS_URL):
    st.error("`GAS_URL` belum dikonfigurasi atau tidak berakhiran `/exec`.")
    st.info("Tambahkan `GAS_URL` pada menu **Settings > Secrets** di Streamlit Cloud.")
    st.stop()

if not st.session_state.logged_in:
    login_page()
    st.stop()


# =========================================================
# KOMUNIKASI KE GOOGLE APPS SCRIPT
# =========================================================
@st.cache_data(ttl=5)
def fetch_stock() -> pd.DataFrame:
    params = {"action": "getStock"}
    if API_KEY:
        params["api_key"] = API_KEY
    resp = requests.get(GAS_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(data.get("message", "Gagal mengambil data stok"))
    df = pd.DataFrame(data)
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=5)
def fetch_history(tx_type: str) -> pd.DataFrame:
    params = {"action": "getHistory", "type": tx_type}
    if API_KEY:
        params["api_key"] = API_KEY
    resp = requests.get(GAS_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(data.get("message", "Gagal mengambil riwayat"))
    return pd.DataFrame(data)


def post_payload(payload: dict) -> dict:
    if API_KEY:
        payload["api_key"] = API_KEY
    resp = requests.post(GAS_URL, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if isinstance(result, dict) and result.get("status") == "error":
        raise RuntimeError(result.get("message", "Gagal memproses data"))
    return result


# =========================================================
# EXPORT EXCEL & PDF
# =========================================================
def to_excel(sheets: dict) -> bytes:
    """sheets: {nama_sheet: DataFrame}"""
    from openpyxl.styles import Alignment, Font, PatternFill

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=name[:31])
            ws = writer.sheets[name[:31]]
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="4E73DF")
                c.alignment = Alignment(horizontal="center", vertical="center")
            for i, col in enumerate(frame.columns, start=1):
                width = max([len(str(col))] + [len(str(v)) for v in frame[col].head(300)]) + 3
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(width, 45)
            ws.freeze_panes = "A2"
    return buf.getvalue()


def to_pdf(title: str, frame: pd.DataFrame, money_cols=(), int_cols=(), total_row: dict = None, subtitle: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1 * cm, title=title)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>{title}</b>", styles["Title"]),
        Paragraph(f"{subtitle} Dicetak: {now_wib():%d-%m-%Y %H:%M} WIB", styles["Normal"]),
        Spacer(1, 0.4 * cm),
    ]
    cell = styles["BodyText"].clone("cell")
    cell.fontSize = 7
    cell.leading = 8.5

    def fmt(col, v):
        if col in money_cols:
            return rp(v)
        if col in int_cols:
            return num(v)
        return Paragraph(str(v), cell)

    header = [str(c) for c in frame.columns]
    rows = [[fmt(c, v) for c, v in zip(frame.columns, r)] for r in frame.itertuples(index=False)]
    data = [header] + rows
    if total_row:
        data.append([fmt(c, total_row.get(c, "")) if c in total_row else "" for c in frame.columns])

    tbl = Table(data, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(C_PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d3e2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, c in enumerate(frame.columns):
        if c in money_cols or c in int_cols:
            style.append(("ALIGN", (i, 0), (i, -1), "RIGHT"))
    if total_row:
        style += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                  ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eaecf4"))]
    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()


def export_buttons(label: str, frame: pd.DataFrame, title: str, money_cols=(), int_cols=(), total_row=None, key=""):
    stamp = now_wib().strftime("%Y%m%d_%H%M")
    c1, c2, _ = st.columns([1, 1, 3])
    c1.download_button("📗 Cetak Excel", to_excel({label: frame}), f"{label}_{stamp}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True, key=f"x_{key}")
    c2.download_button("📕 Cetak PDF", to_pdf(title, frame, money_cols, int_cols, total_row), f"{label}_{stamp}.pdf",
                       "application/pdf", use_container_width=True, key=f"p_{key}")


# =========================================================
# KOMPONEN UI
# =========================================================
def topbar(title: str, icon: str):
    st.markdown(
        f"""<div class="topbar"><div><h1>{icon} {title}</h1>
        <div class="crumb">Sistem Stock Sparepart &nbsp;/&nbsp; {title}</div></div>
        <div><span class="chip">📅 {now_wib():%d %b %Y, %H:%M} WIB</span>
        <span class="chip role">👤 {st.session_state.username} · {st.session_state.role.upper()}</span></div></div>""",
        unsafe_allow_html=True,
    )


def kpi_cards(items):
    html = '<div class="kpi-grid">'
    for label, value, icon, color in items:
        html += (f'<div class="kpi" style="--c:{color}"><div><div class="lb">{label}</div>'
                 f'<div class="vl">{value}</div></div><div class="ic">{icon}</div></div>')
    st.markdown(html + "</div>", unsafe_allow_html=True)


def style_fig(fig, height=340):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Nunito", color="#5a5c69"),
                      legend=dict(orientation="h", y=-0.2))
    return fig


def goto(page: str, **state):
    st.session_state.menu = page
    for k, v in state.items():
        st.session_state[k] = v


def load_stock():
    try:
        return fetch_stock()
    except Exception as e:
        swal("error", "Gagal memuat data", str(e))
        st.error(f"Error memuat stok: {e}")
        st.stop()


# =========================================================
# SIDEBAR & NAVIGASI
# =========================================================
is_admin = st.session_state.role == "admin"

PAGES_ALL = {
    "📊  Dashboard": "dash",
    "📦  Data Stok": "stok",
    "🗂️  Stok per Kategori": "kategori",
    "📥  Barang Masuk / Keluar": "trx",
    "🛠️  Master Sparepart": "master",
    "🕘  Riwayat Transaksi": "riwayat",
}
ADMIN_ONLY = {"trx", "master"}
pages = {k: v for k, v in PAGES_ALL.items() if is_admin or v not in ADMIN_ONLY}

if st.session_state.get("menu") not in pages:
    st.session_state.menu = list(pages.keys())[0]

with st.sidebar:
    st.markdown(
        '<div class="sb-brand"><div class="ic">📦</div><div class="tx">Stock Sparepart'
        '<small>INVENTORY SYSTEM</small></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="sb-user"><div class="av">{st.session_state.username[:1].upper()}</div>'
        f'<div><b>{st.session_state.username}</b><span>{st.session_state.role}</span></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sb-label">Menu Utama</div>', unsafe_allow_html=True)
    menu_label = st.radio("Navigasi", list(pages.keys()), key="menu", label_visibility="collapsed")
    st.markdown('<div class="sb-label">Aksi</div>', unsafe_allow_html=True)
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        flash("success", "Data diperbarui", "Data terbaru berhasil dimuat dari Google Sheets.")
        st.rerun()
    if st.button("🚪 Logout"):
        st.session_state.update(logged_in=False, role=None, username="", menu=None)
        st.rerun()

page = pages[menu_label]
show_flash()

# =========================================================
# 1. DASHBOARD
# =========================================================
if page == "dash":
    topbar("Dashboard", "📊")
    df = load_stock()
    if df.empty:
        st.info("Belum ada data di tab `STOCK`.")
        st.stop()

    n_item = len(df)
    tot_stok = int(df["STOCK AKHIR"].sum()) if "STOCK AKHIR" in df else 0
    tot_nom = df["NOMINAL TOTAL"].sum() if "NOMINAL TOTAL" in df else 0
    n_kritis = int((df["STOCK AKHIR"] <= KRITIS_MAX).sum()) if "STOCK AKHIR" in df else 0

    kpi_cards([
        ("Jumlah Item Part", num(n_item), "🔩", C_PRIMARY),
        ("Total Stok Akhir", num(tot_stok), "📦", C_SUCCESS),
        ("Total Nominal Stok", rp(tot_nom), "💰", C_INFO),
        (f"Stok Kritis (≤ {KRITIS_MAX})", num(n_kritis), "⚠️", C_DANGER),
    ])
    if n_kritis:
        swal_key = f"kritis_{n_kritis}"
        if st.session_state.get("_kritis_alert") != swal_key:
            st.session_state["_kritis_alert"] = swal_key
            swal("warning", "Perhatian: stok kritis", f"Ada {n_kritis} item dengan stok ≤ {KRITIS_MAX}.")

    has_kat = "KATEGORI" in df.columns
    if has_kat:
        dfk = df.assign(KATEGORI=df["KATEGORI"].replace("", "Tanpa Kategori").fillna("Tanpa Kategori"))
        g = dfk.groupby("KATEGORI", as_index=False).agg(
            NOMINAL=("NOMINAL TOTAL", "sum"), STOK=("STOCK AKHIR", "sum"), ITEM=("NO.PART", "count"))
        r1a, r1b = st.columns([3, 2])
        with r1a.container(border=True):
            st.markdown('<div class="panel-title">Nominal Stok per Kategori</div>', unsafe_allow_html=True)
            gs = g.sort_values("NOMINAL", ascending=False).head(15)
            fig = px.bar(gs, x="KATEGORI", y="NOMINAL", color_discrete_sequence=[C_PRIMARY])
            fig.update_yaxes(title=None, tickformat=",.0f")
            fig.update_xaxes(title=None)
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with r1b.container(border=True):
            st.markdown('<div class="panel-title">Komposisi Stok per Kategori</div>', unsafe_allow_html=True)
            gp = g[g["STOK"] > 0].sort_values("STOK", ascending=False)
            top = gp.head(7)
            if len(gp) > 7:
                top = pd.concat([top, pd.DataFrame([{"KATEGORI": "Lainnya", "STOK": gp["STOK"].iloc[7:].sum()}])])
            fig = px.pie(top, names="KATEGORI", values="STOK", hole=0.55, color_discrete_sequence=PALETTE)
            fig.update_traces(textinfo="percent")
            st.plotly_chart(style_fig(fig), use_container_width=True)

    r2a, r2b = st.columns(2)
    with r2a.container(border=True):
        st.markdown('<div class="panel-title">Top 10 Nominal Stok per Part</div>', unsafe_allow_html=True)
        top10 = df.sort_values("NOMINAL TOTAL", ascending=False).head(10).iloc[::-1]
        fig = px.bar(top10, x="NOMINAL TOTAL", y="SPAREPART", orientation="h", color_discrete_sequence=[C_SUCCESS])
        fig.update_xaxes(title=None, tickformat=",.0f")
        fig.update_yaxes(title=None)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with r2b.container(border=True):
        st.markdown('<div class="panel-title">Tren Barang Masuk vs Keluar (per bulan)</div>', unsafe_allow_html=True)
        trend = []
        try:
            for t in ["MASUK", "KELUAR"]:
                h = fetch_history(t)
                if h.empty:
                    continue
                dcol = next((c for c in h.columns if "TGL" in c.upper() or "TANGGAL" in c.upper() or "DATE" in c.upper()), None)
                qcol = next((c for c in h.columns if c.upper() in ("QTY", "JUMLAH")), None)
                if dcol and qcol:
                    x = pd.DataFrame({"tgl": pd.to_datetime(h[dcol], errors="coerce", dayfirst=True),
                                      "qty": pd.to_numeric(h[qcol], errors="coerce").fillna(0)}).dropna()
                    x["Bulan"] = x["tgl"].dt.to_period("M").astype(str)
                    x = x.groupby("Bulan", as_index=False)["qty"].sum()
                    x["Jenis"] = t
                    trend.append(x)
        except Exception:
            trend = []
        if trend:
            td = pd.concat(trend)
            fig = px.line(td, x="Bulan", y="qty", color="Jenis", markers=True,
                          color_discrete_map={"MASUK": C_SUCCESS, "KELUAR": C_DANGER})
            fig.update_yaxes(title=None)
            fig.update_xaxes(title=None)
            st.plotly_chart(style_fig(fig), use_container_width=True)
        else:
            st.info("Data tren belum tersedia (butuh kolom tanggal & QTY pada riwayat).")

    with st.container(border=True):
        st.markdown('<div class="panel-title">⚠️ Daftar Stok Kritis</div>', unsafe_allow_html=True)
        cols = [c for c in ["NO.PART", "SPAREPART", "TIPE MOBIL", "KATEGORI", "STOCK AKHIR"] if c in df.columns]
        kr = df[df["STOCK AKHIR"] <= KRITIS_MAX][cols]
        if kr.empty:
            st.success("Semua stok dalam kondisi aman.")
        else:
            st.dataframe(kr, use_container_width=True, hide_index=True)

# =========================================================
# 2. DATA STOK
# =========================================================
elif page == "stok":
    topbar("Data Stok", "📦")
    df = load_stock()
    if df.empty:
        st.info("Belum ada data di tab `STOCK`.")
        st.stop()

    with st.container(border=True):
        f1, f2, f3 = st.columns([2, 1, 1])
        cari = f1.text_input("🔍 Cari Sparepart / No. Part / Tipe Mobil")
        kat_opts = ["Semua"]
        if "KATEGORI" in df.columns:
            kat_opts += sorted([str(x) for x in df["KATEGORI"].dropna().unique() if str(x).strip()])
        kat = f2.selectbox("Kategori", kat_opts)
        kritis = f3.checkbox(f"Hanya stok ≤ {KRITIS_MAX}")

        v = df.copy()
        if cari:
            mask = pd.Series(False, index=v.index)
            for col in ["SPAREPART", "NO.PART", "TIPE MOBIL"]:
                if col in v.columns:
                    mask |= v[col].astype(str).str.contains(cari, case=False, na=False)
            v = v[mask]
        if kat != "Semua" and "KATEGORI" in v.columns:
            v = v[v["KATEGORI"].astype(str) == kat]
        if kritis and "STOCK AKHIR" in v.columns:
            v = v[v["STOCK AKHIR"] <= KRITIS_MAX]

        st.caption(f"Menampilkan {len(v):,} dari {len(df):,} item")
        st.dataframe(v, use_container_width=True, hide_index=True, height=480)
        tot = {}
        if "NOMINAL TOTAL" in v.columns:
            tot = {"SPAREPART": "TOTAL", "NOMINAL TOTAL": v["NOMINAL TOTAL"].sum()}
        export_buttons("Data_Stok", v, "Laporan Data Stok Sparepart",
                       money_cols=("PRICELIST", "NOMINAL TOTAL"),
                       int_cols=("STOCK AWAL", "MASUK", "KELUAR", "STOCK AKHIR"), total_row=tot, key="stok")

# =========================================================
# 3. STOK PER KATEGORI
# =========================================================
elif page == "kategori":
    topbar("Total Stok per Kategori", "🗂️")
    df = load_stock()
    if df.empty or "KATEGORI" not in df.columns:
        st.info("Data stok / kolom KATEGORI belum tersedia.")
        st.stop()

    df = df.assign(KATEGORI=df["KATEGORI"].replace("", "Tanpa Kategori").fillna("Tanpa Kategori"))
    g = df.groupby("KATEGORI", as_index=False).agg(
        **{"JUMLAH ITEM": ("NO.PART", "count"), "STOCK AWAL": ("STOCK AWAL", "sum"), "MASUK": ("MASUK", "sum"),
           "KELUAR": ("KELUAR", "sum"), "STOCK AKHIR": ("STOCK AKHIR", "sum"), "NOMINAL TOTAL": ("NOMINAL TOTAL", "sum")}
    ).sort_values("NOMINAL TOTAL", ascending=False)

    kpi_cards([
        ("Jumlah Kategori", num(len(g)), "🗂️", C_PRIMARY),
        ("Total Stok Akhir", num(g["STOCK AKHIR"].sum()), "📦", C_SUCCESS),
        ("Total Nominal", rp(g["NOMINAL TOTAL"].sum()), "💰", C_INFO),
    ])

    with st.container(border=True):
        st.markdown('<div class="panel-title">Ringkasan per Kategori</div>', unsafe_allow_html=True)
        st.dataframe(g, use_container_width=True, hide_index=True)
        total = {"KATEGORI": "TOTAL", "JUMLAH ITEM": g["JUMLAH ITEM"].sum(), "STOCK AWAL": g["STOCK AWAL"].sum(),
                 "MASUK": g["MASUK"].sum(), "KELUAR": g["KELUAR"].sum(), "STOCK AKHIR": g["STOCK AKHIR"].sum(),
                 "NOMINAL TOTAL": g["NOMINAL TOTAL"].sum()}
        export_buttons("Stok_per_Kategori", g, "Laporan Total Stok per Kategori",
                       money_cols=("NOMINAL TOTAL",),
                       int_cols=("JUMLAH ITEM", "STOCK AWAL", "MASUK", "KELUAR", "STOCK AKHIR"),
                       total_row=total, key="kat")

    with st.container(border=True):
        st.markdown('<div class="panel-title">Detail Part per Kategori</div>', unsafe_allow_html=True)
        pilih = st.selectbox("Pilih kategori", ["Semua"] + g["KATEGORI"].tolist())
        d = df if pilih == "Semua" else df[df["KATEGORI"] == pilih]
        cols = [c for c in ["KATEGORI", "NO.PART", "SPAREPART", "TIPE MOBIL", "STOCK AKHIR", "PRICELIST", "NOMINAL TOTAL"] if c in d.columns]
        d = d[cols].sort_values(["KATEGORI", "SPAREPART"])
        st.dataframe(d, use_container_width=True, hide_index=True, height=380)
        export_buttons(f"Detail_Kategori_{pilih}".replace(" ", "_"), d, f"Detail Stok Kategori: {pilih}",
                       money_cols=("PRICELIST", "NOMINAL TOTAL"), int_cols=("STOCK AKHIR",),
                       total_row={"SPAREPART": "TOTAL", "NOMINAL TOTAL": d["NOMINAL TOTAL"].sum()}, key="katd")

# =========================================================
# 4. INPUT BARANG MASUK / KELUAR (ADMIN)
# =========================================================
elif page == "trx" and is_admin:
    topbar("Input Barang Masuk / Keluar", "📥")
    df = load_stock()
    if df.empty or "NO.PART" not in df.columns:
        st.warning("Master sparepart kosong. Tambahkan item dulu di menu **Master Sparepart**.")
        st.stop()

    if st.session_state.pop("reset_trx", False):
        st.session_state["trx_kode"] = ""

    keys = df["NO.PART"].astype(str).str.strip().str.upper()
    with st.container(border=True):
        jenis = st.radio("Jenis Transaksi", ["MASUK", "KELUAR"], horizontal=True,
                         format_func=lambda x: "📥 Barang MASUK" if x == "MASUK" else "📤 Barang KELUAR")
        kode_raw = st.text_input("🔎 Ketik No. Part", key="trx_kode",
                                 placeholder="Contoh: 52119-0K903  (tekan Enter)")
        kode = kode_raw.strip().upper()

        if not kode:
            st.info("Masukkan No. Part, data sparepart akan muncul otomatis jika terdaftar di master.")
        else:
            hit = df[keys == kode]
            if hit.empty:
                st.error(f"No. Part **{kode_raw.strip()}** belum terdaftar di master sparepart.")
                sim = df[keys.str.contains(kode, regex=False)].head(5)
                if not sim.empty:
                    st.caption("Mungkin maksud Anda:")
                    st.dataframe(sim[[c for c in ["NO.PART", "SPAREPART", "TIPE MOBIL"] if c in sim.columns]],
                                 hide_index=True, use_container_width=True)
                st.button("➕ Daftarkan di Master Sparepart", type="primary",
                          on_click=goto, args=("🛠️  Master Sparepart",),
                          kwargs={"prefill_no_part": kode_raw.strip()})
            else:
                row = hit.iloc[0]
                no_part, nama = str(row["NO.PART"]), str(row.get("SPAREPART", ""))
                stok = int(row.get("STOCK AKHIR", 0))
                st.markdown(
                    f"""<div class="partcard"><h3>✅ {nama}</h3><div class="g">
                    <div><small>No. Part</small><b>{no_part}</b></div>
                    <div><small>Tipe Mobil</small><b>{row.get('TIPE MOBIL', '-') or '-'}</b></div>
                    <div><small>Kategori</small><b>{row.get('KATEGORI', '-') or '-'}</b></div>
                    <div><small>Pricelist</small><b>{rp(row.get('PRICELIST', 0))}</b></div>
                    <div><small>Stok Akhir</small><b>{num(stok)}</b></div></div></div>""",
                    unsafe_allow_html=True,
                )
                with st.form("form_trx", clear_on_submit=True):
                    qty = st.number_input("QTY", min_value=1, step=1, value=1)
                    ket = st.text_input("Keterangan (No. PO / Mekanik / Catatan)")
                    go_ = st.form_submit_button(f"💾 Simpan Barang {jenis}", type="primary", use_container_width=True)
                if go_:
                    if jenis == "KELUAR" and qty > stok:
                        swal("error", "Stok tidak cukup", f"Qty keluar ({qty}) melebihi stok tersedia ({stok}).")
                    else:
                        try:
                            res = post_payload({"action": "addTransaction", "type": jenis, "no_part": no_part,
                                                "sparepart": nama, "qty": int(qty), "keterangan": ket})
                            st.cache_data.clear()
                            flash("success", "Berhasil!", res.get("message", f"Transaksi {jenis} {no_part} x{qty} tersimpan."))
                            st.session_state["reset_trx"] = True
                            st.rerun()
                        except Exception as e:
                            swal("error", "Gagal menyimpan", str(e))

# =========================================================
# 5. MASTER SPAREPART (ADMIN)
# =========================================================
elif page == "master" and is_admin:
    topbar("Master Sparepart", "🛠️")
    tab_add, tab_edit, tab_del = st.tabs(["➕ Tambah Baru", "✏️ Edit Sparepart", "🗑️ Hapus Sparepart"])
    df_m = load_stock()
    has_data = not df_m.empty and "NO.PART" in df_m.columns

    with tab_add:
        prefill = st.session_state.pop("prefill_no_part", "")
        if prefill:
            st.info(f"No. Part **{prefill}** belum ada di master. Lengkapi datanya di bawah.")
        kat_exist = sorted({str(x) for x in df_m.get("KATEGORI", pd.Series(dtype=str)).dropna() if str(x).strip()}) if has_data else []
        with st.container(border=True):
            with st.form("form_master_add", clear_on_submit=True):
                c1, c2 = st.columns(2)
                no_part = c1.text_input("NO.PART *", value=prefill).strip()
                sparepart = c2.text_input("SPAREPART *").strip()
                c3, c4 = st.columns(2)
                tipe = c3.text_input("TIPE MOBIL").strip()
                kategori = c4.text_input("KATEGORI", help="Kategori yang sudah ada: " + (", ".join(kat_exist) or "-")).strip()
                c5, c6 = st.columns(2)
                s_awal = c5.number_input("STOCK AWAL", min_value=0, step=1, value=0)
                price = c6.number_input("PRICELIST", min_value=0, step=500, value=0)
                ok = st.form_submit_button("💾 Simpan Sparepart Baru", type="primary", use_container_width=True)
            if ok:
                if not no_part or not sparepart:
                    swal("warning", "Data belum lengkap", "NO.PART dan SPAREPART wajib diisi.")
                elif has_data and no_part.upper() in df_m["NO.PART"].astype(str).str.strip().str.upper().values:
                    swal("warning", "No. Part sudah ada", f"{no_part} sudah terdaftar di master.")
                else:
                    try:
                        res = post_payload({"action": "addNewPart", "no_part": no_part, "sparepart": sparepart,
                                            "tipe_mobil": tipe, "kategori": kategori,
                                            "stock_awal": int(s_awal), "pricelist": int(price)})
                        st.cache_data.clear()
                        flash("success", "Berhasil!", res.get("message", "Sparepart berhasil ditambahkan."))
                        st.rerun()
                    except Exception as e:
                        swal("error", "Gagal menambah sparepart", str(e))

    with tab_edit:
        if not has_data:
            st.info("Belum ada data sparepart untuk diedit.")
        else:
            with st.container(border=True):
                q = st.text_input("🔎 Ketik No. Part yang akan diedit", key="edit_q").strip().upper()
                k = df_m["NO.PART"].astype(str).str.strip().str.upper()
                hit = df_m[k == q] if q else df_m.iloc[0:0]
                if q and hit.empty:
                    st.error("No. Part tidak ditemukan.")
                    sim = df_m[k.str.contains(q, regex=False)].head(5)
                    if not sim.empty:
                        st.dataframe(sim[["NO.PART", "SPAREPART"]], hide_index=True, use_container_width=True)
                elif not q:
                    st.info("Ketik No. Part lalu tekan Enter.")
                else:
                    r = hit.iloc[0]
                    old = str(r["NO.PART"])
                    with st.form("form_master_edit"):
                        e1, e2 = st.columns(2)
                        n_no = e1.text_input("NO.PART *", value=old).strip()
                        n_sp = e2.text_input("SPAREPART *", value=str(r.get("SPAREPART", ""))).strip()
                        e3, e4 = st.columns(2)
                        n_tp = e3.text_input("TIPE MOBIL", value=str(r.get("TIPE MOBIL", ""))).strip()
                        n_kt = e4.text_input("KATEGORI", value=str(r.get("KATEGORI", ""))).strip()
                        e5, e6 = st.columns(2)
                        n_sa = e5.number_input("STOCK AWAL", min_value=0, step=1, value=int(r.get("STOCK AWAL", 0)))
                        n_pl = e6.number_input("PRICELIST", min_value=0, step=500, value=int(r.get("PRICELIST", 0)))
                        ok = st.form_submit_button("💾 Simpan Perubahan", type="primary", use_container_width=True)
                    if ok:
                        if not n_no or not n_sp:
                            swal("warning", "Data belum lengkap", "NO.PART dan SPAREPART wajib diisi.")
                        else:
                            try:
                                res = post_payload({"action": "updatePart", "old_no_part": old, "no_part": n_no,
                                                    "sparepart": n_sp, "tipe_mobil": n_tp, "kategori": n_kt,
                                                    "stock_awal": int(n_sa), "pricelist": int(n_pl)})
                                st.cache_data.clear()
                                flash("success", "Berhasil!", res.get("message", "Data sparepart diperbarui."))
                                st.rerun()
                            except Exception as e:
                                swal("error", "Gagal memperbarui", str(e))

    with tab_del:
        if not has_data:
            st.info("Belum ada data sparepart untuk dihapus.")
        else:
            with st.container(border=True):
                q = st.text_input("🔎 Ketik No. Part yang akan dihapus", key="del_q").strip().upper()
                k = df_m["NO.PART"].astype(str).str.strip().str.upper()
                hit = df_m[k == q] if q else df_m.iloc[0:0]
                if q and hit.empty:
                    st.error("No. Part tidak ditemukan.")
                elif not q:
                    st.info("Ketik No. Part lalu tekan Enter.")
                else:
                    r = hit.iloc[0]
                    no = str(r["NO.PART"])
                    st.warning(f"**{no} — {r.get('SPAREPART', '')}** akan dihapus permanen dari tab `STOCK`.")
                    yakin = st.checkbox("Saya yakin ingin menghapus sparepart ini")
                    if st.button("🗑️ Hapus Permanen", disabled=not yakin):
                        try:
                            res = post_payload({"action": "deletePart", "no_part": no})
                            st.cache_data.clear()
                            st.session_state["del_q"] = ""
                            flash("success", "Terhapus", res.get("message", "Sparepart berhasil dihapus."))
                            st.rerun()
                        except Exception as e:
                            swal("error", "Gagal menghapus", str(e))

# =========================================================
# 6. RIWAYAT TRANSAKSI
# =========================================================
elif page == "riwayat":
    topbar("Riwayat Transaksi", "🕘")
    with st.container(border=True):
        jenis = st.radio("Pilih Riwayat", ["MASUK", "KELUAR"], horizontal=True,
                         format_func=lambda x: "📥 Barang MASUK" if x == "MASUK" else "📤 Barang KELUAR")
        try:
            h = fetch_history(jenis)
        except Exception as e:
            swal("error", "Gagal memuat riwayat", str(e))
            st.error(f"Error memuat riwayat: {e}")
            st.stop()

        if h.empty:
            st.info(f"Belum ada data pada tab `{jenis}`.")
        else:
            cari = st.text_input("🔍 Cari di riwayat")
            if cari:
                m = h.astype(str).apply(lambda c: c.str.contains(cari, case=False, na=False)).any(axis=1)
                h = h[m]
            st.caption(f"{len(h):,} transaksi")
            st.dataframe(h, use_container_width=True, hide_index=True, height=480)
            export_buttons(f"Riwayat_{jenis}", h, f"Riwayat Barang {jenis}", key="riw")
