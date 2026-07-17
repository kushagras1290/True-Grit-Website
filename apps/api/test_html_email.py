import smtplib
from email.message import EmailMessage
import os
import sys

# Ensure the app code is in the python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from truegrit_api.services.email_templates import render_password_reset, render_order_confirmation, render_farm_order_notification

def load_env(filepath):
    env = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    env[parts[0]] = parts[1]
    return env

def main():
    env = load_env('.env')
    
    host = env.get('SMTP_HOST')
    port = int(env.get('SMTP_PORT', 587))
    user = env.get('SMTP_USERNAME')
    password = env.get('SMTP_PASSWORD')
    use_tls = env.get('SMTP_USE_TLS', 'true').lower() == 'true'
    email_from = env.get('EMAIL_FROM')
    email_to = "sinku9403@gmail.com"
    admin_url = env.get('PUBLIC_ADMIN_URL', 'http://localhost:5174')
    
    if not host or not user or not password:
        print("Error: SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD must be set in .env")
        return

    try:
        print(f"Connecting to {host}:{port}...")
        server = smtplib.SMTP(host, port)
        if use_tls:
            server.starttls()
        server.login(user, password)
        
        # Test 1: Password Reset
        msg1 = EmailMessage()
        msg1['Subject'] = "UI Test: Password Reset"
        msg1['From'] = email_from
        msg1['To'] = email_to
        msg1.set_content("Plain text fallback: Reset your password...")
        msg1.add_alternative(render_password_reset("http://localhost:5173/reset-password?token=test", 30), subtype="html")
        server.send_message(msg1)
        print("Sent password reset test.")
        
        # Test 2: Order Confirmation
        msg2 = EmailMessage()
        msg2['Subject'] = "UI Test: Order Confirmation"
        msg2['From'] = email_from
        msg2['To'] = email_to
        msg2.set_content("Plain text fallback: Order confirmed...")
        msg2.add_alternative(render_order_confirmation("John Doe", "ORD-12345", "150.00 INR"), subtype="html")
        server.send_message(msg2)
        print("Sent order confirmation test.")

        # Test 3: Farm Order Notification
        msg3 = EmailMessage()
        msg3['Subject'] = "UI Test: Order Received (Farm Owner)"
        msg3['From'] = email_from
        msg3['To'] = email_to
        msg3.set_content("Plain text fallback: Order received for your farm...")
        msg3.add_alternative(render_farm_order_notification("Jane Smith", "Green Acres Farm", "ORD-12345", admin_url), subtype="html")
        server.send_message(msg3)
        print("Sent farm order notification test.")

        server.quit()
        print("All test HTML emails sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    main()
