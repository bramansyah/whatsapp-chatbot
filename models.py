"""
=============================================================
  Database Models - SQLAlchemy ORM
  Mengelola semua data chatbot: users, messages, sessions, 
  FAQ, products, orders, analytics
=============================================================
"""
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ======================== USER / CONTACT ========================
class Contact(db.Model):
    """Menyimpan data kontak WhatsApp"""
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), default="Unknown")
    email = db.Column(db.String(150), nullable=True)
    language = db.Column(db.String(5), default="id")
    is_blocked = db.Column(db.Boolean, default=False)
    is_subscribed = db.Column(db.Boolean, default=True)
    tags = db.Column(db.Text, default="")  # comma-separated tags
    notes = db.Column(db.Text, default="")
    total_messages = db.Column(db.Integer, default=0)
    first_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_contact = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    messages = db.relationship("Message", backref="contact", lazy="dynamic")
    sessions = db.relationship("ChatSession", backref="contact", lazy="dynamic")
    orders = db.relationship("Order", backref="contact", lazy="dynamic")

    def __repr__(self):
        return f"<Contact {self.phone_number} - {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "phone_number": self.phone_number,
            "name": self.name,
            "email": self.email,
            "is_blocked": self.is_blocked,
            "total_messages": self.total_messages,
            "first_contact": self.first_contact.isoformat() if self.first_contact else None,
            "last_contact": self.last_contact.isoformat() if self.last_contact else None,
            "tags": self.tags.split(",") if self.tags else [],
        }


# ======================== MESSAGES ========================
class Message(db.Model):
    """Log semua pesan masuk dan keluar"""
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    wa_message_id = db.Column(db.String(100), unique=True, nullable=True)
    direction = db.Column(db.String(10), nullable=False)  # "inbound" or "outbound"
    message_type = db.Column(db.String(20), default="text")  # text, image, document, etc.
    content = db.Column(db.Text, nullable=True)
    media_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default="sent")  # sent, delivered, read, failed
    is_bot_response = db.Column(db.Boolean, default=False)
    matched_keyword = db.Column(db.String(100), nullable=True)
    response_time_ms = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Message {self.direction} - {self.content[:30] if self.content else 'media'}>"

    def to_dict(self):
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "direction": self.direction,
            "message_type": self.message_type,
            "content": self.content,
            "status": self.status,
            "is_bot_response": self.is_bot_response,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


# ======================== CHAT SESSIONS ========================
class ChatSession(db.Model):
    """Mengelola sesi percakapan dengan state machine"""
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    current_state = db.Column(db.String(50), default="MAIN_MENU")
    previous_state = db.Column(db.String(50), nullable=True)
    context_data = db.Column(db.Text, default="{}")  # JSON data for session context
    is_active = db.Column(db.Boolean, default=True)
    is_human_takeover = db.Column(db.Boolean, default=False)  # Live agent takeover
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

    def is_expired(self, timeout_minutes=30):
        if not self.last_activity:
            return True
        return datetime.utcnow() - self.last_activity > timedelta(minutes=timeout_minutes)

    def __repr__(self):
        return f"<Session {self.contact_id} - {self.current_state}>"


# ======================== FAQ ========================
class FAQ(db.Model):
    """Database FAQ yang bisa dikelola admin"""
    __tablename__ = "faqs"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), default="Umum")
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.Text, nullable=False)  # comma-separated keywords
    priority = db.Column(db.Integer, default=0)  # Higher = more priority
    is_active = db.Column(db.Boolean, default=True)
    hit_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FAQ {self.question[:40]}>"

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "keywords": self.keywords.split(",") if self.keywords else [],
            "priority": self.priority,
            "is_active": self.is_active,
            "hit_count": self.hit_count,
        }


# ======================== AUTO REPLY RULES ========================
class AutoReply(db.Model):
    """Rule-based auto reply yang bisa dikustomisasi"""
    __tablename__ = "auto_replies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trigger_type = db.Column(db.String(20), default="keyword")  # keyword, regex, exact, contains
    trigger_value = db.Column(db.Text, nullable=False)
    response_type = db.Column(db.String(20), default="text")  # text, image, button, list, template
    response_content = db.Column(db.Text, nullable=False)
    response_media_url = db.Column(db.String(500), nullable=True)
    response_buttons = db.Column(db.Text, nullable=True)  # JSON buttons
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    schedule_start = db.Column(db.Time, nullable=True)  # Aktif mulai jam
    schedule_end = db.Column(db.Time, nullable=True)  # Aktif sampai jam
    hit_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AutoReply {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger_value": self.trigger_value,
            "response_type": self.response_type,
            "response_content": self.response_content,
            "is_active": self.is_active,
            "hit_count": self.hit_count,
        }


# ======================== PRODUCTS ========================
class Product(db.Model):
    """Katalog produk untuk fitur e-commerce mini"""
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), default="Umum")
    image_url = db.Column(db.String(500), nullable=True)
    stock = db.Column(db.Integer, default=0)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Product {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category": self.category,
            "stock": self.stock,
            "is_available": self.is_available,
        }


# ======================== ORDERS ========================
class Order(db.Model):
    """Manajemen pesanan"""
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    items = db.Column(db.Text, nullable=False)  # JSON list of items
    total_price = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="pending")  # pending, confirmed, shipped, delivered, cancelled
    payment_method = db.Column(db.String(50), nullable=True)
    shipping_address = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Order {self.order_number}>"

    def to_dict(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "contact_id": self.contact_id,
            "total_price": self.total_price,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ======================== BROADCAST ========================
class Broadcast(db.Model):
    """Broadcast / Campaign messages"""
    __tablename__ = "broadcasts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default="text")
    target_tags = db.Column(db.Text, nullable=True)  # Target contacts by tags
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="draft")  # draft, scheduled, sending, completed
    scheduled_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Broadcast {self.name}>"


# ======================== SCHEDULED MESSAGES ========================
class ScheduledMessage(db.Model):
    """Pesan terjadwal"""
    __tablename__ = "scheduled_messages"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default="text")
    scheduled_at = db.Column(db.DateTime, nullable=False)
    is_sent = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(20), nullable=True)  # daily, weekly, monthly
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contact_ref = db.relationship("Contact", backref="scheduled_messages")

    def __repr__(self):
        return f"<ScheduledMessage to {self.contact_id} at {self.scheduled_at}>"


# ======================== ANALYTICS ========================
class Analytics(db.Model):
    """Daily analytics data"""
    __tablename__ = "analytics"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_messages_in = db.Column(db.Integer, default=0)
    total_messages_out = db.Column(db.Integer, default=0)
    unique_contacts = db.Column(db.Integer, default=0)
    new_contacts = db.Column(db.Integer, default=0)
    bot_responses = db.Column(db.Integer, default=0)
    human_responses = db.Column(db.Integer, default=0)
    avg_response_time_ms = db.Column(db.Integer, default=0)
    top_keywords = db.Column(db.Text, default="")  # JSON
    orders_count = db.Column(db.Integer, default=0)
    revenue = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<Analytics {self.date}>"


# ======================== ADMIN USERS ========================
class AdminUser(db.Model):
    """Admin panel users"""
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="admin")  # admin, operator
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<AdminUser {self.username}>"


def init_db(app):
    """Initialize database and create tables"""
    db.init_app(app)
    with app.app_context():
        db.create_all()

        # Create default admin if not exists
        if not AdminUser.query.filter_by(username="admin").first():
            admin = AdminUser(username="admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)

        # Create default FAQ entries
        if FAQ.query.count() == 0:
            default_faqs = [
                FAQ(
                    category="Umum",
                    question="Jam operasional?",
                    answer="Kami beroperasi Senin-Jumat, 08:00-17:00 WIB. Di luar jam tersebut, bot kami siap melayani Anda!",
                    keywords="jam,buka,operasional,tutup,waktu,kapan",
                    priority=10,
                ),
                FAQ(
                    category="Umum",
                    question="Bagaimana cara menghubungi customer service?",
                    answer="Anda bisa menghubungi CS kami melalui:\n📞 Telepon: 021-xxxx-xxxx\n📧 Email: cs@example.com\n💬 WhatsApp: Anda sudah di tempat yang tepat!",
                    keywords="cs,customer service,hubungi,kontak,contact,telepon",
                    priority=9,
                ),
                FAQ(
                    category="Produk",
                    question="Bagaimana cara memesan?",
                    answer="Untuk memesan, ketik *PESAN* atau pilih menu Pemesanan. Ikuti langkah-langkah yang diberikan oleh bot kami.",
                    keywords="pesan,order,beli,cara pesan,pemesanan",
                    priority=8,
                ),
            ]
            db.session.add_all(default_faqs)

        # Create default auto-replies
        if AutoReply.query.count() == 0:
            default_replies = [
                AutoReply(
                    name="Greeting",
                    trigger_type="keyword",
                    trigger_value="halo,hai,hi,hello,hey,assalamualaikum,selamat pagi,selamat siang,selamat sore,selamat malam",
                    response_type="text",
                    response_content="Halo! 👋 Selamat datang di *{bot_name}*!\n\nSaya adalah asisten virtual yang siap membantu Anda.\n\nSilakan pilih menu:\n1️⃣ Info Produk\n2️⃣ Pemesanan\n3️⃣ Cek Status Pesanan\n4️⃣ FAQ / Bantuan\n5️⃣ Hubungi CS\n\nKetik angka untuk memilih menu.",
                    priority=100,
                ),
                AutoReply(
                    name="Thank You",
                    trigger_type="keyword",
                    trigger_value="terima kasih,makasih,thanks,thank you,thx",
                    response_type="text",
                    response_content="Sama-sama! 😊 Senang bisa membantu Anda.\n\nJika ada pertanyaan lain, jangan ragu untuk menghubungi kami kembali.\n\nKetik *MENU* untuk kembali ke menu utama.",
                    priority=90,
                ),
            ]
            db.session.add_all(default_replies)

        db.session.commit()
