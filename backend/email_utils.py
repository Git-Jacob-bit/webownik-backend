import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_reset_email(to_email: str, reset_token: str):
    reset_url = f"{os.getenv('RESET_LINK_BASE_URL')}?token={reset_token}"

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {os.getenv('RESEND_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "from": os.getenv("EMAIL_FROM"),
            "to": [to_email],
            "subject": "🔐 Resetowanie hasła – Webownik",
            "html": f"""
                <p>Cześć!</p>
                <p>Kliknij w link, aby ustawić nowe hasło:</p>
                <p><a href="{reset_url}">{reset_url}</a></p>
                <p>Jeśli to nie Ty, zignoruj tę wiadomość.</p>
            """,
        },
    )

    if response.status_code != 200:
        raise Exception(f"Błąd wysyłania e-maila: {response.text}")
