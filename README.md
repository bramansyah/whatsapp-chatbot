# 🤖 SmartBot - Chatbot WhatsApp Bisnis

Chatbot WhatsApp lengkap dengan panel admin, menggunakan **WhatsApp Business Cloud API** (resmi dari Meta).

---

## ✨ Fitur Lengkap

### Mesin Bot
- **Alur Percakapan Otomatis** - Navigasi menu bertingkat dengan 15+ kondisi
- **Balasan Otomatis** - Aturan balasan berdasarkan kata kunci, regex, teks persis, atau mengandung kata tertentu
- **Sistem FAQ** - Pencarian FAQ otomatis dengan pencocokan kata mirip (fuzzy matching)
- **Toko Online Mini** - Katalog produk, pemesanan, dan pengelolaan pesanan langsung dari WhatsApp
- **Manajemen Sesi** - Percakapan sadar konteks dengan batas waktu otomatis
- **Alih ke CS** - Transfer ke customer service manusia kapan saja
- **Pesan Siaran** - Kirim pesan massal ke semua kontak yang terdaftar

### Panel Admin (Dashboard)
- 📊 Dashboard statistik dengan grafik harian
- 👥 Kelola kontak + riwayat percakapan
- 📦 Tambah/ubah/hapus produk & kategori
- 🛒 Kelola pesanan + update status otomatis dikirim ke pelanggan via WA
- ❓ Tambah/ubah/hapus FAQ dengan pencocokan kata kunci
- 🤖 Tambah/ubah/hapus aturan balasan otomatis
- 📢 Kirim pesan siaran (broadcast) dengan filter tag

### API WhatsApp yang Didukung
- Pesan teks, gambar, dokumen, lokasi
- Tombol interaktif & menu daftar
- Pesan template
- Reaksi emoji
- Tanda sudah dibaca
- Verifikasi tanda tangan webhook

---

## 🚀 Cara Memulai

### Langkah 1: Daftar WhatsApp Business API

1. Buat akun di [Meta for Developers](https://developers.facebook.com/)
2. Buat Aplikasi baru > pilih **WhatsApp**
3. Dapatkan `Phone Number ID` dan `Access Token` dari halaman API Setup
4. Catat juga `App Secret` dari menu Settings > Basic

### Langkah 2: Install & Jalankan

```bash
# Clone repositori ini
git clone https://github.com/bramansyah/whatsapp-chatbot.git
cd whatsapp-chatbot

# Install semua dependensi Python
pip install -r requirements.txt

# Salin file konfigurasi
cp .env.example .env

# Buka file .env dan isi dengan kredensial WhatsApp kamu
# (gunakan notepad, nano, atau editor lain)
```

**Isi file `.env` seperti ini:**
```
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxx...
WHATSAPP_VERIFY_TOKEN=my_secret_verify_token
WHATSAPP_APP_SECRET=abcdef123456
```

**Jalankan server:**
```bash
python app.py
```

### Langkah 3: Pasang Webhook (Wajib HTTPS)

Untuk testing di komputer lokal, gunakan **ngrok**:
```bash
# Download ngrok dari https://ngrok.com/ lalu jalankan
ngrok http 5000
```

Kamu akan dapat URL seperti `https://xxxx.ngrok.io`. Lalu di **Meta Developer Dashboard**:
1. Masuk ke WhatsApp > Configuration > Edit
2. **Callback URL**: `https://xxxx.ngrok.io/webhook`
3. **Verify Token**: `my_secret_verify_token` (harus sama dengan yang di file .env)
4. Klik **Verify and Save**
5. Subscribe ke field: **messages**

### Langkah 4: Akses Panel Admin

Buka browser dan masuk ke `http://localhost:5000/admin`
- Nama pengguna: `admin`
- Kata sandi: `admin123`

**Yang bisa dilakukan di panel admin:**
- **Dashboard** — Lihat statistik pesan, kontak, pesanan dalam bentuk grafik
- **Kontak** — Lihat semua kontak, riwayat chat, kirim pesan manual, blokir/buka blokir
- **Produk** — Tambah produk baru (akan muncul di katalog bot otomatis)
- **Pesanan** — Kelola pesanan masuk, ubah status (pelanggan otomatis dapat notifikasi WA)
- **FAQ** — Buat pertanyaan + jawaban + kata kunci (bot otomatis jawab)
- **Balasan Otomatis** — Buat aturan balasan kustom (keyword/regex/exact)
- **Broadcast** — Kirim pesan massal ke semua kontak sekaligus

---

## 📁 Struktur Proyek

```
whatsapp-chatbot/
├── app.py                  # Server Flask + halaman admin + API
├── config.py               # Konfigurasi aplikasi
├── models.py               # Model database (12 tabel)
├── chatbot_engine.py       # Otak bot: alur percakapan + pencarian FAQ
├── whatsapp_api.py         # Penghubung ke API WhatsApp Cloud
├── requirements.txt        # Daftar pustaka Python
├── .env.example            # Contoh file konfigurasi
└── templates/
    ├── base.html            # Template dasar + sidebar
    ├── login.html           # Halaman login
    ├── dashboard.html       # Halaman dashboard statistik
    ├── contacts.html        # Daftar kontak
    ├── contact_detail.html  # Detail kontak + riwayat chat
    ├── faq_list.html        # Daftar FAQ
    ├── faq_form.html        # Formulir tambah/edit FAQ
    ├── auto_reply_list.html # Daftar aturan balasan otomatis
    ├── auto_reply_form.html # Formulir tambah/edit balasan otomatis
    ├── product_list.html    # Daftar produk
    ├── product_form.html    # Formulir tambah/edit produk
    ├── order_list.html      # Daftar pesanan
    ├── order_detail.html    # Detail pesanan + update status
    ├── broadcast_list.html  # Riwayat broadcast
    └── broadcast_form.html  # Formulir kirim broadcast
```

---

## 🔧 Alur Kerja Chatbot

```
Pelanggan kirim pesan di WhatsApp
  → Webhook menerima pesan
    → Parsing isi pesan
      → Cek apakah kontak diblokir?
      → Simpan pesan ke database
      → Ambil/buat sesi percakapan
      → Cek apakah sedang mode CS manusia
      → Normalisasi teks
      → Cek perintah global (menu, bot, stop)
      → Cek aturan balasan otomatis
      → Proses berdasarkan kondisi saat ini:
        → SELAMAT DATANG → MENU UTAMA
        → MENU PRODUK → DETAIL PRODUK
        → ALUR PEMESANAN (pilih → jumlah → alamat → konfirmasi → bayar)
        → CEK PESANAN
        → MENU FAQ → CARI FAQ (pencocokan kata mirip)
        → HUBUNGI CS → MODE CS MANUSIA
      → Kirim balasan ke pelanggan
      → Simpan pesan keluar
      → Tandai sudah dibaca
```

---

## 📱 Perintah Chat yang Tersedia

| Pesan | Fungsi |
|-------|--------|
| `Halo` / `Hi` / `Hai` | Memulai percakapan, tampilkan menu utama |
| `1` | Lihat katalog produk |
| `2` | Mulai pemesanan baru |
| `3` | Cek status pesanan |
| `4` | Buka FAQ / bantuan |
| `5` | Hubungi customer service |
| `MENU` | Kembali ke menu utama (dari kondisi manapun) |
| `BOT` | Kembali ke mode bot (setelah CS ambil alih) |
| `STOP` | Berhenti berlangganan |
| `FEEDBACK` | Kirim saran/kritik |

---

## ⚠️ Catatan Penting

- Webhook **wajib menggunakan HTTPS** (persyaratan dari Meta)
- Gunakan **ngrok** untuk testing di komputer lokal: `ngrok http 5000`
- Batas kecepatan WhatsApp Business API: 80 pesan/detik
- **Ganti kata sandi admin** sebelum digunakan di production!
- Access Token dari Meta bersifat sementara (24 jam). Untuk token permanen, buat System User di Meta Business Suite
