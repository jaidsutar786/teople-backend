# 🔐 Gmail App Password Setup - URGENT

## ⚠️ CURRENT PROBLEM:
- Old App Password: `foxv ywrh zyoo tedl` is **EXPIRED or WRONG**
- Error: `Username and Password not accepted`
- Solution: Generate **NEW** App Password

---

## 📝 Step-by-Step Instructions:

### **Step 1: Open Gmail Security Settings**

Click this link (login if needed):
```
https://myaccount.google.com/apppasswords
```

**OR manually:**
1. Go to: https://myaccount.google.com/
2. Click "Security" (left sidebar)
3. Scroll down to "How you sign in to Google"
4. Click "2-Step Verification" (enable if not enabled)
5. Scroll down and click "App passwords"

---

### **Step 2: Enable 2-Step Verification (If Not Enabled)**

If you see "2-Step Verification is off":
1. Click "Get Started"
2. Enter your phone number
3. Verify with SMS code
4. Click "Turn On"

---

### **Step 3: Generate App Password**

1. In "App passwords" page:
   - **Select app:** Choose "Mail" or "Other (Custom name)"
   - **Type name:** "Django Teople App"
   - Click "Generate"

2. You'll see a **16-digit password** like:
   ```
   abcd efgh ijkl mnop
   ```

3. **COPY THIS PASSWORD** (with or without spaces)

---

### **Step 4: Update settings.py**

Open: `c:\Users\admin\Downloads\src\manage\login_backend\settings.py`

Find **Line 234** (Email Configuration section)

**Replace this:**
```python
# 🧪 TESTING MODE: Console backend (OTP prints in terminal)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'sutarjaid970@gmail.com'
```

**With this:**
```python
# ✅ PRODUCTION MODE: Real email sending
EMAIL_BACKEND = 'accounts.email_backend.CustomEmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'sutarjaid970@gmail.com'
EMAIL_HOST_PASSWORD = 'abcdefghijklmnop'  # PASTE YOUR NEW APP PASSWORD (remove spaces)
DEFAULT_FROM_EMAIL = 'sutarjaid970@gmail.com'
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
```

**IMPORTANT:** Remove spaces from password:
- `abcd efgh ijkl mnop` → `abcdefghijklmnop`

---

### **Step 5: Restart Django Server**

```bash
# Stop server (Ctrl+C)
cd c:\Users\admin\Downloads\src\manage
python manage.py runserver
```

---

### **Step 6: Test Email**

Run test script:
```bash
cd c:\Users\admin\Downloads\src\manage
python test_email.py
```

**Expected Output:**
```
✅ SUCCESS! Email sent successfully!
   📬 Check inbox: sutarjaid970@gmail.com
```

---

## 🎯 Quick Copy-Paste Template:

After generating App Password, copy this and update in settings.py:

```python
# ✅ PRODUCTION MODE: Real email sending
EMAIL_BACKEND = 'accounts.email_backend.CustomEmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'sutarjaid970@gmail.com'
EMAIL_HOST_PASSWORD = 'PASTE_YOUR_16_DIGIT_PASSWORD_HERE'  # No spaces!
DEFAULT_FROM_EMAIL = 'sutarjaid970@gmail.com'
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 30
```

---

## ❓ Troubleshooting:

### **Can't find "App passwords" option?**
- Make sure 2-Step Verification is enabled first
- Wait 5 minutes after enabling 2-Step Verification
- Try this direct link: https://myaccount.google.com/apppasswords

### **Still getting authentication error?**
- Double-check password has no spaces
- Make sure you copied the entire 16-digit password
- Try generating a new App Password
- Check EMAIL_HOST_USER matches your Gmail address

### **"Less secure app access" message?**
- Ignore this - App Passwords are the secure way
- Don't enable "Less secure app access"

---

## 📞 Need Help?

If still not working:
1. Screenshot the error from `python test_email.py`
2. Verify App Password is exactly 16 characters (no spaces)
3. Make sure sutarjaid970@gmail.com is the correct Gmail account

---

**NEXT STEPS:**
1. ✅ Generate new App Password
2. ✅ Update settings.py (Line 234)
3. ✅ Restart server
4. ✅ Run test_email.py
5. ✅ Test OTP from frontend

---

**Last Updated:** 2025-01-20
**Status:** Waiting for new App Password
