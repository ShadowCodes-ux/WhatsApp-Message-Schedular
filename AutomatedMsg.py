import os

from twilio.rest import Client
from datetime import datetime, timedelta
import time

# Optional: load variables from a local .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

# Credentials come from environment variables (never hard-code them in Git!)
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

# Twilio sandbox WhatsApp number
WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


def send_whatsapp_message(recipient_number, message_body):
    if not account_sid or not auth_token:
        raise RuntimeError(
            "Twilio credentials missing. Set TWILIO_ACCOUNT_SID and "
            "TWILIO_AUTH_TOKEN (see .env.example)."
        )

    client = Client(account_sid, auth_token)
    try:
        message = client.messages.create(
            from_=WHATSAPP_FROM,
            body=message_body,
            to=f'whatsapp:{recipient_number}'
        )
        print(f"Message sent to {recipient_number} successfully!: {message.sid}")
    except Exception as e:
        print(f"Failed to send message to {recipient_number}: {str(e)}")
