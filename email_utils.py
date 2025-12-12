import os
import requests

MAILTRAP_TOKEN = os.getenv("MAILTRAP_TOKEN")
MAILTRAP_SANDBOX_ID = os.getenv("MAILTRAP_SANDBOX_ID")

MAILTRAP_API_URL = f"https://sandbox.api.mailtrap.io/api/send/{MAILTRAP_SANDBOX_ID}"

def send_password_reset_email(to_email: str, reset_token: str):
    """
    Mailtrap Email API kullanarak reset email gönderir.
    """
    if not MAILTRAP_TOKEN:
        raise Exception("MAILTRAP_TOKEN env variable missing")

    payload = {
        "from": {
            "email": "no-reply@mindio.app",
            "name": "Mindio Support"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": "Reset Your Mindio Password",
        "text": f"Use this token to reset your password: {reset_token}",
        "category": "Password Reset"
    }

    headers = {
        "Authorization": f"Bearer {MAILTRAP_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(MAILTRAP_API_URL, json=payload, headers=headers)

    if response.status_code not in (200, 202):
        raise Exception(f"Mail sending failed: {response.text}")

    return True
