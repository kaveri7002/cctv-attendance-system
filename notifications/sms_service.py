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

    if provider == "demo":
        logger.info("Demo SMS (not sent): %s -> %s", phone_number, message)
        return {
            "success": False,
            "provider": "demo",
            "sent": False,
            "message": message,
            "detail": "SMS_PROVIDER is set to demo; no text message was sent.",
        }

    if provider != "twilio":
        raise ValueError(f"Unsupported SMS_PROVIDER: {provider}")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not all((account_sid, auth_token, from_number)):
        raise ValueError(
            "Twilio is selected but TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "and TWILIO_FROM_NUMBER must all be configured."
        )
    if not phone_number:
        raise ValueError("The student does not have a registered phone number.")

    try:
        from twilio.rest import Client
    except ImportError as exc:
        logger.exception("Twilio SDK is not installed.")
        raise RuntimeError("Twilio SDK is unavailable. Install the project requirements.") from exc

    try:
        client = Client(account_sid, auth_token)
        result = client.messages.create(body=message, from_=from_number, to=phone_number)
    except Exception as exc:
        logger.exception("Twilio SMS delivery failed for student %s.", student_id)
        raise RuntimeError(f"SMS delivery failed: {exc}") from exc

    logger.info("SMS sent successfully with Twilio: %s", result.sid)
    return {
        "success": True,
        "provider": "twilio",
        "sent": True,
        "message": message,
        "sid": result.sid,
    }
