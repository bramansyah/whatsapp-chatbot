"""
=============================================================
  Chatbot Engine - Otak dari Chatbot
  State Machine + NLP + FAQ Matching + Order Flow
  Fitur: Multi-level menu, context awareness, fuzzy matching
=============================================================
"""
import re
import json
import logging
import random
import time
from datetime import datetime
from difflib import SequenceMatcher

from models import (
    db, Contact, Message, ChatSession, FAQ, AutoReply,
    Product, Order, ScheduledMessage
)
from whatsapp_api import wa_api
from config import BOT_NAME, SESSION_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)


# ======================== STATES ========================
class States:
    """Semua state dalam chatbot state machine"""
    WELCOME = "WELCOME"
    MAIN_MENU = "MAIN_MENU"
    PRODUCT_MENU = "PRODUCT_MENU"
    PRODUCT_DETAIL = "PRODUCT_DETAIL"
    ORDER_START = "ORDER_START"
    ORDER_SELECT_PRODUCT = "ORDER_SELECT_PRODUCT"
    ORDER_QUANTITY = "ORDER_QUANTITY"
    ORDER_ADDRESS = "ORDER_ADDRESS"
    ORDER_CONFIRM = "ORDER_CONFIRM"
    ORDER_PAYMENT = "ORDER_PAYMENT"
    CHECK_ORDER = "CHECK_ORDER"
    FAQ_MENU = "FAQ_MENU"
    FAQ_SEARCH = "FAQ_SEARCH"
    FEEDBACK = "FEEDBACK"
    CONTACT_CS = "CONTACT_CS"
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"
    WAITING_INPUT = "WAITING_INPUT"


class ChatbotEngine:
    """Engine utama chatbot dengan state machine"""

    def __init__(self):
        self.greetings = [
            "Halo! 👋", "Hai! 😊", "Selamat datang! 🎉",
            "Hello! 👋", "Hai, apa kabar? 😊"
        ]

    def process_message(self, phone_number: str, message: str, message_type: str = "text",
                        message_id: str = None, sender_name: str = "Unknown") -> list:
        """
        Proses pesan masuk dan return list of responses
        Returns: list of dicts [{type, content, ...}]
        """
        start_time = time.time()
        responses = []

        try:
            # 1. Get or create contact
            contact = self._get_or_create_contact(phone_number, sender_name)

            if contact.is_blocked:
                logger.info(f"Blocked contact tried to message: {phone_number}")
                return []

            # 2. Log incoming message
            self._log_message(contact.id, message, "inbound", message_type, message_id)

            # 3. Get or create session
            session = self._get_or_create_session(contact.id)

            # 4. Check for human takeover
            if session.is_human_takeover:
                return []  # Don't auto-respond during human takeover

            # 5. Normalize message
            normalized = self._normalize_message(message)

            # 6. Check global commands first
            global_response = self._check_global_commands(normalized, session, contact)
            if global_response:
                responses = global_response
            else:
                # 7. Check auto-reply rules
                auto_response = self._check_auto_replies(normalized)
                if auto_response and session.current_state == States.MAIN_MENU:
                    responses = auto_response
                else:
                    # 8. Process based on current state
                    responses = self._process_state(normalized, message, session, contact)

            # 9. Send responses
            response_time = int((time.time() - start_time) * 1000)
            for resp in responses:
                self._send_response(phone_number, resp)
                self._log_message(
                    contact.id,
                    resp.get("content", ""),
                    "outbound",
                    resp.get("type", "text"),
                    is_bot=True,
                    response_time=response_time,
                    matched_keyword=resp.get("matched_keyword"),
                )

            # 10. Mark as read
            if message_id:
                wa_api.mark_as_read(message_id)

            # 11. Update contact stats
            contact.total_messages += 1
            contact.last_contact = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            responses = [{"type": "text", "content": "Maaf, terjadi kesalahan. Silakan coba lagi nanti. 🙏"}]
            try:
                self._send_response(phone_number, responses[0])
            except Exception:
                pass

        return responses

    # ==================== STATE MACHINE ====================

    def _process_state(self, normalized: str, original: str, session: ChatSession, contact: Contact) -> list:
        """Route ke handler berdasarkan state saat ini"""
        state = session.current_state

        handlers = {
            States.WELCOME: self._handle_welcome,
            States.MAIN_MENU: self._handle_main_menu,
            States.PRODUCT_MENU: self._handle_product_menu,
            States.PRODUCT_DETAIL: self._handle_product_detail,
            States.ORDER_START: self._handle_order_start,
            States.ORDER_SELECT_PRODUCT: self._handle_order_select,
            States.ORDER_QUANTITY: self._handle_order_quantity,
            States.ORDER_ADDRESS: self._handle_order_address,
            States.ORDER_CONFIRM: self._handle_order_confirm,
            States.ORDER_PAYMENT: self._handle_order_payment,
            States.CHECK_ORDER: self._handle_check_order,
            States.FAQ_MENU: self._handle_faq_menu,
            States.FAQ_SEARCH: self._handle_faq_search,
            States.FEEDBACK: self._handle_feedback,
            States.CONTACT_CS: self._handle_contact_cs,
        }

        handler = handlers.get(state, self._handle_main_menu)
        return handler(normalized, original, session, contact)

    def _handle_welcome(self, normalized, original, session, contact):
        """Welcome state - tampilkan greeting dan main menu"""
        greeting = random.choice(self.greetings)
        name = contact.name if contact.name != "Unknown" else ""
        name_greeting = f" {name}" if name else ""

        self._set_state(session, States.MAIN_MENU)

        return [
            {"type": "text", "content": f"{greeting}{name_greeting}\nSelamat datang di *{BOT_NAME}*! 🤖"},
            self._get_main_menu_message(),
        ]

    def _handle_main_menu(self, normalized, original, session, contact):
        """Main menu handler"""
        # Check for number selections
        if normalized in ["1", "satu", "produk", "info produk", "katalog"]:
            self._set_state(session, States.PRODUCT_MENU)
            return self._get_product_menu()

        elif normalized in ["2", "dua", "pesan", "order", "pemesanan", "beli"]:
            self._set_state(session, States.ORDER_START)
            return self._get_order_start()

        elif normalized in ["3", "tiga", "cek", "status", "cek pesanan", "status pesanan", "tracking"]:
            self._set_state(session, States.CHECK_ORDER)
            return [{"type": "text", "content": "📦 *Cek Status Pesanan*\n\nSilakan masukkan nomor pesanan Anda:\n(Contoh: ORD-20260325-001)"}]

        elif normalized in ["4", "empat", "faq", "bantuan", "help", "tanya"]:
            self._set_state(session, States.FAQ_MENU)
            return self._get_faq_menu()

        elif normalized in ["5", "lima", "cs", "customer service", "hubungi cs", "agent", "manusia"]:
            self._set_state(session, States.CONTACT_CS)
            return self._handle_contact_cs(normalized, original, session, contact)

        # Try FAQ keyword matching
        faq_response = self._search_faq(normalized)
        if faq_response:
            return faq_response

        # Unknown input
        return [
            {"type": "text", "content": f"Maaf, saya tidak mengerti pesan Anda. 🤔\n\nSilakan pilih menu di bawah ini:"},
            self._get_main_menu_message(),
        ]

    def _handle_product_menu(self, normalized, original, session, contact):
        """Product listing and categories"""
        if normalized in ["0", "kembali", "back", "menu"]:
            self._set_state(session, States.MAIN_MENU)
            return [self._get_main_menu_message()]

        # Check if it's a category selection or product number
        products = Product.query.filter_by(is_available=True).all()
        categories = list(set(p.category for p in products))

        # Try to match category
        for i, cat in enumerate(categories, 1):
            if normalized == str(i) or normalized.lower() == cat.lower():
                cat_products = [p for p in products if p.category == cat]
                product_list = f"📦 *Produk Kategori: {cat}*\n\n"
                for j, p in enumerate(cat_products, 1):
                    stock_emoji = "✅" if p.stock > 0 else "❌"
                    product_list += f"{j}. *{p.name}*\n   💰 Rp {p.price:,.0f}\n   {stock_emoji} Stok: {p.stock}\n\n"
                product_list += "\nKetik nomor produk untuk detail, atau *0* untuk kembali."

                self._set_state(session, States.PRODUCT_DETAIL)
                context = {"category": cat, "products": [p.id for p in cat_products]}
                session.context_data = json.dumps(context)
                db.session.commit()

                return [{"type": "text", "content": product_list}]

        # If no categories, show all
        if not categories:
            return [{"type": "text", "content": "Maaf, belum ada produk tersedia. 😔\n\nKetik *0* untuk kembali."}]

        return self._get_product_menu()

    def _handle_product_detail(self, normalized, original, session, contact):
        """Show product detail"""
        if normalized in ["0", "kembali", "back"]:
            self._set_state(session, States.PRODUCT_MENU)
            return self._get_product_menu()

        if normalized in ["pesan", "beli", "order"]:
            self._set_state(session, States.ORDER_START)
            return self._get_order_start()

        try:
            context = json.loads(session.context_data or "{}")
            product_ids = context.get("products", [])
            idx = int(normalized) - 1

            if 0 <= idx < len(product_ids):
                product = Product.query.get(product_ids[idx])
                if product:
                    detail = (
                        f"📦 *{product.name}*\n\n"
                        f"📝 {product.description}\n\n"
                        f"💰 Harga: Rp {product.price:,.0f}\n"
                        f"📊 Stok: {product.stock}\n"
                        f"📁 Kategori: {product.category}\n\n"
                    )
                    if product.stock > 0:
                        detail += "Ketik *PESAN* untuk memesan produk ini.\n"

                    detail += "Ketik *0* untuk kembali."

                    context["selected_product"] = product.id
                    session.context_data = json.dumps(context)
                    db.session.commit()

                    resp = [{"type": "text", "content": detail}]
                    if product.image_url:
                        resp.insert(0, {"type": "image", "url": product.image_url, "caption": product.name})
                    return resp
        except (ValueError, IndexError):
            pass

        return [{"type": "text", "content": "Pilihan tidak valid. Ketik nomor produk atau *0* untuk kembali."}]

    def _handle_order_start(self, normalized, original, session, contact):
        """Start order flow"""
        if normalized in ["0", "kembali", "back", "batal", "cancel"]:
            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": "Pemesanan dibatalkan. ❌"}, self._get_main_menu_message()]

        products = Product.query.filter_by(is_available=True).filter(Product.stock > 0).all()
        if not products:
            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": "Maaf, tidak ada produk tersedia saat ini. 😔"}, self._get_main_menu_message()]

        product_list = "🛒 *Pilih Produk untuk Dipesan:*\n\n"
        for i, p in enumerate(products, 1):
            product_list += f"{i}. {p.name} - Rp {p.price:,.0f} (stok: {p.stock})\n"
        product_list += "\nKetik nomor produk, atau *0* untuk batal."

        self._set_state(session, States.ORDER_SELECT_PRODUCT)
        context = {"order_products": [p.id for p in products]}
        session.context_data = json.dumps(context)
        db.session.commit()

        return [{"type": "text", "content": product_list}]

    def _handle_order_select(self, normalized, original, session, contact):
        """Select product for order"""
        if normalized in ["0", "batal", "cancel"]:
            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": "Pemesanan dibatalkan. ❌"}, self._get_main_menu_message()]

        try:
            context = json.loads(session.context_data or "{}")
            product_ids = context.get("order_products", [])
            idx = int(normalized) - 1

            if 0 <= idx < len(product_ids):
                product = Product.query.get(product_ids[idx])
                if product and product.stock > 0:
                    context["selected_product"] = product.id
                    context["product_name"] = product.name
                    context["product_price"] = product.price
                    session.context_data = json.dumps(context)
                    self._set_state(session, States.ORDER_QUANTITY)
                    db.session.commit()

                    return [{"type": "text", "content": (
                        f"✅ Produk dipilih: *{product.name}*\n"
                        f"💰 Harga: Rp {product.price:,.0f}/pcs\n\n"
                        f"Masukkan jumlah yang ingin dipesan (max: {product.stock}):"
                    )}]
        except (ValueError, IndexError):
            pass

        return [{"type": "text", "content": "Pilihan tidak valid. Masukkan nomor produk atau *0* untuk batal."}]

    def _handle_order_quantity(self, normalized, original, session, contact):
        """Set order quantity"""
        if normalized in ["0", "batal", "cancel"]:
            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": "Pemesanan dibatalkan. ❌"}, self._get_main_menu_message()]

        try:
            qty = int(normalized)
            context = json.loads(session.context_data or "{}")
            product = Product.query.get(context.get("selected_product"))

            if product and 1 <= qty <= product.stock:
                context["quantity"] = qty
                context["subtotal"] = product.price * qty
                session.context_data = json.dumps(context)
                self._set_state(session, States.ORDER_ADDRESS)
                db.session.commit()

                return [{"type": "text", "content": (
                    f"📦 *{product.name}* x {qty}\n"
                    f"💰 Subtotal: Rp {product.price * qty:,.0f}\n\n"
                    f"📍 Masukkan alamat pengiriman lengkap:"
                )}]
            else:
                return [{"type": "text", "content": f"Jumlah tidak valid. Masukkan angka 1 - {product.stock if product else 99}."}]
        except ValueError:
            return [{"type": "text", "content": "Masukkan angka yang valid, atau *0* untuk batal."}]

    def _handle_order_address(self, normalized, original, session, contact):
        """Set shipping address"""
        if normalized in ["0", "batal", "cancel"]:
            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": "Pemesanan dibatalkan. ❌"}, self._get_main_menu_message()]

        if len(original.strip()) < 10:
            return [{"type": "text", "content": "Alamat terlalu pendek. Masukkan alamat lengkap Anda."}]

        context = json.loads(session.context_data or "{}")
        context["address"] = original.strip()
        session.context_data = json.dumps(context)
        self._set_state(session, States.ORDER_CONFIRM)
        db.session.commit()

        product_name = context.get("product_name", "?")
        qty = context.get("quantity", 0)
        subtotal = context.get("subtotal", 0)

        return [{"type": "text", "content": (
            f"📋 *Konfirmasi Pesanan*\n\n"
            f"📦 Produk: {product_name}\n"
            f"🔢 Jumlah: {qty}\n"
            f"💰 Total: Rp {subtotal:,.0f}\n"
            f"📍 Alamat: {original.strip()}\n\n"
            f"Ketik *YA* untuk konfirmasi atau *BATAL* untuk membatalkan."
        )}]

    def _handle_order_confirm(self, normalized, original, session, contact):
        """Confirm order"""
        if normalized in ["ya", "yes", "ok", "oke", "konfirmasi", "setuju"]:
            context = json.loads(session.context_data or "{}")
            order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{Order.query.count() + 1:03d}"

            order = Order(
                order_number=order_number,
                contact_id=contact.id,
                items=json.dumps([{
                    "product_id": context.get("selected_product"),
                    "name": context.get("product_name"),
                    "quantity": context.get("quantity"),
                    "price": context.get("product_price"),
                }]),
                total_price=context.get("subtotal", 0),
                shipping_address=context.get("address", ""),
                status="pending",
            )
            db.session.add(order)

            # Reduce stock
            product = Product.query.get(context.get("selected_product"))
            if product:
                product.stock -= context.get("quantity", 0)

            db.session.commit()

            self._set_state(session, States.ORDER_PAYMENT)
            context["order_number"] = order_number
            session.context_data = json.dumps(context)
            db.session.commit()

            return [{"type": "text", "content": (
                f"✅ *Pesanan Berhasil Dibuat!*\n\n"
                f"📝 No. Pesanan: *{order_number}*\n"
                f"💰 Total: Rp {context.get('subtotal', 0):,.0f}\n\n"
                f"💳 *Metode Pembayaran:*\n"
                f"1. Transfer Bank BCA\n"
                f"2. Transfer Bank Mandiri\n"
                f"3. GoPay\n"
                f"4. OVO\n"
                f"5. DANA\n\n"
                f"Pilih metode pembayaran:"
            )}]

        elif normalized in ["tidak", "batal", "cancel", "no"]:
            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": "Pemesanan dibatalkan. ❌"}, self._get_main_menu_message()]

        return [{"type": "text", "content": "Ketik *YA* untuk konfirmasi atau *BATAL* untuk membatalkan."}]

    def _handle_order_payment(self, normalized, original, session, contact):
        """Handle payment method selection"""
        payment_methods = {
            "1": ("Transfer BCA", "BCA: 1234567890 a/n PT Example"),
            "2": ("Transfer Mandiri", "Mandiri: 0987654321 a/n PT Example"),
            "3": ("GoPay", "GoPay: 081234567890"),
            "4": ("OVO", "OVO: 081234567890"),
            "5": ("DANA", "DANA: 081234567890"),
        }

        if normalized in payment_methods:
            method_name, method_detail = payment_methods[normalized]
            context = json.loads(session.context_data or "{}")
            order_number = context.get("order_number", "")

            order = Order.query.filter_by(order_number=order_number).first()
            if order:
                order.payment_method = method_name
                db.session.commit()

            self._set_state(session, States.MAIN_MENU)

            return [{"type": "text", "content": (
                f"💳 *Pembayaran: {method_name}*\n\n"
                f"Silakan transfer ke:\n"
                f"*{method_detail}*\n\n"
                f"💰 Total: Rp {context.get('subtotal', 0):,.0f}\n"
                f"📝 No. Pesanan: {order_number}\n\n"
                f"⚠️ Kirim bukti transfer ke chat ini.\n"
                f"Pesanan akan diproses setelah pembayaran dikonfirmasi.\n\n"
                f"Terima kasih! 🙏"
            )}, self._get_main_menu_message()]

        return [{"type": "text", "content": "Pilih metode pembayaran (1-5):"}]

    def _handle_check_order(self, normalized, original, session, contact):
        """Check order status"""
        if normalized in ["0", "kembali", "back", "menu"]:
            self._set_state(session, States.MAIN_MENU)
            return [self._get_main_menu_message()]

        # Search by order number
        order = Order.query.filter_by(order_number=original.strip().upper()).first()

        if not order:
            # Try partial match
            order = Order.query.filter(
                Order.order_number.contains(normalized.upper())
            ).first()

        if order:
            status_emoji = {
                "pending": "⏳",
                "confirmed": "✅",
                "shipped": "🚚",
                "delivered": "📬",
                "cancelled": "❌",
            }
            emoji = status_emoji.get(order.status, "❓")

            self._set_state(session, States.MAIN_MENU)
            return [{"type": "text", "content": (
                f"📦 *Status Pesanan*\n\n"
                f"📝 No: {order.order_number}\n"
                f"{emoji} Status: *{order.status.upper()}*\n"
                f"💰 Total: Rp {order.total_price:,.0f}\n"
                f"📅 Tanggal: {order.created_at.strftime('%d/%m/%Y %H:%M')}\n"
                f"💳 Pembayaran: {order.payment_method or '-'}\n"
                f"📍 Alamat: {order.shipping_address or '-'}\n"
            )}, self._get_main_menu_message()]

        # If no order found, check user's orders
        user_orders = Order.query.filter_by(contact_id=contact.id).order_by(Order.created_at.desc()).limit(5).all()
        if user_orders:
            order_list = "📦 *Pesanan Anda:*\n\n"
            for o in user_orders:
                emoji = {"pending": "⏳", "confirmed": "✅", "shipped": "🚚", "delivered": "📬", "cancelled": "❌"}.get(o.status, "❓")
                order_list += f"{emoji} {o.order_number} - {o.status.upper()} - Rp {o.total_price:,.0f}\n"
            order_list += "\nKetik nomor pesanan untuk detail, atau *0* untuk kembali."
            return [{"type": "text", "content": order_list}]

        return [{"type": "text", "content": "Pesanan tidak ditemukan. 😔\nPastikan nomor pesanan sudah benar.\n\nKetik *0* untuk kembali."}]

    def _handle_faq_menu(self, normalized, original, session, contact):
        """FAQ menu"""
        if normalized in ["0", "kembali", "back", "menu"]:
            self._set_state(session, States.MAIN_MENU)
            return [self._get_main_menu_message()]

        if normalized in ["1", "cari", "search"]:
            self._set_state(session, States.FAQ_SEARCH)
            return [{"type": "text", "content": "🔍 Ketik pertanyaan atau kata kunci yang ingin dicari:"}]

        # Show FAQ by category
        faqs = FAQ.query.filter_by(is_active=True).all()
        categories = list(set(f.category for f in faqs))

        try:
            idx = int(normalized) - 2  # offset by 2 because 1 is search
            if 0 <= idx < len(categories):
                cat = categories[idx]
                cat_faqs = [f for f in faqs if f.category == cat]
                faq_text = f"❓ *FAQ - {cat}*\n\n"
                for f in cat_faqs:
                    faq_text += f"*Q: {f.question}*\n{f.answer}\n\n"
                faq_text += "Ketik *0* untuk kembali."
                return [{"type": "text", "content": faq_text}]
        except ValueError:
            pass

        # Try to search FAQ
        results = self._search_faq(normalized)
        if results:
            return results

        return self._get_faq_menu()

    def _handle_faq_search(self, normalized, original, session, contact):
        """Search FAQ"""
        if normalized in ["0", "kembali", "back", "menu"]:
            self._set_state(session, States.FAQ_MENU)
            return self._get_faq_menu()

        results = self._search_faq(normalized)
        if results:
            self._set_state(session, States.MAIN_MENU)
            return results

        return [{"type": "text", "content": (
            "Maaf, tidak ditemukan FAQ yang cocok. 😔\n\n"
            "Coba kata kunci lain, atau ketik *0* untuk kembali."
        )}]

    def _handle_feedback(self, normalized, original, session, contact):
        """Handle feedback"""
        if len(original.strip()) > 3:
            contact.notes = (contact.notes or "") + f"\n[Feedback {datetime.utcnow().strftime('%Y-%m-%d')}]: {original}"
            self._set_state(session, States.MAIN_MENU)
            db.session.commit()
            return [
                {"type": "text", "content": "Terima kasih atas feedback Anda! 🙏 Masukan Anda sangat berarti bagi kami."},
                self._get_main_menu_message(),
            ]
        return [{"type": "text", "content": "Silakan tulis feedback Anda, atau ketik *0* untuk kembali."}]

    def _handle_contact_cs(self, normalized, original, session, contact):
        """Handle contact CS / human takeover request"""
        session.is_human_takeover = True
        self._set_state(session, States.HUMAN_TAKEOVER)
        db.session.commit()

        return [{"type": "text", "content": (
            "👤 *Menghubungi Customer Service*\n\n"
            "Anda akan terhubung dengan CS kami.\n"
            "Mohon tunggu sebentar... ⏳\n\n"
            "Jam operasional CS:\n"
            "🕐 Senin - Jumat: 08:00 - 17:00 WIB\n"
            "🕐 Sabtu: 08:00 - 12:00 WIB\n\n"
            "Ketik *BOT* untuk kembali ke mode bot."
        )}]

    # ==================== HELPER METHODS ====================

    def _get_or_create_contact(self, phone_number: str, name: str = "Unknown") -> Contact:
        """Get existing contact or create new one"""
        contact = Contact.query.filter_by(phone_number=phone_number).first()
        if not contact:
            contact = Contact(phone_number=phone_number, name=name)
            db.session.add(contact)
            db.session.commit()
        elif name != "Unknown" and contact.name == "Unknown":
            contact.name = name
            db.session.commit()
        return contact

    def _get_or_create_session(self, contact_id: int) -> ChatSession:
        """Get active session or create new one"""
        session = ChatSession.query.filter_by(
            contact_id=contact_id, is_active=True
        ).first()

        if session:
            if session.is_expired(SESSION_TIMEOUT_MINUTES):
                session.is_active = False
                session.ended_at = datetime.utcnow()
                db.session.commit()
                session = None

        if not session:
            session = ChatSession(
                contact_id=contact_id,
                current_state=States.WELCOME,
            )
            db.session.add(session)
            db.session.commit()

        session.last_activity = datetime.utcnow()
        db.session.commit()
        return session

    def _set_state(self, session: ChatSession, new_state: str):
        """Update session state"""
        session.previous_state = session.current_state
        session.current_state = new_state
        db.session.commit()

    def _normalize_message(self, message: str) -> str:
        """Normalize message for matching"""
        if not message:
            return ""
        text = message.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        return text

    def _check_global_commands(self, normalized: str, session: ChatSession, contact: Contact) -> list:
        """Check for global commands that work from any state"""
        if normalized in ["menu", "home", "start", "mulai"]:
            self._set_state(session, States.MAIN_MENU)
            return [self._get_main_menu_message()]

        if normalized == "bot":
            session.is_human_takeover = False
            self._set_state(session, States.MAIN_MENU)
            db.session.commit()
            return [
                {"type": "text", "content": "🤖 Mode bot aktif kembali!"},
                self._get_main_menu_message(),
            ]

        if normalized in ["feedback", "saran", "kritik"]:
            self._set_state(session, States.FEEDBACK)
            return [{"type": "text", "content": "📝 *Feedback*\n\nSilakan tulis saran, kritik, atau masukan Anda:"}]

        if normalized in ["stop", "berhenti", "unsubscribe"]:
            contact.is_subscribed = False
            db.session.commit()
            return [{"type": "text", "content": "Anda telah berhenti berlangganan. Ketik *START* untuk berlangganan kembali."}]

        return None

    def _check_auto_replies(self, normalized: str) -> list:
        """Check auto reply rules"""
        auto_replies = AutoReply.query.filter_by(is_active=True).order_by(AutoReply.priority.desc()).all()

        for rule in auto_replies:
            matched = False

            if rule.trigger_type == "keyword":
                keywords = [k.strip().lower() for k in rule.trigger_value.split(",")]
                for keyword in keywords:
                    if keyword in normalized:
                        matched = True
                        break

            elif rule.trigger_type == "exact":
                if normalized == rule.trigger_value.lower():
                    matched = True

            elif rule.trigger_type == "contains":
                if rule.trigger_value.lower() in normalized:
                    matched = True

            elif rule.trigger_type == "regex":
                try:
                    if re.search(rule.trigger_value, normalized, re.IGNORECASE):
                        matched = True
                except re.error:
                    pass

            if matched:
                # Check schedule
                if rule.schedule_start and rule.schedule_end:
                    now = datetime.utcnow().time()
                    if not (rule.schedule_start <= now <= rule.schedule_end):
                        continue

                rule.hit_count += 1
                db.session.commit()

                content = rule.response_content.replace("{bot_name}", BOT_NAME)
                response = {"type": rule.response_type, "content": content, "matched_keyword": rule.name}

                if rule.response_media_url:
                    response["url"] = rule.response_media_url

                if rule.response_buttons:
                    try:
                        response["buttons"] = json.loads(rule.response_buttons)
                    except json.JSONDecodeError:
                        pass

                return [response]

        return None

    def _search_faq(self, query: str) -> list:
        """Search FAQ using keyword matching with fuzzy search"""
        faqs = FAQ.query.filter_by(is_active=True).order_by(FAQ.priority.desc()).all()
        scored_faqs = []

        query_words = set(query.lower().split())

        for faq in faqs:
            keywords = [k.strip().lower() for k in faq.keywords.split(",")]
            score = 0

            # Exact keyword match
            for keyword in keywords:
                if keyword in query:
                    score += 10

            # Word-level matching
            for word in query_words:
                for keyword in keywords:
                    # Fuzzy match
                    ratio = SequenceMatcher(None, word, keyword).ratio()
                    if ratio > 0.7:
                        score += ratio * 5

            # Question similarity
            q_ratio = SequenceMatcher(None, query, faq.question.lower()).ratio()
            score += q_ratio * 8

            if score > 3:
                scored_faqs.append((faq, score))

        scored_faqs.sort(key=lambda x: x[1], reverse=True)

        if scored_faqs:
            best_faq = scored_faqs[0][0]
            best_faq.hit_count += 1
            db.session.commit()

            result = f"❓ *{best_faq.question}*\n\n{best_faq.answer}"

            if len(scored_faqs) > 1:
                result += "\n\n📌 *FAQ Terkait:*\n"
                for faq, score in scored_faqs[1:3]:
                    result += f"• {faq.question}\n"

            result += "\n\nKetik *MENU* untuk kembali ke menu utama."
            return [{"type": "text", "content": result}]

        return None

    def _log_message(self, contact_id, content, direction, msg_type="text",
                     msg_id=None, is_bot=False, response_time=None, matched_keyword=None):
        """Log message to database"""
        try:
            msg = Message(
                contact_id=contact_id,
                wa_message_id=msg_id,
                direction=direction,
                message_type=msg_type,
                content=content[:5000] if content else "",
                is_bot_response=is_bot,
                response_time_ms=response_time,
                matched_keyword=matched_keyword,
            )
            db.session.add(msg)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error logging message: {e}")
            db.session.rollback()

    def _send_response(self, phone_number: str, response: dict):
        """Send response via WhatsApp API"""
        resp_type = response.get("type", "text")

        try:
            if resp_type == "text":
                wa_api.send_text(phone_number, response["content"])

            elif resp_type == "image":
                wa_api.send_image(phone_number, response.get("url", ""), response.get("caption", ""))

            elif resp_type == "document":
                wa_api.send_document(phone_number, response.get("url", ""), response.get("filename", "file"))

            elif resp_type == "button":
                buttons = response.get("buttons", [])
                wa_api.send_interactive_buttons(phone_number, response["content"], buttons)

            elif resp_type == "list":
                sections = response.get("sections", [])
                wa_api.send_interactive_list(
                    phone_number, response["content"],
                    response.get("button_text", "Pilih"),
                    sections
                )

            elif resp_type == "location":
                wa_api.send_location(
                    phone_number,
                    response.get("latitude", 0),
                    response.get("longitude", 0),
                    response.get("name", ""),
                    response.get("address", ""),
                )
        except Exception as e:
            logger.error(f"Error sending response: {e}")

    # ==================== MENU BUILDERS ====================

    def _get_main_menu_message(self) -> dict:
        """Build main menu message"""
        return {
            "type": "text",
            "content": (
                f"📋 *Menu Utama - {BOT_NAME}*\n\n"
                "1️⃣ *Info Produk* - Lihat katalog produk\n"
                "2️⃣ *Pemesanan* - Buat pesanan baru\n"
                "3️⃣ *Cek Pesanan* - Status pesanan Anda\n"
                "4️⃣ *FAQ / Bantuan* - Pertanyaan umum\n"
                "5️⃣ *Hubungi CS* - Chat dengan CS\n\n"
                "📝 Ketik angka atau kata kunci untuk memilih."
            ),
        }

    def _get_product_menu(self) -> list:
        """Build product category menu"""
        products = Product.query.filter_by(is_available=True).all()
        categories = list(set(p.category for p in products))

        if not categories:
            return [{"type": "text", "content": "Belum ada produk tersedia. 😔\nKetik *0* untuk kembali."}]

        menu = "📦 *Katalog Produk*\n\nPilih kategori:\n\n"
        for i, cat in enumerate(categories, 1):
            count = len([p for p in products if p.category == cat])
            menu += f"{i}. *{cat}* ({count} produk)\n"
        menu += "\nKetik nomor kategori, atau *0* untuk kembali."

        return [{"type": "text", "content": menu}]

    def _get_faq_menu(self) -> list:
        """Build FAQ menu"""
        faqs = FAQ.query.filter_by(is_active=True).all()
        categories = list(set(f.category for f in faqs))

        menu = "❓ *FAQ / Bantuan*\n\n"
        menu += "1. 🔍 *Cari FAQ*\n"
        for i, cat in enumerate(categories, 2):
            count = len([f for f in faqs if f.category == cat])
            menu += f"{i}. 📁 *{cat}* ({count} pertanyaan)\n"
        menu += "\nKetik nomor untuk memilih, atau *0* untuk kembali."

        return [{"type": "text", "content": menu}]

    def _get_order_start(self) -> list:
        """Build order start message"""
        return [{"type": "text", "content": (
            "🛒 *Pemesanan Baru*\n\n"
            "Saya akan membantu Anda membuat pesanan.\n"
            "Ketik apa saja untuk melanjutkan, atau *0* untuk batal."
        )}]


# Singleton instance
chatbot = ChatbotEngine()
