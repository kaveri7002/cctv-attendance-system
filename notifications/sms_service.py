import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def send_sms(student_name, student_id, phone_number):
    provider = os.getenv("SMS_PROVIDER", "demo").lower()
    current_time = datetime.now().strftime("%I:%M %p")
    message = (
        f"Attendance marked successfully. {student_name} ({student_id}) entered campus at "
        f"{current_time} on {datetime.now().strftime('%d-%m-%Y')}."
    )

    if provider == "demo" or not os.getenv("TWILIO_ACCOUNT_SID"):
        logger.info("Demo SMS mode: %s -> %s", phone_number, message)
        return {"success": True, "provider": "demo", "message": message}

    try:
        from twilio.rest import Client
    except Exception as exc:
        logger.warning("Twilio library missing; falling back to demo SMS mode: %s", exc)
        logger.info("Demo SMS mode: %s -> %s", phone_number, message)
        return {"success": True, "provider": "demo", "message": message}

    client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    result = client.messages.create(
        body=message,
        from_=os.getenv("TWILIO_FROM_NUMBER"),
        to=phone_number,
    )
    logger.info("SMS sent successfully with Twilio: %s", result.sid)
    return {"success": True, "provider": "twilio", "message": message, "sid": result.sid}
