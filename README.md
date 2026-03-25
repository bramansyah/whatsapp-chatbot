# 🤖 SmartBot - WhatsApp Business Chatbot

Chatbot WhatsApp kompleks dengan admin dashboard, menggunakan **WhatsApp Business Cloud API** (Meta Official).

## ✨ Fitur Lengkap

### Bot Engine
- **State Machine** - Multi-level menu navigation dengan 15+ states
- **Auto Reply** - Rule-based auto reply (keyword, regex, exact, contains)
- **FAQ System** - Pencarian FAQ dengan fuzzy matching
- **E-Commerce** - Katalog produk, pemesanan, dan manajemen order
- **Session Management** - Context-aware conversation dengan timeout
- **Human Takeover** - Transfer ke CS manusia kapan saja
- **Broadcast** - Kirim pesan massal ke kontak terdaftar

### Admin Dashboard
- 📊 Dashboard analytics dengan chart
- 👥 Manajemen kontak + chat history
- 📦 CRUD produk & kategori
- 🛒 Manajemen pesanan + update status otomatis
- ❓ CRUD FAQ dengan keyword matching
- 🤖 CRUD Auto Reply rules
- 📢 Broadcast messages dengan filter tags

### WhatsApp API
- Text, Image, Document, Location messages
- Interactive Buttons & List menus
- Template messages
- Reaction emoji
- Read receipts
- Webhook signature verification

## 🚀 Quick Start

### 1. Setup WhatsApp Business API
1. Buat akun di [Meta for Developers](https://developers.facebook.com/)
2. Buat App > pilih WhatsApp
3. Dapatkan `Phone Number ID` dan `Access Token`
4. Setup Webhook URL: `https://your-domain.com/webhook`

### 2. Install & Run

```bash
# Clone & masuk folder
cd whatsapp-chatbot

# Install dependencies
pip install -r requirements.txt

# Copy .env
cp .env.example .env
# Edit .env dan isi credential WhatsApp

# Jalankan
python app.py
```

### 3. Akses Admin Panel
Buka `http://localhost:5000/admin`
- Username: `admin`
- Password: `admin123`

## 📁 Struktur Proyek

```
whatsapp-chatbot/
├── app.py                 # Flask server + routes + admin
├── config.py              # Konfigurasi
├── models.py              # Database models (12 tabel)
├── chatbot_engine.py      # Brain: state machine + NLP
├── whatsapp_api.py        # WhatsApp Cloud API handler
├── requirements.txt       # Python dependencies
├── .env.example           # Template environment variables
└── templates/
    ├── base.html           # Base layout + sidebar
    ├── login.html          # Login page
    ├── dashboard.html      # Analytics dashboard
    ├── contacts.html       # Contact list
    ├── contact_detail.html # Chat history + send message
    ├── faq_list.html       # FAQ management
    ├── faq_form.html       # Add/edit FAQ
    ├── auto_reply_list.html# Auto reply rules
    ├── auto_reply_form.html# Add/edit auto reply
    ├── product_list.html   # Product catalog
    ├── product_form.html   # Add/edit product
    ├── order_list.html     # Order management
    ├── order_detail.html   # Order detail + status update
    ├── broadcast_list.html # Broadcast history
    └── broadcast_form.html # Send broadcast
```

## 🔧 Flow Chatbot

```
User kirim pesan
  → Webhook menerima
    → Parse message
      → Check blocked?
      → Log message
      → Get/create session
      → Check human takeover
      → Normalize text
      → Check global commands (menu, bot, stop)
      → Check auto-reply rules
      → Process by state machine
        → WELCOME → MAIN_MENU
        → PRODUCT_MENU → PRODUCT_DETAIL
        → ORDER flow (select → qty → address → confirm → payment)
        → CHECK_ORDER
        → FAQ_MENU → FAQ_SEARCH (fuzzy matching)
        → CONTACT_CS → HUMAN_TAKEOVER
      → Send response(s)
      → Log outbound
      → Mark as read
```

## ⚠️ Catatan Penting
- Gunakan **HTTPS** untuk webhook (wajib dari Meta)
- Gunakan **ngrok** untuk testing lokal: `ngrok http 5000`
- Rate limit WhatsApp: 80 pesan/detik (Business API)
- Ganti `ADMIN_PASSWORD` di production!
