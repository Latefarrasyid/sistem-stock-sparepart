import io
import json
import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import html as _html
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


import base64


def md(html_str: str):
    """Render HTML tanpa indentasi/baris kosong agar tidak dianggap code block oleh Markdown."""
    st.markdown(" ".join(l.strip() for l in html_str.strip().splitlines()), unsafe_allow_html=True)


LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
LOGO_B64 = ""
if os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as _f:
        LOGO_B64 = base64.b64encode(_f.read()).decode()
LOGIN_BG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login_bg.jpg")
LOGIN_B64 = ""
if os.path.exists(LOGIN_BG_PATH):
    with open(LOGIN_BG_PATH, "rb") as _f:
        LOGIN_B64 = base64.b64encode(_f.read()).decode()
LOGO_IMG = (f'<img src="data:image/png;base64,{LOGO_B64}" class="logo-img">' if LOGO_B64 else "📦")

try:
    from PIL import Image
    _ICON = Image.open(LOGO_PATH) if os.path.exists(LOGO_PATH) else "📦"
except Exception:
    _ICON = "📦"

st.set_page_config(
    page_title="Sistem Stock Sparepart",
    page_icon=_ICON,
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
# Stok di sistem = stok akhir Oktober 2026, jadi transaksi yang diimport hanya yang SETELAH tanggal ini
STOK_CUTOFF = date(2026, 11, 1)
NUM_COLS = ["STOCK AWAL", "KELUAR", "MASUK", "PRICELIST", "NOMINAL TOTAL", "STOCK AKHIR"]

# Palet warna ala SB Admin 2
C_PRIMARY, C_SUCCESS, C_INFO, C_WARNING, C_DANGER = "#2B5CD8", "#22A06B", "#3B8FE8", "#F5A524", "#D64545"
C_DARK = "#1E40AF"
INK = "#0F1E45"
PALETTE = ["#2B5CD8", "#5AA0F0", "#1B2A5C", "#22A06B", "#F5A524", "#8C6BB1", "#D64545", "#7A8B99", "#6FB7A5", "#9DC3F7"]


def is_valid_gas_url(url: str) -> bool:
    return url.startswith("https://script.google.com/macros/s/") and url.endswith("/exec")


def now_wib() -> datetime:
    return datetime.utcnow() + timedelta(hours=7)


MONEY_COLS = ("PRICELIST", "NOMINAL TOTAL", "NOMINAL", "HARGA")


def rp(x) -> str:
    try:
        if pd.isna(x):
            return "Rp 0"
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp button, .stApp input, .stApp textarea, .stApp li, .stApp td, .stApp th, .stApp a,
.topbar, .kpi, .partcard, .panel-title, .sb-brand, .sb-user, .sb-label, .login-head, .rtable
{{ font-family: 'Inter', 'Segoe UI', Roboto, Arial, sans-serif; }}
[data-testid="stIconMaterial"], .material-icons, [class*="material-symbols"]
{{ font-family: 'Material Symbols Rounded', 'Material Icons' !important; }}
.stApp {{ background:#F0F4FB; color:{INK}; }}
#MainMenu, footer {{ visibility:hidden; }}
header[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding:1rem 1.5rem 3rem 1.5rem; max-width:1500px; }}
.logo-img {{ width:46px; height:46px; border-radius:50%; }}

/* SIDEBAR */
section[data-testid="stSidebar"] {{ background:#DCE9FB; border-right:1px solid #c5d8f3; }}
.sb-brand {{ text-align:center; padding:.6rem 0 1.1rem; }}
.sb-brand .logo-img {{ width:72px; height:72px; box-shadow:0 3px 10px rgba(30,64,175,.25); }}
.sb-brand .tx {{ font-weight:800; color:{INK}; letter-spacing:.06rem; margin-top:.55rem; font-size:1rem; text-transform:uppercase; }}
.sb-brand small {{ display:block; color:#5b6f96; font-size:.62rem; letter-spacing:.14rem; font-weight:700; }}
.sb-user {{ background:#fff; border-radius:.75rem; padding:.6rem .8rem; margin-bottom:.8rem; display:flex;
  align-items:center; gap:.7rem; box-shadow:0 1px 4px rgba(30,64,175,.10); }}
.sb-user .av {{ width:36px; height:36px; border-radius:50%; background:{C_PRIMARY}; color:#fff;
  display:flex; align-items:center; justify-content:center; font-weight:800; }}
.sb-user b {{ display:block; font-size:.88rem; color:{INK}; }}
.sb-user span {{ font-size:.66rem; color:#5b6f96; text-transform:uppercase; letter-spacing:.06rem; font-weight:700; }}
.sb-label {{ font-size:.65rem; font-weight:800; text-transform:uppercase; letter-spacing:.1rem; color:#6a7ea6; margin:.6rem 0 .3rem .3rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:.2rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{ padding:.7rem .9rem; border-radius:.6rem; width:100%; cursor:pointer; transition:.15s; margin:0; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background:rgba(43,92,216,.10); }}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display:none !important; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label p {{ white-space:normal; line-height:1.25; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label p {{ font-weight:600; font-size:.93rem; color:{INK}; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{ background:{C_PRIMARY}; box-shadow:0 3px 8px rgba(43,92,216,.35); }}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {{ color:#fff !important; }}
section[data-testid="stSidebar"] .stButton > button {{ background:#fff; border:1px solid #b9cdee; color:{C_DARK}; width:100%; border-radius:.6rem; font-weight:700; }}
section[data-testid="stSidebar"] .stButton > button:hover {{ background:{C_PRIMARY}; color:#fff; border-color:{C_PRIMARY}; }}

/* TOPBAR */
.topbar {{ background:#fff; border-radius:.9rem; box-shadow:0 1px 6px rgba(15,30,69,.08); padding:.85rem 1.3rem;
  margin-bottom:1.1rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.6rem; }}
.topbar h1 {{ font-size:1.4rem; font-weight:700; margin:0; color:{INK}; }}
.topbar .crumb {{ font-size:.74rem; color:#6a7ea6; }}
.tb-right {{ display:flex; align-items:center; gap:.9rem; flex-wrap:wrap; }}
.chip {{ background:#EEF3FC; border-radius:2rem; padding:.35rem .9rem; font-size:.78rem; font-weight:600; color:#3a4d78; }}
.tb-user {{ display:flex; align-items:center; gap:.55rem; }}
.tb-user .av {{ width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#5AA0F0,{C_PRIMARY}); color:#fff;
  display:flex; align-items:center; justify-content:center; font-weight:800; }}
.tb-user b {{ display:block; font-size:.9rem; line-height:1.1; }}
.tb-user small {{ color:#6a7ea6; font-size:.68rem; font-weight:700; text-transform:uppercase; }}
.bell {{ position:relative; font-size:1.2rem; }}
.bell i {{ position:absolute; top:-1px; right:-2px; width:8px; height:8px; background:{C_DANGER}; border-radius:50%; }}

/* KPI */
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; margin-bottom:1.1rem; }}
.kpi {{ background:#fff; border-radius:.9rem; padding:1rem 1.2rem; box-shadow:0 1px 6px rgba(15,30,69,.08);
  display:flex; justify-content:space-between; align-items:center; gap:.5rem; }}
.kpi .lb {{ font-size:.85rem; font-weight:600; color:#33476f; }}
.kpi .vl {{ font-size:1.9rem; font-weight:800; line-height:1.15; margin-top:.15rem; word-break:break-word; }}
.kpi .kr {{ display:flex; flex-direction:column; align-items:flex-end; gap:.3rem; }}
.kpi .ib {{ width:46px; height:46px; border-radius:.7rem; display:flex; align-items:center; justify-content:center; font-size:1.4rem; }}
.kpi small {{ font-weight:700; font-size:.7rem; }}

/* PANEL */
.panel-title {{ font-weight:700; color:{INK}; font-size:1.05rem; margin:.2rem 0 .5rem; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ background:#fff; border-radius:.9rem; box-shadow:0 1px 6px rgba(15,30,69,.07); border:none; }}
.partcard {{ background:linear-gradient(135deg,#eaf1ff,#fff); border:1px solid #cfdcf5; border-radius:.8rem; padding:1rem 1.2rem; margin:.6rem 0 1rem; }}
.partcard h3 {{ margin:0 0 .6rem; color:{C_DARK}; font-size:1.1rem; font-weight:700; }}
.partcard .g {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.6rem; }}
.partcard .g div small {{ display:block; color:#6a7ea6; font-size:.68rem; font-weight:700; text-transform:uppercase; }}
.partcard .g div b {{ color:{INK}; }}
.rtable-wrap {{ overflow-x:auto; }}
.rtable {{ width:100%; border-collapse:collapse; }}
.rtable th {{ background:#F1F5FC; text-align:left; font-size:.78rem; color:#33476f; padding:.55rem .6rem; font-weight:600; }}
.rtable td {{ padding:.55rem .6rem; border-bottom:1px solid #e8eef8; font-size:.85rem; }}
.badge {{ padding:.15rem .65rem; border-radius:1rem; font-size:.75rem; font-weight:600; }}
.badge.ok {{ background:#DDF5E8; color:#1d7a4d; }}
.badge.out {{ background:#FDEBD0; color:#a8620c; }}

/* INPUT & TOMBOL */
div[data-baseweb="input"], div[data-baseweb="base-input"] {{ border-radius:.5rem !important; background:#fff !important; }}
.stTextInput input, .stNumberInput input {{ background:#fff !important; }}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{ border-radius:.55rem; font-weight:600; }}
.stFormSubmitButton > button[kind="primary"], .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"]
{{ background:{C_PRIMARY} !important; border-color:{C_PRIMARY} !important; color:#fff !important; }}
.stFormSubmitButton > button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover
{{ background:{C_DARK} !important; border-color:{C_DARK} !important; }}

@media (max-width: 768px) {{
  .block-container {{ padding:.6rem .7rem 3rem; }}
  .topbar h1 {{ font-size:1.15rem; }}
  .kpi .vl {{ font-size:1.4rem; }}
  .kpi-grid {{ grid-template-columns:1fr 1fr; gap:.6rem; }}
  .kpi {{ padding:.8rem; }}
  .kpi .ib {{ width:36px; height:36px; font-size:1.1rem; }}
  .chip {{ display:none; }}
}}
@media (max-width: 480px) {{ .kpi-grid {{ grid-template-columns:1fr; }} }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
components.html("""<script>
(function(){const d=window.parent.document;
if(!d.getElementById('inter-font')){const l=d.createElement('link');l.id='inter-font';l.rel='stylesheet';
l.href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap';d.head.appendChild(l);}})();
</script>""", height=0)


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
    art = f'<img src="data:image/jpeg;base64,{LOGIN_B64}" class="login-art">' if LOGIN_B64 else ""
    md(f"""
        <style>
        section[data-testid="stSidebar"]{{display:none;}}
        header[data-testid="stHeader"]{{display:none;}}
        .stApp{{background:#EEF2F9;}}
        .block-container{{padding:0 !important; max-width:100% !important;}}
        div[data-testid="stHorizontalBlock"]{{gap:0 !important; align-items:stretch;}}
        .login-left{{background:linear-gradient(160deg,#5A9BF0 0%,#2B5CD8 100%); min-height:100vh; display:flex;
          align-items:center; justify-content:center; padding:2rem;}}
        .login-art{{width:100%; max-width:540px; border-radius:18px; box-shadow:0 12px 40px rgba(10,30,90,.35);
          border:3px solid rgba(255,255,255,.4);}}
        .login-head{{text-align:center; margin:14vh 0 1.4rem;}}
        .login-head .logo-img{{width:76px; height:76px; box-shadow:0 4px 14px rgba(30,64,175,.3);}}
        .login-head h2{{font-size:1.8rem; font-weight:800; color:#0F1E45; margin:.7rem 0 .2rem;}}
        .login-head p{{color:#3a4d78; margin:0;}}
        @media (max-width:768px){{ .login-left{{display:none;}} .login-head{{margin-top:6vh;}} }}
        </style>
    """)
    left, right = st.columns(2)
    with left:
        md(f'<div class="login-left">{art}</div>')
    with right:
        md(f"""<div class="login-head">{LOGO_IMG}<h2>Aplikasi Stock Sparepart</h2>
            <p>Masuk untuk mengelola stok dan inventaris</p></div>""")
        _, mid, _ = st.columns([0.1, 0.8, 0.1])
        with mid:
            with st.container(border=True):
                with st.form("login_form"):
                    username = st.text_input("Username", placeholder="Username")
                    password = st.text_input("Password", type="password", placeholder="Kata Sandi")
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
                c.fill = PatternFill("solid", fgColor="2B5CD8")
                c.alignment = Alignment(horizontal="center", vertical="center")
            for i, col in enumerate(frame.columns, start=1):
                width = max([len(str(col))] + [len(str(v)) for v in frame[col].head(300)]) + 3
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(width, 45)
            for i, col in enumerate(frame.columns, start=1):
                if str(col).upper() in MONEY_COLS:
                    for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                        for c in row:
                            c.number_format = '"Rp" #,##0'
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
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbf7f2")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, c in enumerate(frame.columns):
        if c in money_cols or c in int_cols:
            style.append(("ALIGN", (i, 0), (i, -1), "RIGHT"))
    if total_row:
        style += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                  ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f4e9de"))]
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
def topbar(title: str, icon: str = ""):
    u = st.session_state.username
    md(f"""<div class="topbar"><div><h1>{title}</h1>
        <div class="crumb">Sistem Stock Sparepart &nbsp;/&nbsp; {title}</div></div>
        <div class="tb-right"><span class="chip">📅 {now_wib():%d %b %Y, %H:%M} WIB</span>
        <div class="tb-user"><div class="av">{u[:1].upper()}</div>
        <div><b>{u}</b><small>{st.session_state.role}</small></div></div></div></div>""")


def kpi_cards(items):
    html = '<div class="kpi-grid">'
    for it in items:
        label, value, icon, color = it[:4]
        note = it[4] if len(it) > 4 else ""
        vcolor = C_DANGER if color == C_DANGER else INK
        note_html = f'<small style="color:{color}">{note}</small>' if note else ""
        html += (f'<div class="kpi"><div><div class="lb">{label}</div><div class="vl" style="color:{vcolor}">{value}</div></div>'
                 f'<div class="kr"><div class="ib" style="background:{color}22;color:{color}">{icon}</div>{note_html}</div></div>')
    st.markdown(html + "</div>", unsafe_allow_html=True)


def style_fig(fig, height=340):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter", color="#0F1E45"),
                      legend=dict(orientation="h", y=-0.2))
    return fig


def goto(page: str, **state):
    st.session_state.menu = page
    for k, v in state.items():
        st.session_state[k] = v


def _pick(cols, keys=(), exact=()):
    for c in cols:
        u = str(c).upper()
        if u in exact or any(k in u for k in keys):
            return c
    return None


def movement_data() -> pd.DataFrame:
    frames = []
    for t in ["MASUK", "KELUAR"]:
        try:
            h = fetch_history(t)
        except Exception:
            continue
        if h.empty:
            continue
        dcol = _pick(h.columns, ("TGL", "TANGGAL", "DATE", "WAKTU"))
        qcol = _pick(h.columns, exact=("QTY", "JUMLAH"))
        pcol = _pick(h.columns, ("NO.PART", "NO PART", "NOPART"))
        scol = _pick(h.columns, ("SPAREPART",))
        frames.append(pd.DataFrame({
            "Waktu": pd.to_datetime(h[dcol], errors="coerce", dayfirst=True) if dcol else pd.NaT,
            "Jenis": t,
            "No.Part": h[pcol] if pcol else "-",
            "Sparepart": h[scol] if scol else "-",
            "Qty": pd.to_numeric(h[qcol], errors="coerce").fillna(0) if qcol else 0,
        }))
    if not frames:
        return pd.DataFrame(columns=["Waktu", "Jenis", "No.Part", "Sparepart", "Qty"])
    out = pd.concat(frames, ignore_index=True)
    out["Waktu"] = pd.to_datetime(out["Waktu"], errors="coerce")
    return out


KATEGORI_LIST = [
    "ACCU", "AFFRONT", "AIR BAG", "AIR INLET", "BACKDOOR", "BAN", "BULKHEAD", "BUMPER", "CHASSIS", "CONDENSOR",
    "COWL", "CROSSMEMBER", "EMBLEM", "ENGINE", "EXHAUST", "FENDER DAN QUARTER", "FILTER UDARA",
    "FOG & COVER FOG LAMP", "FOOTSTEP", "HEAD LAMP", "INSTRUMENT & GOLVS", "INTERIOR LAMP", "INTERIOR TRIME",
    "KACA", "KAKI-KAKI", "KAP MESIN", "LANTAI", "LINNER", "LIST PINTU", "MOUNTING", "MUDGUARD", "NHF & TPR",
    "PILAR", "PINTU", "RADIATOR", "RAM & GRILLE", "REM", "ROOF & SIDE ROOF", "SPEEDOMETER", "SPION",
    "STEERING SISTEM", "STOP LAMP", "TALANG AIR", "TAPE DAN RADIO", "TOOLSET", "TRANSMISI & KOPLING",
    "TRISPLANG", "VELG", "WIPER", "WIREHARNESS",
]


def clean_kategori(x) -> str:
    """Ambil nama kategorinya saja: buang awalan 'PART', tahun (2024 dst) dan ekstensi file."""
    t = str(x or "").strip().upper().replace("_", " ")
    t = re.sub(r"\.XLSX?$", "", t)
    t = re.sub(r"^PART\s+", "", t)
    t = re.sub(r"\s*(19|20)\d{2}\s*$", "", t)
    return t.strip()


def kategori_options(df=None) -> list:
    """Daftar tetap + kategori lain yang sudah ada di sheet (jika ada yang belum masuk daftar)."""
    opts = list(KATEGORI_LIST)
    if df is not None and not df.empty and "KATEGORI" in df.columns:
        for v in df["KATEGORI"].dropna().unique():
            c = clean_kategori(v)
            if c and c not in opts:
                opts.append(c)
    return sorted(opts)


def sdf(frame, **kw):
    """st.dataframe dengan kolom PRICELIST / NOMINAL tampil sebagai Rp 1.234.567 (nilai tetap angka, bisa di-sort)."""
    cols = {c: rp for c in MONEY_COLS if c in frame.columns}
    data = frame.style.format(cols) if cols else frame
    kw.setdefault("hide_index", True)
    kw.setdefault("use_container_width", True)
    st.dataframe(data, **kw)


# ---------------------------------------------------------
# IMPORT MASTER DARI EXCEL / CSV
# ---------------------------------------------------------
STD_COLS = ["NO.PART", "SPAREPART", "TIPE MOBIL", "KATEGORI", "STOCK AWAL", "PRICELIST"]
IMPORT_ALIASES = {
    "NO.PART": {"NOPART", "PARTNO", "PARTNUMBER", "NOPARTNUMBER", "KODEPART"},
    "SPAREPART": {"SPAREPART", "NAMAPART", "NAMABARANG", "NAMASPAREPART", "DESKRIPSI", "DESCRIPTION"},
    "TIPE MOBIL": {"TIPEMOBIL", "TIPE", "MODEL", "TYPE", "MOBIL", "TYPEMODEL", "TIPEMODEL"},
    "KATEGORI": {"KATEGORI", "KATEGORY", "CATEGORY"},
    "STOCK AWAL": {"STOCKAWAL", "STOKAWAL", "SALDOAWAL", "STOCK", "STOK", "QTY"},
    "PRICELIST": {"PRICELIST", "HARGA", "HARGAJUAL", "PRICE", "HARGAPART", "HARGAPL", "HARGAPRICELIST"},
}


def _norm(x) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(x).upper())


def _map_headers(values) -> dict:
    mapping = {}
    # kolom STOCK AKHIR (termasuk salah ketik seperti "STOCK AKIRH") diutamakan
    for idx, v in enumerate(values):
        if re.match(r"^(STOCK|STOK)AK", _norm(v)):
            mapping["STOCK AKHIR"] = idx
            break
    for std, alias in IMPORT_ALIASES.items():
        for idx, v in enumerate(values):
            if idx not in mapping.values() and _norm(v) in alias:
                mapping[std] = idx
                break
    return mapping


def to_int(v) -> int:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0
    if isinstance(v, (int, float)):
        return int(round(v))
    t = re.sub(r"[^\d,.\-]", "", str(v))
    if not t or t in "-.,":
        return 0
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+", t):
        t = t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        return int(round(float(t)))
    except ValueError:
        return 0


def _clean_cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def parse_upload(f):
    """Baca satu file (xlsx/csv). Hanya STOCK AKHIR yang diambil (transaksi masuk/keluar diabaikan).
    Return (DataFrame kolom STD_COLS, catatan). Kolom STOCK AWAL pada hasil = stok akhir dari file."""
    name = f.name
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    try:
        if name.lower().endswith(".csv"):
            try:
                raw = pd.read_csv(f, header=None, dtype=object, sep=None, engine="python", encoding="utf-8")
            except UnicodeDecodeError:
                f.seek(0)
                raw = pd.read_csv(f, header=None, dtype=object, sep=None, engine="python", encoding="latin-1")
            sheets = {"csv": raw}
        else:
            sheets = pd.read_excel(f, sheet_name=None, header=None, dtype=object)
    except Exception as e:
        return None, f"Gagal membaca file: {e}"

    cands = []
    for sname, raw in sheets.items():
        for i in range(min(20, len(raw))):
            mp = _map_headers(list(raw.iloc[i].values))
            if "NO.PART" in mp and "SPAREPART" in mp:
                cands.append((sname, raw, i, mp))
                break
    if not cands:
        return None, "Kolom NO.PART dan SPAREPART tidak ditemukan pada 20 baris pertama."

    # pilih sheet yang punya kolom stok akhir (sheet MASUK/KELUAR otomatis terabaikan)
    sname, raw, i, mp = next((c for c in cands if "STOCK AKHIR" in c[3]), cands[0])
    stock_idx = mp.get("STOCK AKHIR", mp.get("STOCK AWAL"))
    data = raw.iloc[i + 1:]
    out = pd.DataFrame(index=range(len(data)))
    for c in STD_COLS:
        if c == "STOCK AWAL":
            out[c] = data.iloc[:, stock_idx].reset_index(drop=True).map(to_int) if stock_idx is not None else 0
        elif c in mp:
            col = data.iloc[:, mp[c]].reset_index(drop=True)
            out[c] = col.map(to_int) if c == "PRICELIST" else col.map(_clean_cell)
        else:
            out[c] = 0 if c == "PRICELIST" else ""
    out["FILE"] = name
    out["_STEM"] = stem
    out = out[(out["NO.PART"] != "") & (out["SPAREPART"] != "")]
    stok_hdr = _clean_cell(raw.iloc[i, stock_idx]) if stock_idx is not None else "-"
    return out, f"{len(out)} baris dari sheet '{sname}' (stok diambil dari kolom '{stok_hdr}')"


# ---------------------------------------------------------
# IMPORT TRANSAKSI MASUK / KELUAR DARI EXCEL
# ---------------------------------------------------------
TRX_ALIASES = {
    "NO": {"NO"},
    "TANGGAL": {"TANGGAL", "TGL", "DATE"},
    "ASURANSI": {"ASURANSI", "INSURANCE"},
    "MEREK": {"MEREK", "TIPEMOBIL", "MODEL", "TYPE", "MOBIL"},
    "PLAT": {"PLATNOMOR", "NOPOL", "PLAT", "NOPLAT", "PLATNO"},
    "SPAREPART": {"SPAREPART", "NAMAPART", "NAMABARANG"},
    "NO.PART": {"NOMORPART", "NOPART", "PARTNO", "PARTNUMBER", "NOPARTNUMBER"},
    "HARGA": {"HARGA", "PRICE", "PRICELIST", "HARGAPART"},
    "QTY": {"QTY", "JUMLAH", "JML"},
}

CAT_KEYWORDS = [
    ("AIR BAG", "AIR BAG"), ("AIRBAG", "AIR BAG"), ("HEAD LAMP", "HEAD LAMP"), ("HEADLAMP", "HEAD LAMP"),
    ("STOP LAMP", "STOP LAMP"), ("FOG LAMP", "FOG & COVER FOG LAMP"), ("INTERIOR LAMP", "INTERIOR LAMP"),
    ("BUMPER", "BUMPER"), ("GRILLE", "RAM & GRILLE"), ("GRILE", "RAM & GRILLE"), ("SPION", "SPION"),
    ("VELG", "VELG"), ("KAP MESIN", "KAP MESIN"), ("BACKDOOR", "BACKDOOR"), ("BAKDOOR", "BACKDOOR"),
    ("LIST PINTU", "LIST PINTU"), ("PINTU", "PINTU"), ("FENDER", "FENDER DAN QUARTER"),
    ("QUARTER", "FENDER DAN QUARTER"), ("RADIATOR", "RADIATOR"), ("CONDENSOR", "CONDENSOR"),
    ("KACA", "KACA"), ("EMBLEM", "EMBLEM"), ("SHOCK", "KAKI-KAKI"), ("WIPER", "WIPER"), ("ACCU", "ACCU"),
    ("AFRONT", "AFFRONT"), ("AFFRONT", "AFFRONT"), ("MUDGUARD", "MUDGUARD"), ("LINNER", "LINNER"),
    ("TRISPLANG", "TRISPLANG"), ("TISLANG", "TRISPLANG"), ("INTERCOOLER", "ENGINE"), ("INTAKE", "ENGINE"),
    ("TURBO", "ENGINE"), ("PILAR", "PILAR"), ("COWL", "COWL"),
]


def guess_kategori(name):
    """Tebakan kategori dari nama sparepart (bisa diubah user). Return None jika tidak yakin."""
    u = str(name).upper()
    for key, cat in CAT_KEYWORDS:
        if key in u:
            return cat
    return None


def _map_trx(values) -> dict:
    mp = {}
    for std, alias in TRX_ALIASES.items():
        for idx, v in enumerate(values):
            if idx not in mp.values() and _norm(v) in alias:
                mp[std] = idx
                break
    return mp


def _to_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return pd.NaT
    return pd.to_datetime(v, errors="coerce", dayfirst=True)


def parse_trx_file(f):
    """Baca file transaksi (banyak sheet per bulan). Baris lanjutan (tanpa NO.) mewarisi
    tanggal/asuransi/merek/plat dari baris transaksi di atasnya. Return (DataFrame, catatan)."""
    name = f.name
    try:
        sheets = pd.read_excel(f, sheet_name=None, header=None, dtype=object)
    except Exception as e:
        return None, f"Gagal membaca file: {e}"
    u = name.upper()
    jenis = "KELUAR" if "KELUAR" in u else "MASUK" if "MASUK" in u else ""
    rows, n_sheet = [], 0
    for sname, raw in sheets.items():
        if not jenis and raw.shape[0] and raw.shape[1]:
            title = str(raw.iloc[0, 0]).upper()
            jenis = "KELUAR" if "KELUAR" in title else "MASUK" if "MASUK" in title else ""
        hdr = None
        for i in range(min(10, len(raw))):
            mp = _map_trx(list(raw.iloc[i].values))
            if "SPAREPART" in mp and "NO.PART" in mp:
                hdr = (i, mp)
                break
        if hdr is None:
            continue
        n_sheet += 1
        i, mp = hdr
        cur = {"TANGGAL": pd.NaT, "ASURANSI": "", "MEREK": "", "PLAT": ""}
        for vals in raw.iloc[i + 1:].itertuples(index=False, name=None):
            get = lambda k: vals[mp[k]] if k in mp else None
            no = _clean_cell(get("NO"))
            if no.upper().startswith("TOTAL"):
                continue
            if no != "":
                cur = {"TANGGAL": _to_date(get("TANGGAL")), "ASURANSI": _clean_cell(get("ASURANSI")),
                       "MEREK": _clean_cell(get("MEREK")), "PLAT": _clean_cell(get("PLAT"))}
            sp = _clean_cell(get("SPAREPART"))
            if sp == "":
                continue
            m = re.search(r"[@(]\s*(\d+)\s*PCS", sp.upper())
            qty = int(m.group(1)) if m else 1
            if "QTY" in mp:
                qty = max(to_int(get("QTY")), 1)
            rows.append({**cur, "SPAREPART": sp, "NO.PART": _clean_cell(get("NO.PART")), "QTY": qty,
                         "HARGA": to_int(get("HARGA")), "SHEET": sname, "FILE": name})
    if not rows:
        return None, "Kolom SPARE PART dan NOMOR PART tidak ditemukan di sheet manapun."
    out = pd.DataFrame(rows)
    out["TANGGAL"] = pd.to_datetime(out["TANGGAL"], errors="coerce")
    out.insert(0, "JENIS", jenis)
    return out, f"{len(out)} baris part dari {n_sheet} sheet" + (f" · terdeteksi {jenis}" if jenis else " · jenis tidak terdeteksi")


def load_stock():
    try:
        d = fetch_stock().copy()
        if "KATEGORI" in d.columns:
            d["KATEGORI"] = d["KATEGORI"].map(clean_kategori)
        return d
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
    "📑  Import Transaksi": "imptrx",
    "🛠️  Master Sparepart": "master",
    "🕘  Riwayat Transaksi": "riwayat",
}
ADMIN_ONLY = {"trx", "imptrx", "master"}
pages = {k: v for k, v in PAGES_ALL.items() if is_admin or v not in ADMIN_ONLY}

if st.session_state.get("menu") not in pages:
    st.session_state.menu = list(pages.keys())[0]

with st.sidebar:
    md(f'<div class="sb-brand">{LOGO_IMG}<div class="tx">Stock Sparepart</div><small>INVENTORY SYSTEM</small></div>')
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
        st.session_state.update(logged_in=False, role=None, username="")
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

    mv = movement_data()
    has_dates = (not mv.empty) and mv["Waktu"].notna().any()
    today = now_wib().date()
    if has_dates:
        masuk_today = int(mv[(mv["Jenis"] == "MASUK") & (mv["Waktu"].dt.date == today)]["Qty"].sum())
        keluar_today = int(mv[(mv["Jenis"] == "KELUAR") & (mv["Waktu"].dt.date == today)]["Qty"].sum())
    else:
        masuk_today = keluar_today = 0

    n_item = len(df)
    tot_stok = int(df["STOCK AKHIR"].sum()) if "STOCK AKHIR" in df else 0
    tot_nom = df["NOMINAL TOTAL"].sum() if "NOMINAL TOTAL" in df else 0
    n_kritis = int((df["STOCK AKHIR"] <= KRITIS_MAX).sum()) if "STOCK AKHIR" in df else 0

    kpi_cards([
        ("Total Stok Barang", num(tot_stok), "📦", C_PRIMARY),
        ("Barang Masuk Hari Ini", num(masuk_today), "⬆️", C_PRIMARY),
        ("Barang Keluar Hari Ini", num(keluar_today), "⬇️", C_INFO),
        (f"Stok Menipis (≤ {KRITIS_MAX})", num(n_kritis), "⚠️", C_DANGER, "Peringatan!" if n_kritis else ""),
    ])
    kpi_cards([
        ("Jumlah Item Part", num(n_item), "🔩", C_PRIMARY),
        ("Total Nominal Stok", rp(tot_nom), "💰", C_SUCCESS),
    ])
    if n_kritis:
        swal_key = f"kritis_{n_kritis}"
        if st.session_state.get("_kritis_alert") != swal_key:
            st.session_state["_kritis_alert"] = swal_key
            swal("warning", "Perhatian: stok kritis", f"Ada {n_kritis} item dengan stok ≤ {KRITIS_MAX}.")

    with st.container(border=True):
        st.markdown('<div class="panel-title">Pergerakan Stok (7 Hari Terakhir)</div>', unsafe_allow_html=True)
        if has_dates:
            w = mv.dropna(subset=["Waktu"]).assign(Tgl=lambda d: d["Waktu"].dt.normalize())
            piv = w.pivot_table(index="Tgl", columns="Jenis", values="Qty", aggfunc="sum", fill_value=0).sort_index().tail(7)
            for c in ["MASUK", "KELUAR"]:
                if c not in piv.columns:
                    piv[c] = 0
            lbl = piv.index.strftime("%d %b")
            fig = go.Figure()
            fig.add_bar(x=lbl, y=piv["MASUK"], name="Masuk", marker_color=C_PRIMARY)
            fig.add_bar(x=lbl, y=piv["KELUAR"], name="Keluar", marker_color="#6FAEF2")
            fig.add_scatter(x=lbl, y=piv["MASUK"] - piv["KELUAR"], name="Selisih", mode="lines+markers",
                            line=dict(color="#1B2A5C", width=2))
            fig.update_layout(barmode="group")
            st.plotly_chart(style_fig(fig, 320), use_container_width=True)
        else:
            st.info("Grafik pergerakan butuh kolom tanggal & QTY pada sheet riwayat.")

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
        fig = px.bar(top10, x="NOMINAL TOTAL", y="SPAREPART", orientation="h", color_discrete_sequence=["#5AA0F0"])
        fig.update_xaxes(title=None, tickformat=",.0f")
        fig.update_yaxes(title=None)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    with r2b.container(border=True):
        st.markdown('<div class="panel-title">Transaksi Terbaru</div>', unsafe_allow_html=True)
        if mv.empty:
            st.info("Belum ada transaksi.")
        else:
            rec = mv.sort_values("Waktu", ascending=False, na_position="last").head(8)
            rows = ""
            for r in rec.itertuples():
                wkt = r.Waktu.strftime("%d/%m %H:%M") if pd.notna(r.Waktu) else "-"
                cls = "ok" if r.Jenis == "MASUK" else "out"
                rows += (f'<tr><td>{wkt}</td><td><span class="badge {cls}">{r.Jenis.title()}</span></td>'
                         f'<td>{_html.escape(str(r.Sparepart))}</td><td>{num(r.Qty)}</td></tr>')
            md('<div class="rtable-wrap"><table class="rtable"><thead><tr><th>Waktu</th><th>Jenis</th>'
               f'<th>Barang</th><th>Jumlah</th></tr></thead><tbody>{rows}</tbody></table></div>')

    with st.container(border=True):
        st.markdown('<div class="panel-title">⚠️ Daftar Stok Kritis</div>', unsafe_allow_html=True)
        cols = [c for c in ["NO.PART", "SPAREPART", "TIPE MOBIL", "KATEGORI", "STOCK AKHIR"] if c in df.columns]
        kr = df[df["STOCK AKHIR"] <= KRITIS_MAX][cols]
        if kr.empty:
            st.success("Semua stok dalam kondisi aman.")
        else:
            sdf(kr, use_container_width=True, hide_index=True)

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

        judul = f" · {_html.escape(kat)}" if kat != "Semua" else ""
        kpi_cards([
            (f"Jumlah Item{judul}", num(len(v)), "🔩", C_PRIMARY),
            ("Total Stok Akhir", num(v["STOCK AKHIR"].sum()) if "STOCK AKHIR" in v.columns else "0", "📦", C_SUCCESS),
            ("Total Nominal", rp(v["NOMINAL TOTAL"].sum()) if "NOMINAL TOTAL" in v.columns else "Rp 0", "💰", C_INFO),
        ])
        st.caption(f"Menampilkan {len(v):,} dari {len(df):,} item")
        sdf(v, use_container_width=True, hide_index=True, height=480)
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
        sdf(g, use_container_width=True, hide_index=True)
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
        sdf(d, use_container_width=True, hide_index=True, height=380)
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
                    sdf(sim[[c for c in ["NO.PART", "SPAREPART", "TIPE MOBIL"] if c in sim.columns]],
                                 hide_index=True, use_container_width=True)
                st.button("➕ Daftarkan di Master Sparepart", type="primary",
                          on_click=goto, args=("🛠️  Master Sparepart",),
                          kwargs={"prefill_no_part": kode_raw.strip()})
            else:
                row = hit.iloc[0]
                no_part, nama = str(row["NO.PART"]), str(row.get("SPAREPART", ""))
                stok = int(row.get("STOCK AKHIR", 0))
                md(
                    f"""<div class="partcard"><h3>✅ {nama}</h3><div class="g">
                    <div><small>No. Part</small><b>{no_part}</b></div>
                    <div><small>Tipe Mobil</small><b>{row.get('TIPE MOBIL', '-') or '-'}</b></div>
                    <div><small>Kategori</small><b>{row.get('KATEGORI', '-') or '-'}</b></div>
                    <div><small>Pricelist</small><b>{rp(row.get('PRICELIST', 0))}</b></div>
                    <div><small>Stok Akhir</small><b>{num(stok)}</b></div></div></div>""",
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
# 4b. IMPORT TRANSAKSI MASUK / KELUAR (ADMIN)
# =========================================================
elif page == "imptrx" and is_admin:
    topbar("Import Transaksi Masuk / Keluar", "📑")
    df = load_stock()
    master = {}
    if not df.empty and "NO.PART" in df.columns:
        for _, r in df.iterrows():
            master.setdefault(_norm(r["NO.PART"]), (str(r["NO.PART"]), str(r.get("SPAREPART", "")), int(r.get("STOCK AKHIR", 0))))

    st.warning(f"Stok di sistem dimulai dari stok akhir Oktober 2026. Agar stok tidak terhitung ganda, "
               f"hanya transaksi **mulai {STOK_CUTOFF:%d-%m-%Y}** yang diimport secara default (bisa diubah di bawah).")

    with st.container(border=True):
        st.markdown('<div class="panel-title">1. Upload file Excel transaksi</div>', unsafe_allow_html=True)
        st.caption("Bisa upload file MASUK dan KELUAR sekaligus. Semua sheet bulanan dibaca otomatis. "
                   "Keterangan transaksi diisi otomatis dari PLAT NOMOR dan ASURANSI.")
        files = st.file_uploader("Pilih file (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="trx_files")
        c1, c2, c3 = st.columns(3)
        jenis_opt = c1.radio("Jenis transaksi", ["Otomatis", "MASUK", "KELUAR"], horizontal=True,
                             help="Otomatis = dari nama file / judul sheet")
        dari = c2.date_input("Dari tanggal", value=STOK_CUTOFF, format="DD/MM/YYYY")
        sampai = c3.date_input("Sampai tanggal", value=now_wib().date(), format="DD/MM/YYYY")
        o1, o2 = st.columns(2)
        incl_nodate = o1.checkbox("Sertakan baris tanpa tanggal", value=False)
        cek_stok = o2.checkbox("Tolak KELUAR jika stok tidak cukup", value=True)

    if files:
        frames = []
        for f in files:
            d, note = parse_trx_file(f)
            (st.success if d is not None else st.error)(f"**{f.name}** — {note}")
            if d is not None:
                frames.append(d)
        if frames:
            trx = pd.concat(frames, ignore_index=True)
            if jenis_opt != "Otomatis":
                trx["JENIS"] = jenis_opt
            if (trx["JENIS"] == "").any():
                st.error("Jenis (MASUK/KELUAR) tidak terdeteksi untuk sebagian file. Pilih jenisnya manual di atas.")
                st.stop()

            trx["KEY"] = trx["NO.PART"].map(_norm)
            in_range = trx["TANGGAL"].notna() & (trx["TANGGAL"] >= pd.Timestamp(dari)) & (trx["TANGGAL"] <= pd.Timestamp(sampai))
            trx["STATUS"] = "SIAP"
            trx.loc[trx["KEY"] == "", "STATUS"] = "NO.PART KOSONG"
            trx.loc[(trx["STATUS"] == "SIAP") & ~trx["KEY"].isin(master.keys()), "STATUS"] = "BELUM ADA DI MASTER"
            if incl_nodate:
                trx.loc[trx["TANGGAL"].notna() & ~in_range, "STATUS"] = "DI LUAR TANGGAL"
            else:
                trx.loc[~in_range & trx["TANGGAL"].notna(), "STATUS"] = "DI LUAR TANGGAL"
                trx.loc[trx["TANGGAL"].isna(), "STATUS"] = "TANPA TANGGAL"

            # ---- 2. part belum ada di master ----
            unk_rows = trx[trx["STATUS"] == "BELUM ADA DI MASTER"].drop_duplicates("KEY")
            if not unk_rows.empty:
                with st.container(border=True):
                    st.markdown(f'<div class="panel-title">2. Part belum ada di Master ({len(unk_rows)} part)</div>',
                                unsafe_allow_html=True)
                    st.caption("Lengkapi KATEGORI (sudah ditebak otomatis dari nama part, silakan koreksi), "
                               "lalu tambahkan ke Master. Stok awal part baru = 0.")
                    unk = pd.DataFrame({
                        "NO.PART": unk_rows["NO.PART"].values,
                        "SPAREPART": unk_rows["SPAREPART"].values,
                        "TIPE MOBIL": unk_rows["MEREK"].values,
                        "KATEGORI": [guess_kategori(x) for x in unk_rows["SPAREPART"]],
                        "PRICELIST": unk_rows["HARGA"].values,
                    })
                    edited = st.data_editor(
                        unk, hide_index=True, use_container_width=True, key="unk_editor", disabled=["NO.PART"],
                        column_config={
                            "KATEGORI": st.column_config.SelectboxColumn("KATEGORI", options=kategori_options(df), required=True),
                            "PRICELIST": st.column_config.NumberColumn("PRICELIST", format="%d", min_value=0),
                        })
                    if st.button(f"➕ Tambahkan {len(edited)} part ke Master", type="primary", key="add_unk"):
                        if edited["KATEGORI"].isna().any() or (edited["KATEGORI"] == "").any():
                            swal("warning", "Kategori belum lengkap", "Pilih KATEGORI untuk semua part dulu.")
                        else:
                            prog = st.progress(0.0, text="Menambahkan ke master...")
                            ok_n, fails = 0, []
                            recs = edited.to_dict("records")
                            for i, r in enumerate(recs, start=1):
                                try:
                                    post_payload({"action": "addNewPart", "no_part": r["NO.PART"], "sparepart": r["SPAREPART"],
                                                  "tipe_mobil": r["TIPE MOBIL"], "kategori": r["KATEGORI"],
                                                  "stock_awal": 0, "pricelist": int(r["PRICELIST"] or 0)})
                                    ok_n += 1
                                except Exception as e:
                                    fails.append({"NO.PART": r["NO.PART"], "ALASAN": str(e)})
                                prog.progress(i / len(recs), text=f"{i} / {len(recs)}")
                            st.cache_data.clear()
                            if fails:
                                st.warning(f"{ok_n} berhasil, {len(fails)} gagal:")
                                sdf(pd.DataFrame(fails))
                            else:
                                flash("success", "Master diperbarui", f"{ok_n} part baru ditambahkan. Silakan lanjut import transaksi.")
                                st.rerun()

            # ---- cek stok berjalan untuk KELUAR ----
            run = {k: v[2] for k, v in master.items()}
            order = trx[trx["STATUS"] == "SIAP"].assign(_o=lambda d: (d["JENIS"] == "KELUAR").astype(int)) \
                .sort_values(["TANGGAL", "_o"], kind="stable")
            for idx, r in order.iterrows():
                if r["JENIS"] == "MASUK":
                    run[r["KEY"]] = run.get(r["KEY"], 0) + int(r["QTY"])
                else:
                    if cek_stok and int(r["QTY"]) > run.get(r["KEY"], 0):
                        trx.loc[idx, "STATUS"] = "STOK KURANG"
                    else:
                        run[r["KEY"]] = run.get(r["KEY"], 0) - int(r["QTY"])

            # ---- 3. pratinjau & import ----
            n_ok = int((trx["STATUS"] == "SIAP").sum())
            with st.container(border=True):
                st.markdown('<div class="panel-title">3. Pratinjau & Import</div>', unsafe_allow_html=True)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total baris", num(len(trx)))
                m2.metric("Siap diimport", num(n_ok))
                m3.metric("Belum ada di master", num(int((trx["STATUS"] == "BELUM ADA DI MASTER").sum())))
                m4.metric("Dilewati lainnya", num(len(trx) - n_ok - int((trx["STATUS"] == "BELUM ADA DI MASTER").sum())))
                st.caption("Dilewati: di luar rentang tanggal, tanpa tanggal, NO.PART kosong, atau stok tidak cukup.")
                show = trx.copy()
                show["TANGGAL"] = show["TANGGAL"].dt.strftime("%d/%m/%Y").fillna("-")
                sdf(show[["STATUS", "JENIS", "TANGGAL", "PLAT", "ASURANSI", "SPAREPART", "NO.PART", "QTY", "HARGA", "SHEET"]],
                    height=380)
                if n_ok and st.button(f"🚀 Import {num(n_ok)} transaksi", type="primary", key="go_trx"):
                    rows = trx[trx["STATUS"] == "SIAP"].sort_values("TANGGAL", kind="stable").to_dict("records")
                    prog = st.progress(0.0, text="Mengirim transaksi...")
                    ok_n, fails = 0, []
                    for i, r in enumerate(rows, start=1):
                        m_no, m_name, _ = master[r["KEY"]]
                        ket = " | ".join([x for x in [r["PLAT"], r["ASURANSI"]] if x])
                        try:
                            post_payload({"action": "addTransaction", "type": r["JENIS"], "no_part": m_no,
                                          "sparepart": m_name, "qty": int(r["QTY"]), "keterangan": ket,
                                          "tanggal": r["TANGGAL"].strftime("%Y-%m-%d")})
                            ok_n += 1
                        except Exception as e:
                            fails.append({"NO.PART": m_no, "JENIS": r["JENIS"], "ALASAN": str(e)})
                        prog.progress(i / len(rows), text=f"Mengirim {i} / {len(rows)}")
                    st.cache_data.clear()
                    if fails:
                        swal("warning", "Import selesai sebagian", f"{ok_n} berhasil, {len(fails)} gagal.")
                        st.warning(f"{ok_n} berhasil, {len(fails)} gagal:")
                        sdf(pd.DataFrame(fails))
                    else:
                        swal("success", "Import berhasil!", f"{ok_n} transaksi tersimpan.")
                        st.success(f"{ok_n} transaksi berhasil diimport.")

# =========================================================
# 5. MASTER SPAREPART (ADMIN)
# =========================================================
elif page == "master" and is_admin:
    topbar("Master Sparepart", "🛠️")
    tab_add, tab_imp, tab_edit, tab_del = st.tabs(["➕ Tambah Baru", "📤 Import Excel/CSV", "✏️ Edit Sparepart", "🗑️ Hapus Sparepart"])
    df_m = load_stock()
    has_data = not df_m.empty and "NO.PART" in df_m.columns

    with tab_add:
        prefill = st.session_state.pop("prefill_no_part", "")
        if prefill:
            st.info(f"No. Part **{prefill}** belum ada di master. Lengkapi datanya di bawah.")
        kat_opts = kategori_options(df_m if has_data else None)
        with st.container(border=True):
            with st.form("form_master_add", clear_on_submit=True):
                c1, c2 = st.columns(2)
                no_part = c1.text_input("NO.PART *", value=prefill).strip()
                sparepart = c2.text_input("SPAREPART *").strip()
                c3, c4 = st.columns(2)
                tipe = c3.text_input("TIPE MOBIL").strip()
                kategori = c4.selectbox("KATEGORI *", kat_opts, index=None, placeholder="Pilih / ketik untuk mencari kategori")
                c5, c6 = st.columns(2)
                s_awal = c5.number_input("STOCK AWAL", min_value=0, step=1, value=0)
                price = c6.number_input("PRICELIST", min_value=0, step=500, value=0)
                ok = st.form_submit_button("💾 Simpan Sparepart Baru", type="primary", use_container_width=True)
            if ok:
                if not no_part or not sparepart or not kategori:
                    swal("warning", "Data belum lengkap", "NO.PART, SPAREPART, dan KATEGORI wajib diisi.")
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

    with tab_imp:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Import Master Sparepart dari Excel / CSV</div>', unsafe_allow_html=True)
            st.caption("Upload satu atau banyak file sekaligus. Kolom dikenali otomatis dari judul kolomnya: "
                       "NO.PART, SPAREPART, TIPE/MODEL, KATEGORI, STOCK AKHIR, HARGA PL. "
                       "Sistem dimulai bersih: yang diambil hanya STOCK AKHIR sebagai stok awal di sistem baru. "
                       "Data transaksi masuk/keluar di file lama diabaikan.")
            tpl = pd.DataFrame([{"NO.PART": "12345-67890", "SPAREPART": "CONTOH BUMPER DEPAN", "TIPE MOBIL": "AVANZA",
                                 "KATEGORI": "BUMPER", "STOCK AWAL": 2, "PRICELIST": 1500000}])
            st.download_button("📗 Unduh Template Excel", to_excel({"Template": tpl}), "template_master_sparepart.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            files = st.file_uploader("Pilih file (.xlsx / .csv)", type=["xlsx", "csv"], accept_multiple_files=True, key="imp_files")
            skip_zero = st.checkbox("Lewati part yang stok akhirnya 0", value=True)
            use_fname = st.checkbox("Jika kolom KATEGORI kosong, ambil dari nama file (PART ACCU2024.xlsx → ACCU)", value=True)
            default_kat = st.selectbox("Kategori cadangan (dipakai jika kategori masih kosong)",
                                       kategori_options(df_m if has_data else None), index=None, placeholder="Opsional")

            if files:
                frames = []
                for f in files:
                    d, note = parse_upload(f)
                    (st.success if d is not None else st.error)(f"**{f.name}** — {note}")
                    if d is not None:
                        frames.append(d)
                if frames:
                    imp = pd.concat(frames, ignore_index=True)
                    imp["KATEGORI"] = imp["KATEGORI"].map(clean_kategori)
                    if use_fname:
                        blank = imp["KATEGORI"] == ""
                        imp.loc[blank, "KATEGORI"] = imp.loc[blank, "_STEM"].map(clean_kategori)
                    if default_kat:
                        imp.loc[imp["KATEGORI"] == "", "KATEGORI"] = default_kat
                    imp["NO.PART"] = imp["NO.PART"].str.strip()

                    existing = set(df_m["NO.PART"].astype(str).str.strip().str.upper()) if has_data else set()
                    key = imp["NO.PART"].str.upper()
                    dup_file = key.duplicated(keep="first") & ~(skip_zero & (imp["STOCK AWAL"] <= 0))
                    imp["STATUS"] = "BARU"
                    imp.loc[imp["KATEGORI"] == "", "STATUS"] = "KATEGORI KOSONG"
                    if skip_zero:
                        imp.loc[imp["STOCK AWAL"] <= 0, "STATUS"] = "STOK 0"
                    imp.loc[dup_file, "STATUS"] = "DUPLIKAT DI FILE"
                    imp.loc[key.isin(existing), "STATUS"] = "SUDAH ADA"

                    n_new = int((imp["STATUS"] == "BARU").sum())
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total baris terbaca", num(len(imp)))
                    m2.metric("Siap diimport (baru)", num(n_new))
                    m3.metric("Dilewati", num(len(imp) - n_new))
                    st.caption("Dilewati = stok 0, sudah ada di master, duplikat di file, atau kategori kosong.")
                    sdf(imp[["STATUS", "NO.PART", "SPAREPART", "TIPE MOBIL", "KATEGORI", "STOCK AWAL", "PRICELIST", "FILE"]]
                        .rename(columns={"STOCK AWAL": "STOK (dari file)"}), height=360)

                    if n_new and st.button(f"🚀 Import {num(n_new)} data baru", type="primary"):
                        rows = imp[imp["STATUS"] == "BARU"].to_dict("records")
                        prog = st.progress(0.0, text="Mengirim data...")
                        ok_n, fails = 0, []
                        for i, r in enumerate(rows, start=1):
                            try:
                                post_payload({"action": "addNewPart", "no_part": r["NO.PART"], "sparepart": r["SPAREPART"],
                                              "tipe_mobil": r["TIPE MOBIL"], "kategori": r["KATEGORI"],
                                              "stock_awal": int(r["STOCK AWAL"]), "pricelist": int(r["PRICELIST"])})
                                ok_n += 1
                            except Exception as e:
                                fails.append({"NO.PART": r["NO.PART"], "SPAREPART": r["SPAREPART"], "ALASAN": str(e)})
                            prog.progress(i / len(rows), text=f"Mengirim {i} / {len(rows)}")
                        st.cache_data.clear()
                        if fails:
                            swal("warning", "Import selesai sebagian", f"{ok_n} berhasil, {len(fails)} gagal.")
                            st.warning(f"{ok_n} berhasil, {len(fails)} gagal:")
                            sdf(pd.DataFrame(fails))
                        else:
                            swal("success", "Import berhasil!", f"{ok_n} sparepart ditambahkan ke master.")
                            st.success(f"{ok_n} sparepart berhasil ditambahkan ke master.")

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
                        sdf(sim[["NO.PART", "SPAREPART"]], hide_index=True, use_container_width=True)
                elif not q:
                    st.info("Ketik No. Part lalu tekan Enter.")
                else:
                    r = hit.iloc[0]
                    old = str(r["NO.PART"])
                    cur_kat = clean_kategori(r.get("KATEGORI", ""))
                    kat_opts_e = kategori_options(df_m)
                    kat_idx = kat_opts_e.index(cur_kat) if cur_kat in kat_opts_e else None
                    with st.form("form_master_edit"):
                        e1, e2 = st.columns(2)
                        n_no = e1.text_input("NO.PART *", value=old).strip()
                        n_sp = e2.text_input("SPAREPART *", value=str(r.get("SPAREPART", ""))).strip()
                        e3, e4 = st.columns(2)
                        n_tp = e3.text_input("TIPE MOBIL", value=str(r.get("TIPE MOBIL", ""))).strip()
                        n_kt = e4.selectbox("KATEGORI *", kat_opts_e, index=kat_idx, placeholder="Pilih kategori")
                        e5, e6 = st.columns(2)
                        n_sa = e5.number_input("STOCK AWAL", min_value=0, step=1, value=int(r.get("STOCK AWAL", 0)))
                        n_pl = e6.number_input("PRICELIST", min_value=0, step=500, value=int(r.get("PRICELIST", 0)))
                        ok = st.form_submit_button("💾 Simpan Perubahan", type="primary", use_container_width=True)
                    if ok:
                        if not n_no or not n_sp or not n_kt:
                            swal("warning", "Data belum lengkap", "NO.PART, SPAREPART, dan KATEGORI wajib diisi.")
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
            sdf(h, use_container_width=True, hide_index=True, height=480)
            export_buttons(f"Riwayat_{jenis}", h, f"Riwayat Barang {jenis}", key="riw")
