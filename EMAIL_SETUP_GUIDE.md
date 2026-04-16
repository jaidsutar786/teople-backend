# 📧 Email Setup Guide - Gmail SMTP Configuration

## 🚨 Current Status:
- **Email Backend:** Console (Testing Mode)
- **OTP:** Prints in terminal/console
- **Real Email:** Not configured yet

---

## ✅ Step-by-Step: Enable Real Email Sending

### **Step 1: Generate Gmail App Password**

1. Go to: https://myaccount.google.com/security
2. Enable **2-Step Verification** (if not enabled)
3. Search for **"App passwords"** in the search bar
4. Click **"App passwords"**
5. Select:
   - **App:** Mail
   - **Device:** Windows Computer (or Other)
6. Click **"Generate"**
7. Copy the **16-digit password** (e.g., `abcd efgh ijkl mnop`)
8. **Remove spaces:** `abcdefghijklmnop`

---

### **Step 2: Update settings.py**

Open: `c:\Users\admin\Downloads\src\manage\login_backend\settings.py`

**Find Line 234 (Email Configuration section)**

**Comment out Console Backend:**
```python
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

**Uncomment Production Settings:**
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'sutarjaid970@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-digit-app-password-here'  # PASTE YOUR APP PASSWORD
DEFAULT_FROM_EMAIL = 'sutarjaid970@gmail.com'
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
```

---

### **Step 3: Restart Django Server**

```bash
# Stop current server (Ctrl+C)
cd c:\Users\admin\Downloads\src\manage
python manage.py runserver
```

---

### **Step 4: Test Email**

**Option A: Test via Django Shell**
```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    'Test Email',
    'This is a test email from Django.',
    'sutarjaid970@gmail.com',
    ['sutarjaid970@gmail.com'],
    fail_silently=False,
)
```

**Expected Output:**
```
1  # Email sent successfully
```

**Option B: Test via OTP Registration**
- Go to registration page
- Enter email
- Click "Send OTP"
- Check email inbox

---

## 🔧 Troubleshooting

### **Error: SMTPAuthenticationError**
**Problem:** App password is wrong or 2-Step Verification not enabled

**Fix:**
1. Regenerate App Password
2. Make sure no spaces in password
3. Enable 2-Step Verification first

---

### **Error: SMTPServerDisconnected**
**Problem:** Gmail blocked the connection

**Fix:**
1. Go to: https://myaccount.google.com/lesssecureapps
2. Turn ON "Allow less secure apps" (if available)
3. Or use App Password (recommended)

---

### **Error: SSL Certificate Error**
**Problem:** SSL certificate verification failed

**Fix:** Use custom email backend (already created)

In `settings.py`:
```python
EMAIL_BACKEND = 'accounts.email_backend.CustomEmailBackend'
```

---

## 📝 Current Configuration (Testing Mode)

**File:** `settings.py` (Line 234)

```python
# TESTING MODE - OTP prints in console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

**How to see OTP:**
1. Run server: `python manage.py runserver`
2. Request OTP from frontend
3. Check **terminal/console** where server is running
4. OTP will be printed there

**Example Console Output:**
```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Subject: Your OTP for Account Registration - Teople Technologies
From: sutarjaid970@gmail.com
To: employee@example.com

Dear John,

Your OTP for account registration is: 737928

This OTP is valid for 10 minutes.
```

---

## 🎯 Quick Switch Between Modes

### **Testing Mode (Console):**
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### **Production Mode (Real Email):**
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'sutarjaid970@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
DEFAULT_FROM_EMAIL = 'sutarjaid970@gmail.com'
```

---

## ⚠️ Important Notes

1. **Never commit App Password to Git**
   - Use environment variables in production
   - Add `.env` file to `.gitignore`

2. **Gmail Daily Limit**
   - Free Gmail: 500 emails/day
   - Google Workspace: 2000 emails/day

3. **For Production**
   - Use professional email service (SendGrid, AWS SES, Mailgun)
   - Gmail is good for testing only

---

## 🔐 Environment Variables (Production)

Create `.env` file:
```env
EMAIL_HOST_USER=sutarjaid970@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
DEFAULT_FROM_EMAIL=sutarjaid970@gmail.com
```

Update `settings.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
```

Install python-dotenv:
```bash
pip install python-dotenv
```

---

## 📞 Support

If email still not working:
1. Check Gmail App Password is correct
2. Check 2-Step Verification is enabled
3. Try different email provider (Outlook, SendGrid)
4. Check firewall/antivirus blocking port 587

---

**Last Updated:** 2025-01-20
**Status:** Console Mode (Testing)
