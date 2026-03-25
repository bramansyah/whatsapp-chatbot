"""
=============================================================
  Flask App - Main Server
  Webhook handler + Admin Dashboard + REST API
=============================================================
"""
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template, redirect,
    url_for, session, flash, abort
)
from config import *
from models import (
    db, init_db, Contact, Message, ChatSession, FAQ,
    AutoReply, Product, Order, Broadcast, ScheduledMessage,
    Analytics, AdminUser
)
from whatsapp_api import wa_api, WhatsAppAPI
from chatbot_engine import chatbot

# ======================== APP SETUP ========================
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Init DB
init_db(app)


# ======================== AUTH DECORATOR ========================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ======================== WEBHOOK ROUTES ========================
@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """Verify webhook for WhatsApp (GET request from Meta)"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge, 200
    else:
        logger.warning("Webhook verification failed")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    """Receive incoming messages from WhatsApp"""
    try:
        # Verify signature (optional but recommended)
        signature = request.headers.get("X-Hub-Signature-256", "")
        if WHATSAPP_APP_SECRET and signature:
            if not WhatsAppAPI.verify_webhook_signature(request.data, signature):
                logger.warning("Invalid webhook signature")
                return "Unauthorized", 401

        data = request.get_json()
        logger.info(f"Webhook received: {json.dumps(data, indent=2)}")

        # Parse messages
        parsed_messages = WhatsAppAPI.parse_webhook(data)

        for msg in parsed_messages:
            if msg.get("type") == "status_update":
                # Update message status in DB
                _update_message_status(msg)
                continue

            if msg.get("type") in ["text", "image", "document", "audio", "video",
                                     "location", "interactive", "sticker", "contacts"]:
                # Process with chatbot engine
                with app.app_context():
                    chatbot.process_message(
                        phone_number=msg["from"],
                        message=msg.get("content", ""),
                        message_type=msg["type"],
                        message_id=msg.get("message_id"),
                        sender_name=msg.get("name", "Unknown"),
                    )

        return "OK", 200

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return "OK", 200  # Always return 200 to avoid Meta re-sending


def _update_message_status(status_data):
    """Update message status (sent, delivered, read)"""
    try:
        msg = Message.query.filter_by(wa_message_id=status_data.get("message_id")).first()
        if msg:
            msg.status = status_data.get("status", msg.status)
            db.session.commit()
    except Exception as e:
        logger.error(f"Error updating message status: {e}")


# ======================== ADMIN ROUTES ========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        admin = AdminUser.query.filter_by(username=username, is_active=True).first()
        if admin and admin.check_password(password):
            session["admin_id"] = admin.id
            session["admin_username"] = admin.username
            admin.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Username atau password salah!", "error")

    return render_template("login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    """Admin dashboard with analytics"""
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    # Stats
    total_contacts = Contact.query.count()
    total_messages = Message.query.count()
    today_messages = Message.query.filter(
        Message.timestamp >= datetime.combine(today, datetime.min.time())
    ).count()
    active_sessions = ChatSession.query.filter_by(is_active=True).count()
    pending_orders = Order.query.filter_by(status="pending").count()

    # Recent messages
    recent_messages = (
        Message.query.join(Contact)
        .order_by(Message.timestamp.desc())
        .limit(20)
        .all()
    )

    # Weekly chart data
    chart_data = []
    for i in range(7):
        date = today - timedelta(days=6 - i)
        count = Message.query.filter(
            Message.timestamp >= datetime.combine(date, datetime.min.time()),
            Message.timestamp < datetime.combine(date + timedelta(days=1), datetime.min.time()),
        ).count()
        chart_data.append({"date": date.strftime("%d/%m"), "count": count})

    return render_template(
        "dashboard.html",
        total_contacts=total_contacts,
        total_messages=total_messages,
        today_messages=today_messages,
        active_sessions=active_sessions,
        pending_orders=pending_orders,
        recent_messages=recent_messages,
        chart_data=chart_data,
    )


# ======================== CONTACTS API ========================
@app.route("/admin/contacts")
@login_required
def admin_contacts():
    """List all contacts"""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "")

    query = Contact.query
    if search:
        query = query.filter(
            (Contact.phone_number.contains(search)) |
            (Contact.name.contains(search))
        )

    contacts = query.order_by(Contact.last_contact.desc()).paginate(page=page, per_page=20)
    return render_template("contacts.html", contacts=contacts, search=search)


@app.route("/admin/contacts/<int:contact_id>")
@login_required
def admin_contact_detail(contact_id):
    """Contact detail with chat history"""
    contact = Contact.query.get_or_404(contact_id)
    messages = (
        Message.query.filter_by(contact_id=contact_id)
        .order_by(Message.timestamp.desc())
        .limit(100)
        .all()
    )
    orders = Order.query.filter_by(contact_id=contact_id).order_by(Order.created_at.desc()).all()
    return render_template("contact_detail.html", contact=contact, messages=messages, orders=orders)


@app.route("/admin/contacts/<int:contact_id>/send", methods=["POST"])
@login_required
def admin_send_message(contact_id):
    """Send manual message to contact (human agent)"""
    contact = Contact.query.get_or_404(contact_id)
    message_text = request.form.get("message", "").strip()

    if message_text:
        result = wa_api.send_text(contact.phone_number, message_text)
        if result.get("success"):
            msg = Message(
                contact_id=contact_id,
                direction="outbound",
                message_type="text",
                content=message_text,
                is_bot_response=False,
                status="sent",
            )
            db.session.add(msg)
            db.session.commit()
            flash("Pesan berhasil dikirim!", "success")
        else:
            flash("Gagal mengirim pesan.", "error")

    return redirect(url_for("admin_contact_detail", contact_id=contact_id))


@app.route("/admin/contacts/<int:contact_id>/block", methods=["POST"])
@login_required
def admin_block_contact(contact_id):
    """Block/unblock a contact"""
    contact = Contact.query.get_or_404(contact_id)
    contact.is_blocked = not contact.is_blocked
    db.session.commit()
    status = "diblokir" if contact.is_blocked else "dibuka blokirnya"
    flash(f"Kontak {contact.phone_number} telah {status}.", "success")
    return redirect(url_for("admin_contact_detail", contact_id=contact_id))


# ======================== FAQ MANAGEMENT ========================
@app.route("/admin/faq")
@login_required
def admin_faq_list():
    """List all FAQ"""
    faqs = FAQ.query.order_by(FAQ.priority.desc()).all()
    return render_template("faq_list.html", faqs=faqs)


@app.route("/admin/faq/add", methods=["GET", "POST"])
@login_required
def admin_faq_add():
    """Add new FAQ"""
    if request.method == "POST":
        faq = FAQ(
            category=request.form.get("category", "Umum"),
            question=request.form.get("question"),
            answer=request.form.get("answer"),
            keywords=request.form.get("keywords"),
            priority=int(request.form.get("priority", 0)),
            is_active=request.form.get("is_active") == "on",
        )
        db.session.add(faq)
        db.session.commit()
        flash("FAQ berhasil ditambahkan!", "success")
        return redirect(url_for("admin_faq_list"))

    return render_template("faq_form.html", faq=None)


@app.route("/admin/faq/<int:faq_id>/edit", methods=["GET", "POST"])
@login_required
def admin_faq_edit(faq_id):
    """Edit FAQ"""
    faq = FAQ.query.get_or_404(faq_id)
    if request.method == "POST":
        faq.category = request.form.get("category", "Umum")
        faq.question = request.form.get("question")
        faq.answer = request.form.get("answer")
        faq.keywords = request.form.get("keywords")
        faq.priority = int(request.form.get("priority", 0))
        faq.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash("FAQ berhasil diperbarui!", "success")
        return redirect(url_for("admin_faq_list"))

    return render_template("faq_form.html", faq=faq)


@app.route("/admin/faq/<int:faq_id>/delete", methods=["POST"])
@login_required
def admin_faq_delete(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    db.session.delete(faq)
    db.session.commit()
    flash("FAQ berhasil dihapus!", "success")
    return redirect(url_for("admin_faq_list"))


# ======================== AUTO REPLY MANAGEMENT ========================
@app.route("/admin/auto-replies")
@login_required
def admin_auto_reply_list():
    """List auto replies"""
    replies = AutoReply.query.order_by(AutoReply.priority.desc()).all()
    return render_template("auto_reply_list.html", replies=replies)


@app.route("/admin/auto-replies/add", methods=["GET", "POST"])
@login_required
def admin_auto_reply_add():
    if request.method == "POST":
        reply = AutoReply(
            name=request.form.get("name"),
            trigger_type=request.form.get("trigger_type", "keyword"),
            trigger_value=request.form.get("trigger_value"),
            response_type=request.form.get("response_type", "text"),
            response_content=request.form.get("response_content"),
            response_media_url=request.form.get("response_media_url"),
            priority=int(request.form.get("priority", 0)),
            is_active=request.form.get("is_active") == "on",
        )
        db.session.add(reply)
        db.session.commit()
        flash("Auto Reply berhasil ditambahkan!", "success")
        return redirect(url_for("admin_auto_reply_list"))

    return render_template("auto_reply_form.html", reply=None)


@app.route("/admin/auto-replies/<int:reply_id>/edit", methods=["GET", "POST"])
@login_required
def admin_auto_reply_edit(reply_id):
    reply = AutoReply.query.get_or_404(reply_id)
    if request.method == "POST":
        reply.name = request.form.get("name")
        reply.trigger_type = request.form.get("trigger_type", "keyword")
        reply.trigger_value = request.form.get("trigger_value")
        reply.response_type = request.form.get("response_type", "text")
        reply.response_content = request.form.get("response_content")
        reply.response_media_url = request.form.get("response_media_url")
        reply.priority = int(request.form.get("priority", 0))
        reply.is_active = request.form.get("is_active") == "on"
        db.session.commit()
        flash("Auto Reply berhasil diperbarui!", "success")
        return redirect(url_for("admin_auto_reply_list"))

    return render_template("auto_reply_form.html", reply=reply)


@app.route("/admin/auto-replies/<int:reply_id>/delete", methods=["POST"])
@login_required
def admin_auto_reply_delete(reply_id):
    reply = AutoReply.query.get_or_404(reply_id)
    db.session.delete(reply)
    db.session.commit()
    flash("Auto Reply berhasil dihapus!", "success")
    return redirect(url_for("admin_auto_reply_list"))


# ======================== PRODUCT MANAGEMENT ========================
@app.route("/admin/products")
@login_required
def admin_product_list():
    products = Product.query.order_by(Product.category, Product.name).all()
    return render_template("product_list.html", products=products)


@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
def admin_product_add():
    if request.method == "POST":
        product = Product(
            name=request.form.get("name"),
            description=request.form.get("description", ""),
            price=float(request.form.get("price", 0)),
            category=request.form.get("category", "Umum"),
            image_url=request.form.get("image_url"),
            stock=int(request.form.get("stock", 0)),
            is_available=request.form.get("is_available") == "on",
        )
        db.session.add(product)
        db.session.commit()
        flash("Produk berhasil ditambahkan!", "success")
        return redirect(url_for("admin_product_list"))

    return render_template("product_form.html", product=None)


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        product.name = request.form.get("name")
        product.description = request.form.get("description", "")
        product.price = float(request.form.get("price", 0))
        product.category = request.form.get("category", "Umum")
        product.image_url = request.form.get("image_url")
        product.stock = int(request.form.get("stock", 0))
        product.is_available = request.form.get("is_available") == "on"
        db.session.commit()
        flash("Produk berhasil diperbarui!", "success")
        return redirect(url_for("admin_product_list"))

    return render_template("product_form.html", product=product)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
def admin_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Produk berhasil dihapus!", "success")
    return redirect(url_for("admin_product_list"))


# ======================== ORDER MANAGEMENT ========================
@app.route("/admin/orders")
@login_required
def admin_order_list():
    status_filter = request.args.get("status", "")
    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(Order.created_at.desc()).all()
    return render_template("order_list.html", orders=orders, status_filter=status_filter)


@app.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    contact = Contact.query.get(order.contact_id)
    items = json.loads(order.items) if order.items else []
    return render_template("order_detail.html", order=order, contact=contact, items=items)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def admin_order_update_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status")
    old_status = order.status

    if new_status in ["pending", "confirmed", "shipped", "delivered", "cancelled"]:
        order.status = new_status
        db.session.commit()

        # Notify customer
        contact = Contact.query.get(order.contact_id)
        if contact:
            status_messages = {
                "confirmed": f"✅ Pesanan *{order.order_number}* telah dikonfirmasi!\nPesanan Anda sedang diproses.",
                "shipped": f"🚚 Pesanan *{order.order_number}* telah dikirim!\nPesanan Anda dalam perjalanan.",
                "delivered": f"📬 Pesanan *{order.order_number}* telah diterima!\nTerima kasih telah berbelanja.",
                "cancelled": f"❌ Pesanan *{order.order_number}* dibatalkan.\nHubungi CS untuk info lebih lanjut.",
            }
            if new_status in status_messages:
                wa_api.send_text(contact.phone_number, status_messages[new_status])

        flash(f"Status pesanan diubah dari {old_status} ke {new_status}.", "success")

    return redirect(url_for("admin_order_detail", order_id=order_id))


# ======================== BROADCAST ========================
@app.route("/admin/broadcast")
@login_required
def admin_broadcast_list():
    broadcasts = Broadcast.query.order_by(Broadcast.created_at.desc()).all()
    return render_template("broadcast_list.html", broadcasts=broadcasts)


@app.route("/admin/broadcast/send", methods=["GET", "POST"])
@login_required
def admin_broadcast_send():
    if request.method == "POST":
        name = request.form.get("name")
        message = request.form.get("message")
        target_tags = request.form.get("target_tags", "")

        # Get target contacts
        query = Contact.query.filter_by(is_blocked=False, is_subscribed=True)
        if target_tags:
            tags = [t.strip() for t in target_tags.split(",")]
            for tag in tags:
                query = query.filter(Contact.tags.contains(tag))

        contacts = query.all()

        broadcast = Broadcast(
            name=name,
            message_content=message,
            target_tags=target_tags,
            total_recipients=len(contacts),
            status="sending",
            started_at=datetime.utcnow(),
        )
        db.session.add(broadcast)
        db.session.commit()

        # Send messages
        sent = 0
        failed = 0
        for contact in contacts:
            result = wa_api.send_text(contact.phone_number, message)
            if result.get("success"):
                sent += 1
            else:
                failed += 1

        broadcast.sent_count = sent
        broadcast.failed_count = failed
        broadcast.status = "completed"
        broadcast.completed_at = datetime.utcnow()
        db.session.commit()

        flash(f"Broadcast selesai! Terkirim: {sent}, Gagal: {failed}", "success")
        return redirect(url_for("admin_broadcast_list"))

    contacts_count = Contact.query.filter_by(is_blocked=False, is_subscribed=True).count()
    return render_template("broadcast_form.html", contacts_count=contacts_count)


# ======================== REST API ========================
@app.route("/api/stats")
@login_required
def api_stats():
    """Get dashboard stats as JSON"""
    today = datetime.utcnow().date()
    return jsonify({
        "total_contacts": Contact.query.count(),
        "total_messages": Message.query.count(),
        "today_messages": Message.query.filter(
            Message.timestamp >= datetime.combine(today, datetime.min.time())
        ).count(),
        "active_sessions": ChatSession.query.filter_by(is_active=True).count(),
        "pending_orders": Order.query.filter_by(status="pending").count(),
    })


@app.route("/api/messages/<int:contact_id>")
@login_required
def api_contact_messages(contact_id):
    """Get messages for a contact"""
    messages = (
        Message.query.filter_by(contact_id=contact_id)
        .order_by(Message.timestamp.desc())
        .limit(50)
        .all()
    )
    return jsonify([m.to_dict() for m in messages])


@app.route("/api/send", methods=["POST"])
@login_required
def api_send_message():
    """Send message via API"""
    data = request.get_json()
    phone = data.get("phone_number")
    message = data.get("message")

    if not phone or not message:
        return jsonify({"error": "phone_number and message required"}), 400

    result = wa_api.send_text(phone, message)
    return jsonify(result)


# ======================== HEALTH CHECK ========================
@app.route("/health")
def health_check():
    return jsonify({"status": "ok", "bot": BOT_NAME, "timestamp": datetime.utcnow().isoformat()})


@app.route("/")
def index():
    return redirect(url_for("admin_login"))


# ======================== RUN ========================
if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
