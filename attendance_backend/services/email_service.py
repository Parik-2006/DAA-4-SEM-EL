import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()


class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
    
    def send_password_reset(self, recipient_email: str, reset_token: str):
        """Send password reset email"""
        if not self.sender_email or not self.sender_password:
            print("Warning: Email credentials not configured")
            return False
        
        reset_link = f"https://yourdomain.com/reset-password?token={reset_token}"
        
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = recipient_email
        message["Subject"] = "Password Reset Request - Attendance System"
        
        body = f"""
Hello,

You requested a password reset for your Attendance System account.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
Attendance System Team
"""
        
        message.attach(MIMEText(body, "plain"))
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False
    
    def send_verification_email(self, recipient_email: str, verification_code: str):
        """Send account verification email"""
        if not self.sender_email or not self.sender_password:
            print("Warning: Email credentials not configured")
            return False
        
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = recipient_email
        message["Subject"] = "Verify Your Email - Attendance System"
        
        body = f"""
Hello,

Welcome to the Attendance System!

Your email verification code is:
{verification_code}

Use this code to verify your email address.

Best regards,
Attendance System Team
"""
        
        message.attach(MIMEText(body, "plain"))
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False
