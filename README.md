# Sistem Manajemen Stock Sparepart (Login Admin & User)

Aplikasi manajemen stok berbasis **Streamlit** + **Google Apps Script (GAS)** + **Google Sheets** dengan kontrol akses **Admin (CRUD)** dan **User (View Only)**.

## Pengaturan Secrets di Streamlit Cloud
Tambahkan konfigurasi berikut pada **Settings > Secrets**:
```toml
GAS_URL = "https://script.google.com/macros/s/KODE_DEPLOYMENT_ANDA/exec"
API_KEY = "RAHASIA_API_ANDA_123"

ADMIN_USER = "admin"
ADMIN_PASS = "password_admin_anda"

VIEWER_USER = "user"
VIEWER_PASS = "password_user_anda"
```
