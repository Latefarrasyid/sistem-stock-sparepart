import os
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Sistem Stock Sparepart",
    page_icon="📦",
    layout="wide",
)


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


def is_valid_gas_url(url: str) -> bool:
    return url.startswith("https://script.google.com/macros/s/") and url.endswith("/exec")


# ---------------------------------------------------------
# SISTEM LOGIN & HAK AKSES (ADMIN vs USER)
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = ""


def login_page():
    st.title("🔐 Login Sistem Stock Sparepart")
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk", use_container_width=True)

            if submitted:
                if username == ADMIN_USER and password == ADMIN_PASS:
                    st.session_state.logged_in = True
                    st.session_state.role = "admin"
                    st.session_state.username = username
                    st.rerun()
                elif username == VIEWER_USER and password == VIEWER_PASS:
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Username atau password salah.")


if not is_valid_gas_url(GAS_URL):
    st.error("`GAS_URL` belum dikonfigurasi atau tidak berakhiran `/exec`.")
    st.info("Tambahkan `GAS_URL` pada menu **Settings > Secrets** di Streamlit Cloud.")
    st.stop()

if not st.session_state.logged_in:
    login_page()
    st.stop()


# ---------------------------------------------------------
# FUNGSI KOMUNIKASI KE GOOGLE APPS SCRIPT
# ---------------------------------------------------------
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
    return pd.DataFrame(data)


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


# ---------------------------------------------------------
# SIDEBAR & NAVIGASI SESUAI ROLE
# ---------------------------------------------------------
is_admin = st.session_state.role == "admin"

st.sidebar.markdown(f"👤 **{st.session_state.username}** (`{st.session_state.role.upper()}`)")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = ""
    st.rerun()

st.sidebar.divider()

if is_admin:
    menu_options = [
        "Dashboard & Stok",
        "Input Barang Masuk / Keluar",
        "Kelola Master Sparepart (CRUD)",
        "Riwayat Transaksi",
    ]
else:
    menu_options = [
        "Dashboard & Stok",
        "Riwayat Transaksi",
    ]

menu = st.sidebar.radio("Navigasi", menu_options)

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.title("📦 Sistem Manajemen Stock Sparepart")

# ---------------------------------------------------------
# 1. DASHBOARD & STOK (ADMIN & USER)
# ---------------------------------------------------------
if menu == "Dashboard & Stok":
    st.subheader("Data Stok & Ringkasan")
    try:
        df = fetch_stock()
    except Exception as e:
        st.error(f"Error memuat stok: {e}")
        st.stop()

    if df.empty:
        st.info("Belum ada data di tab `STOCK`.")
    else:
        for col in ["STOCK AWAL", "KELUAR", "MASUK", "PRICELIST", "NOMINAL TOTAL", "STOCK AKHIR"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Jumlah Item Part", f"{len(df):,}")
        c2.metric("Total Stok Akhir", f"{int(df['STOCK AKHIR'].sum()):,}" if "STOCK AKHIR" in df.columns else "0")
        c3.metric("Total Nominal Stok", f"Rp {df['NOMINAL TOTAL'].sum():,.0f}" if "NOMINAL TOTAL" in df.columns else "Rp 0")
        c4.metric("Stok Kritis (<= 2)", f"{int((df['STOCK AKHIR'] <= 2).sum()):,}" if "STOCK AKHIR" in df.columns else "0")

        st.divider()

        f1, f2, f3 = st.columns([2, 1, 1])
        cari = f1.text_input("Cari Sparepart / No. Part / Tipe Mobil")

        kat_opts = ["Semua"]
        if "KATEGORI" in df.columns:
            kat_opts += sorted([str(x) for x in df["KATEGORI"].dropna().unique() if str(x).strip()])
        kat_pilih = f2.selectbox("Kategori", kat_opts)
        kritis_only = f3.checkbox("Hanya stok <= 2")

        view_df = df.copy()
        if cari:
            mask = pd.Series(False, index=view_df.index)
            for col in ["SPAREPART", "NO.PART", "TIPE MOBIL"]:
                if col in view_df.columns:
                    mask = mask | view_df[col].astype(str).str.contains(cari, case=False, na=False)
            view_df = view_df[mask]

        if kat_pilih != "Semua" and "KATEGORI" in view_df.columns:
            view_df = view_df[view_df["KATEGORI"].astype(str) == kat_pilih]

        if kritis_only and "STOCK AKHIR" in view_df.columns:
            view_df = view_df[view_df["STOCK AKHIR"] <= 2]

        st.dataframe(view_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# 2. INPUT BARANG MASUK / KELUAR (KHUSUS ADMIN)
# ---------------------------------------------------------
elif menu == "Input Barang Masuk / Keluar" and is_admin:
    st.subheader("Input Transaksi Barang Masuk / Keluar")
    try:
        df_stock = fetch_stock()
    except Exception as e:
        st.error(f"Error memuat master part: {e}")
        st.stop()

    if df_stock.empty or "NO.PART" not in df_stock.columns or "SPAREPART" not in df_stock.columns:
        st.warning("Master sparepart kosong. Tambahkan item dulu di menu **Kelola Master Sparepart (CRUD)**.")
        st.stop()

    jenis = st.selectbox("Jenis Transaksi", ["MASUK", "KELUAR"])
    item_map = {
        f"{row['NO.PART']} — {row['SPAREPART']}": (str(row["NO.PART"]), str(row["SPAREPART"]))
        for _, row in df_stock.iterrows()
        if str(row.get("NO.PART", "")).strip()
    }
    dipilih = st.selectbox("Pilih Sparepart", list(item_map.keys()))
    no_part, nama_part = item_map[dipilih]

    stok_tersedia = None
    row_match = df_stock[df_stock["NO.PART"].astype(str) == no_part]
    if not row_match.empty and "STOCK AKHIR" in row_match.columns:
        stok_tersedia = pd.to_numeric(row_match["STOCK AKHIR"].iloc[0], errors="coerce")
        st.info(f"Stok akhir saat ini untuk **{no_part}**: **{int(stok_tersedia) if pd.notna(stok_tersedia) else '-'}**")

    with st.form("form_trx", clear_on_submit=True):
        qty = st.number_input("QTY", min_value=1, step=1, value=1)
        keterangan = st.text_input("Keterangan (No. PO / Mekanik / Catatan)")
        submit_trx = st.form_submit_button("Simpan Transaksi")

        if submit_trx:
            if jenis == "KELUAR" and pd.notna(stok_tersedia) and qty > stok_tersedia:
                st.error(f"Qty keluar ({qty}) melebihi stok akhir tersedia ({int(stok_tersedia)}).")
            else:
                try:
                    res = post_payload({
                        "action": "addTransaction",
                        "type": jenis,
                        "no_part": no_part,
                        "sparepart": nama_part,
                        "qty": int(qty),
                        "keterangan": keterangan,
                    })
                    st.cache_data.clear()
                    st.success(res.get("message", "Transaksi berhasil disimpan!"))
                except Exception as e:
                    st.error(f"Gagal menyimpan transaksi: {e}")

# ---------------------------------------------------------
# 3. KELOLA MASTER SPAREPART - CRUD (KHUSUS ADMIN)
# ---------------------------------------------------------
elif menu == "Kelola Master Sparepart (CRUD)" and is_admin:
    st.subheader("Kelola Master Sparepart (Tambah / Edit / Hapus)")
    tab_add, tab_edit, tab_del = st.tabs(["➕ Tambah Baru", "✏️ Edit Sparepart", "🗑️ Hapus Sparepart"])

    # TAB TAMBAH
    with tab_add:
        with st.form("form_master_add", clear_on_submit=True):
            c1, c2 = st.columns(2)
            no_part = c1.text_input("NO.PART *").strip()
            sparepart = c2.text_input("SPAREPART *").strip()

            c3, c4 = st.columns(2)
            tipe_mobil = c3.text_input("TIPE MOBIL").strip()
            kategori = c4.text_input("KATEGORI").strip()

            c5, c6 = st.columns(2)
            stock_awal = c5.number_input("STOCK AWAL", min_value=0, step=1, value=0)
            pricelist = c6.number_input("PRICELIST", min_value=0, step=500, value=0)

            submit_part = st.form_submit_button("Simpan Sparepart Baru")
            if submit_part:
                if not no_part or not sparepart:
                    st.error("`NO.PART` dan `SPAREPART` wajib diisi.")
                else:
                    try:
                        res = post_payload({
                            "action": "addNewPart",
                            "no_part": no_part,
                            "sparepart": sparepart,
                            "tipe_mobil": tipe_mobil,
                            "kategori": kategori,
                            "stock_awal": int(stock_awal),
                            "pricelist": int(pricelist),
                        })
                        st.cache_data.clear()
                        st.success(res.get("message", "Sparepart berhasil ditambahkan!"))
                    except Exception as e:
                        st.error(f"Gagal menambah sparepart: {e}")

    # TAB EDIT
    with tab_edit:
        try:
            df_edit = fetch_stock()
        except Exception as e:
            st.error(f"Error memuat data: {e}")
            df_edit = pd.DataFrame()

        if df_edit.empty or "NO.PART" not in df_edit.columns:
            st.info("Belum ada data sparepart untuk diedit.")
        else:
            part_list = df_edit["NO.PART"].astype(str).tolist()
            selected_part = st.selectbox("Pilih NO.PART yang akan diedit", part_list, key="edit_select")
            row_data = df_edit[df_edit["NO.PART"].astype(str) == selected_part].iloc[0]

            with st.form("form_master_edit"):
                e1, e2 = st.columns(2)
                new_no_part = e1.text_input("NO.PART *", value=str(row_data.get("NO.PART", ""))).strip()
                new_sparepart = e2.text_input("SPAREPART *", value=str(row_data.get("SPAREPART", ""))).strip()

                e3, e4 = st.columns(2)
                new_tipe = e3.text_input("TIPE MOBIL", value=str(row_data.get("TIPE MOBIL", ""))).strip()
                new_kategori = e4.text_input("KATEGORI", value=str(row_data.get("KATEGORI", ""))).strip()

                e5, e6 = st.columns(2)
                new_stock_awal = e5.number_input(
                    "STOCK AWAL",
                    min_value=0,
                    step=1,
                    value=int(pd.to_numeric(row_data.get("STOCK AWAL", 0), errors="coerce") or 0),
                )
                new_pricelist = e6.number_input(
                    "PRICELIST",
                    min_value=0,
                    step=500,
                    value=int(pd.to_numeric(row_data.get("PRICELIST", 0), errors="coerce") or 0),
                )

                submit_edit = st.form_submit_button("Simpan Perubahan")
                if submit_edit:
                    if not new_no_part or not new_sparepart:
                        st.error("`NO.PART` dan `SPAREPART` wajib diisi.")
                    else:
                        try:
                            res = post_payload({
                                "action": "updatePart",
                                "old_no_part": selected_part,
                                "no_part": new_no_part,
                                "sparepart": new_sparepart,
                                "tipe_mobil": new_tipe,
                                "kategori": new_kategori,
                                "stock_awal": int(new_stock_awal),
                                "pricelist": int(new_pricelist),
                            })
                            st.cache_data.clear()
                            st.success(res.get("message", "Data sparepart berhasil diperbarui!"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal memperbarui data: {e}")

    # TAB HAPUS
    with tab_del:
        try:
            df_del = fetch_stock()
        except Exception as e:
            st.error(f"Error memuat data: {e}")
            df_del = pd.DataFrame()

        if df_del.empty or "NO.PART" not in df_del.columns:
            st.info("Belum ada data sparepart untuk dihapus.")
        else:
            del_options = {
                f"{r['NO.PART']} — {r['SPAREPART']}": str(r["NO.PART"])
                for _, r in df_del.iterrows()
                if str(r.get("NO.PART", "")).strip()
            }
            del_label = st.selectbox("Pilih Sparepart yang akan dihapus", list(del_options.keys()), key="del_select")
            del_no_part = del_options[del_label]

            st.warning(f"Perhatian: Baris dengan NO.PART **{del_no_part}** akan dihapus permanen dari tab `STOCK`.")
            konfirmasi = st.checkbox("Saya yakin ingin menghapus sparepart ini")
            if st.button("Hapus Permanen", disabled=not konfirmasi):
                try:
                    res = post_payload({
                        "action": "deletePart",
                        "no_part": del_no_part,
                    })
                    st.cache_data.clear()
                    st.success(res.get("message", "Sparepart berhasil dihapus!"))
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menghapus sparepart: {e}")

# ---------------------------------------------------------
# 4. RIWAYAT TRANSAKSI (ADMIN & USER)
# ---------------------------------------------------------
elif menu == "Riwayat Transaksi":
    st.subheader("Riwayat Transaksi")
    tab_pilih = st.radio("Pilih Riwayat", ["MASUK", "KELUAR"], horizontal=True)
    try:
        df_hist = fetch_history(tab_pilih)
    except Exception as e:
        st.error(f"Error memuat riwayat: {e}")
        st.stop()

    if df_hist.empty:
        st.info(f"Belum ada data pada tab `{tab_pilih}`.")
    else:
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
