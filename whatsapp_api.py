"""
=============================================================
  WhatsApp API Handler
  Menangani komunikasi dengan WhatsApp Business Cloud API
  Mendukung: text, image, document, button, list, template
=============================================================
"""
import json
import logging
import requests
import hmac
import hashlib
from config import (
    WHATSAPP_API_URL,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_APP_SECRET,
)

logger = logging.getLogger(__name__)


class WhatsAppAPI:
    """Handler untuk WhatsApp Business Cloud API"""

    def __init__(self):
        self.api_url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
        self.headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    # ==================== SEND METHODS ====================

    def send_text(self, to: str, text: str, preview_url: bool = False) -> dict:
        """Kirim pesan teks biasa"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": text},
        }
        return self._send_request(payload)

    def send_image(self, to: str, image_url: str, caption: str = "") -> dict:
        """Kirim gambar dengan caption"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": caption},
        }
        return self._send_request(payload)

    def send_document(self, to: str, doc_url: str, filename: str, caption: str = "") -> dict:
        """Kirim dokumen (PDF, dll)"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {"link": doc_url, "caption": caption, "filename": filename},
        }
        return self._send_request(payload)

    def send_location(self, to: str, latitude: float, longitude: float, name: str = "", address: str = "") -> dict:
        """Kirim lokasi"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "location",
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "name": name,
                "address": address,
            },
        }
        return self._send_request(payload)

    def send_contact(self, to: str, contacts: list) -> dict:
        """Kirim kartu kontak"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "contacts",
            "contacts": contacts,
        }
        return self._send_request(payload)

    def send_interactive_buttons(self, to: str, body_text: str, buttons: list, header: str = "", footer: str = "") -> dict:
        """
        Kirim pesan dengan tombol interaktif (max 3 buttons)
        buttons: [{"id": "btn_1", "title": "Button 1"}, ...]
        """
        interactive = {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"]}}
                    for btn in buttons[:3]
                ]
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return self._send_request(payload)

    def send_interactive_list(self, to: str, body_text: str, button_text: str, sections: list, header: str = "", footer: str = "") -> dict:
        """
        Kirim pesan list/menu interaktif
        sections: [
            {
                "title": "Section 1",
                "rows": [
                    {"id": "row_1", "title": "Row 1", "description": "Desc 1"},
                    ...
                ]
            },
            ...
        ]
        """
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {"button": button_text, "sections": sections},
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return self._send_request(payload)

    def send_template(self, to: str, template_name: str, language_code: str = "id", components: list = None) -> dict:
        """Kirim template message (untuk broadcast, notifikasi, dll)"""
        template = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template,
        }
        return self._send_request(payload)

    def send_reaction(self, to: str, message_id: str, emoji: str) -> dict:
        """Kirim reaksi emoji ke pesan"""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "reaction",
            "reaction": {"message_id": message_id, "emoji": emoji},
        }
        return self._send_request(payload)

    def mark_as_read(self, message_id: str) -> dict:
        """Tandai pesan sebagai sudah dibaca"""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return self._send_request(payload)

    # ==================== WEBHOOK PARSING ====================

    @staticmethod
    def parse_webhook(data: dict) -> list:
        """
        Parse incoming webhook data dari WhatsApp
        Returns list of parsed messages
        """
        messages = []
        try:
            if data.get("object") != "whatsapp_business_account":
                return messages

            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    # Parse contacts
                    contacts = {}
                    for contact in value.get("contacts", []):
                        wa_id = contact.get("wa_id")
                        profile = contact.get("profile", {})
                        contacts[wa_id] = profile.get("name", "Unknown")

                    # Parse messages
                    for msg in value.get("messages", []):
                        parsed = {
                            "from": msg.get("from"),
                            "name": contacts.get(msg.get("from"), "Unknown"),
                            "message_id": msg.get("id"),
                            "timestamp": msg.get("timestamp"),
                            "type": msg.get("type"),
                        }

                        msg_type = msg.get("type")
                        if msg_type == "text":
                            parsed["content"] = msg["text"]["body"]
                        elif msg_type == "image":
                            parsed["content"] = msg["image"].get("caption", "")
                            parsed["media_id"] = msg["image"]["id"]
                        elif msg_type == "document":
                            parsed["content"] = msg["document"].get("caption", "")
                            parsed["media_id"] = msg["document"]["id"]
                            parsed["filename"] = msg["document"].get("filename", "")
                        elif msg_type == "audio":
                            parsed["media_id"] = msg["audio"]["id"]
                            parsed["content"] = "[Audio Message]"
                        elif msg_type == "video":
                            parsed["content"] = msg["video"].get("caption", "")
                            parsed["media_id"] = msg["video"]["id"]
                        elif msg_type == "location":
                            loc = msg["location"]
                            parsed["content"] = f"📍 {loc.get('name', 'Location')}"
                            parsed["latitude"] = loc.get("latitude")
                            parsed["longitude"] = loc.get("longitude")
                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            int_type = interactive.get("type")
                            if int_type == "button_reply":
                                parsed["content"] = interactive["button_reply"]["title"]
                                parsed["button_id"] = interactive["button_reply"]["id"]
                            elif int_type == "list_reply":
                                parsed["content"] = interactive["list_reply"]["title"]
                                parsed["list_id"] = interactive["list_reply"]["id"]
                        elif msg_type == "sticker":
                            parsed["content"] = "[Sticker]"
                            parsed["media_id"] = msg["sticker"]["id"]
                        elif msg_type == "contacts":
                            parsed["content"] = "[Contact Card]"
                            parsed["shared_contacts"] = msg["contacts"]
                        else:
                            parsed["content"] = f"[{msg_type}]"

                        messages.append(parsed)

                    # Parse status updates
                    for status in value.get("statuses", []):
                        messages.append({
                            "type": "status_update",
                            "message_id": status.get("id"),
                            "status": status.get("status"),
                            "timestamp": status.get("timestamp"),
                            "recipient_id": status.get("recipient_id"),
                        })

        except Exception as e:
            logger.error(f"Error parsing webhook: {e}")

        return messages

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """Verifikasi signature webhook dari Meta"""
        if not WHATSAPP_APP_SECRET:
            return True
        expected = hmac.new(
            WHATSAPP_APP_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    # ==================== INTERNAL ====================

    def _send_request(self, payload: dict) -> dict:
        """Send request to WhatsApp API"""
        try:
            response = requests.post(
                self.api_url, headers=self.headers, json=payload, timeout=30
            )
            result = response.json()

            if response.status_code == 200:
                logger.info(f"Message sent successfully: {result}")
            else:
                logger.error(f"Failed to send message: {response.status_code} - {result}")

            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "data": result,
            }
        except requests.exceptions.Timeout:
            logger.error("WhatsApp API request timeout")
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp API request error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
wa_api = WhatsAppAPI()
