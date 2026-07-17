import smtplib
from email.message import EmailMessage
import os

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
    
    if not host or not user or not password:
        print("Error: SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD must be set in .env")
        return

    msg = EmailMessage()
    msg.set_content("This is a test email from True Grit API to confirm SMTP settings are working.")
    msg['Subject'] = "SMTP Test - True Grit API"
    msg['From'] = email_from
    msg['To'] = email_to

    try:
        print(f"Connecting to {host}:{port}...")
        server = smtplib.SMTP(host, port)
        # server.set_debuglevel(1) # Uncomment for detailed SMTP logs
        
        if use_tls:
            print("Starting TLS...")
            server.starttls()
            
        print("Logging in...")
        server.login(user, password)
        
        print("Sending email...")
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent successfully to {email_to}!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    main()
