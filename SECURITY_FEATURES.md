# Security Features Implemented

## 1. Session Timeout (15 minutes)

**What it does:**
- Automatically logs out users after 15 minutes of inactivity
- Session expires when browser closes
- Warning message appears 2-3 minutes before session expires

**Configuration:** (in `settings.py`)
```python
SESSION_COOKIE_AGE = 900  # 15 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Resets timeout on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Ends on browser close
```

**Middleware:** `SessionTimeoutMiddleware`
- Tracks last activity time
- Shows warning before expiration
- Prevents unauthorized access on shared computers

---

## 2. Rate Limiting

**What it does:**
- Prevents spam and abuse
- Blocks brute-force attacks
- Protects server from being overwhelmed

### Rate Limits Applied:

**Login attempts:** 5 per minute per IP
```python
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True))
```
- Prevents brute-force password attacks
- Limits: 5 login attempts per minute per IP address

**Messaging:** 30 messages per minute per user
```python
@method_decorator(ratelimit(key='user', rate='30/m', method='POST', block=True))
```
- Prevents spam messages
- Limits: 30 messages per minute per logged-in user

**Reservation creation:** 10 per hour per user
```python
@method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
```
- Prevents reservation spam
- Limits: 10 reservation attempts per hour per user

### Rate Limit Exceeded Response:
- Shows custom 429 error page
- Displays countdown timer (60 seconds)
- Explains why it happened
- Provides guidance on what to do

---

## Testing the Features

### Test Session Timeout:
1. Login to your account
2. Wait 15 minutes without any activity
3. Try to access any page → You'll be logged out
4. Or wait 12-13 minutes → You'll see a warning message

### Test Rate Limiting:

**Login Rate Limit:**
1. Try to login with wrong password 6 times quickly
2. 6th attempt → 429 error page appears

**Message Rate Limit:**
1. Send 31 messages rapidly in a reservation chat
2. 31st message → 429 error page appears

**Reservation Rate Limit:**
1. Try to create 11 reservations in one hour
2. 11th attempt → 429 error page appears

---

## Files Modified:

1. **settings.py** - Added session and rate limit configuration
2. **requirements.txt** - Added `django-ratelimit==4.1.0`
3. **accounts/views.py** - Added rate limit to LoginView
4. **accounts/middleware.py** - Created SessionTimeoutMiddleware
5. **dormitory/views.py** - Added rate limits to SendMessageView and ReservationCreateView
6. **smart_dorm_finder/views.py** - Added handler429 for rate limit errors
7. **smart_dorm_finder/urls.py** - Added handler429
8. **templates/429.html** - Created custom rate limit error page

---

## Installation Required:

Run this command to install the new package:
```bash
pip install django-ratelimit==4.1.0
```

---

## Adjusting Settings:

### To change session timeout (in settings.py):
```python
SESSION_COOKIE_AGE = 1800  # 30 minutes (in seconds)
```

### To change rate limits (in views.py):
```python
# More strict
@ratelimit(key='ip', rate='3/m')  # 3 per minute

# More lenient
@ratelimit(key='ip', rate='10/m')  # 10 per minute

# Different time periods
rate='5/s'   # per second
rate='10/m'  # per minute
rate='100/h' # per hour
rate='1000/d' # per day
```

---

## Benefits:

✅ **Security:** Prevents unauthorized access and attacks
✅ **Performance:** Protects server from being overwhelmed
✅ **User Experience:** Clear error messages and guidance
✅ **Compliance:** Industry best practice for web security
✅ **Protection:** Against spam, abuse, and brute-force attacks
