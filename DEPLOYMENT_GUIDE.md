# Deployment Guide - Superuser Creation & Email Verification

This guide addresses two common issues when deploying Django applications to production:

1. **Creating superusers in production**
2. **Email verification not working in production**

## Issue 1: Creating Superuser in Production

### Problem
When you run `python manage.py createsuperuser` locally, it creates the superuser in your local database (SQLite or local PostgreSQL), not in the production database.

### Solution

We've created a custom management command that uses your production database configuration from environment variables.

#### Method 1: Interactive (Recommended for first-time setup)

1. **Connect to your production server** (via SSH, Railway CLI, Heroku CLI, etc.)

2. **Set your production database environment variables** (if not already set):
   ```bash
   # For Railway/Render/Heroku, these are usually set automatically
   # For manual setup, export them:
   export DATABASE_URL="postgresql://user:password@host:port/dbname"
   # OR set individual variables:
   export DB_ENGINE="django.db.backends.postgresql"
   export DB_NAME="your_production_db"
   export DB_USER="your_db_user"
   export DB_PASSWORD="your_db_password"
   export DB_HOST="your_db_host"
   export DB_PORT="5432"
   ```

3. **Run the management command**:
   ```bash
   python manage.py create_production_superuser
   ```

4. **Follow the prompts**:
   - Enter username
   - Enter email
   - Enter password (twice for confirmation)

#### Method 2: Non-Interactive (For CI/CD or automated deployment)

1. **Set environment variables**:
   ```bash
   export SUPERUSER_PASSWORD="your-secure-password"
   ```

2. **Run with arguments**:
   ```bash
   python manage.py create_production_superuser \
     --username admin \
     --email admin@yourdomain.com \
     --noinput \
     --password "$SUPERUSER_PASSWORD"
   ```

   Or use the environment variable for password:
   ```bash
   export SUPERUSER_PASSWORD="your-secure-password"
   python manage.py create_production_superuser \
     --username admin \
     --email admin@yourdomain.com \
     --noinput
   ```

#### Method 3: Using Django Shell (Alternative)

If the management command doesn't work, you can use Django shell:

```bash
python manage.py shell
```

Then in the shell:
```python
from accounts.models import CustomUser
user = CustomUser.objects.create_user(
    username='admin',
    email='admin@yourdomain.com',
    password='your-secure-password',
    is_staff=True,
    is_superuser=True,
    user_type='admin'
)
print(f"Superuser created: {user.username}")
exit()
```

### Verification

After creating the superuser, verify it works:
1. Log in to your production admin panel: `https://yourdomain.com/admin/`
2. Or check via Django shell:
   ```bash
   python manage.py shell
   ```
   ```python
   from accounts.models import CustomUser
   superusers = CustomUser.objects.filter(is_superuser=True)
   for user in superusers:
       print(f"{user.username} - {user.email} - Superuser: {user.is_superuser}")
   ```

---

## Issue 2: Email Verification Not Working in Production

### Problem
Email verification links are being generated with incorrect URLs (e.g., using `localhost` or wrong domain), causing verification to fail.

### Solution

We've added a `SITE_URL` setting that ensures verification links use the correct production domain.

#### Step 1: Set SITE_URL Environment Variable

**For Railway/Render/Heroku:**
1. Go to your project's environment variables settings
2. Add a new variable:
   - **Key**: `SITE_URL`
   - **Value**: `https://yourdomain.com` (your actual production domain)

**For manual deployment:**
Add to your `.env` file or export it:
```bash
export SITE_URL="https://yourdomain.com"
```

**Important:** 
- Include the protocol (`https://`)
- Don't include a trailing slash (it's added automatically)
- Use your actual production domain

#### Step 2: Configure Email Settings

Make sure your email service is properly configured:

**For SendGrid:**
```bash
export SENDGRID_API_KEY="your-sendgrid-api-key"
export DEFAULT_FROM_EMAIL="noreply@yourdomain.com"
```

**For Mailgun:**
```bash
export MAILGUN_API_KEY="your-mailgun-api-key"
export MAILGUN_DOMAIN="your-mailgun-domain"
export MAILGUN_SMTP_LOGIN="your-mailgun-smtp-login"
export DEFAULT_FROM_EMAIL="noreply@yourdomain.com"
```

**For Gmail (Development only, not recommended for production):**
```bash
export EMAIL_HOST="smtp.gmail.com"
export EMAIL_PORT="587"
export EMAIL_USE_TLS="True"
export EMAIL_HOST_USER="your-email@gmail.com"
export EMAIL_HOST_PASSWORD="your-app-password"
export DEFAULT_FROM_EMAIL="your-email@gmail.com"
```

#### Step 3: Verify Configuration

1. **Check your settings are loaded:**
   ```bash
   python manage.py shell
   ```
   ```python
   from django.conf import settings
   print(f"SITE_URL: {settings.SITE_URL}")
   print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
   print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
   print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
   ```

2. **Test email sending:**
   ```bash
   python manage.py shell
   ```
   ```python
   from django.core.mail import send_mail
   from django.conf import settings
   
   send_mail(
       'Test Email',
       'This is a test email from production.',
       settings.DEFAULT_FROM_EMAIL,
       ['your-test-email@example.com'],
       fail_silently=False,
   )
   print("Test email sent!")
   ```

#### Step 4: Check Logs

If email verification still doesn't work, check your application logs:

- **Railway**: View logs in the Railway dashboard
- **Render**: View logs in the Render dashboard
- **Heroku**: `heroku logs --tail`
- **Manual**: Check your application's log files

Look for:
- `✅ Verification email sent successfully` - Success
- `❌ Email send failed` - Email service issue
- `Email not configured` - Missing email credentials

### Troubleshooting Email Verification

1. **Verification link uses wrong domain:**
   - Ensure `SITE_URL` is set correctly
   - Restart your application after setting the variable
   - Check that `ALLOWED_HOSTS` includes your domain

2. **Email not being sent:**
   - Verify email service credentials (SendGrid/Mailgun API keys)
   - Check spam folder
   - Verify `DEFAULT_FROM_EMAIL` is set
   - Check application logs for errors

3. **Verification link expired:**
   - Links expire after 48 hours
   - Users can request a new verification email from the login page

4. **CSRF errors when clicking verification link:**
   - Ensure `CSRF_TRUSTED_ORIGINS` includes your domain
   - Format: `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`

---

## Complete Environment Variables Checklist

For production deployment, ensure these are set:

### Required
- `SECRET_KEY` - Django secret key
- `DEBUG=False` - Set to False in production
- `DJANGO_ALLOWED_HOSTS` - Your production domain(s)
- `DATABASE_URL` - Production database connection string
- `SITE_URL` - Your production domain (for email verification)

### Email Configuration (Choose one)
- **SendGrid**: `SENDGRID_API_KEY`, `DEFAULT_FROM_EMAIL`
- **Mailgun**: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_SMTP_LOGIN`, `DEFAULT_FROM_EMAIL`
- **Gmail**: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`

### Optional but Recommended
- `CSRF_TRUSTED_ORIGINS` - Your production domain(s)
- `SUPERUSER_PASSWORD` - For automated superuser creation

---

## Quick Reference Commands

### Create Superuser in Production
```bash
python manage.py create_production_superuser
```

### Check Superuser Exists
```bash
python manage.py shell
```
```python
from accounts.models import CustomUser
CustomUser.objects.filter(is_superuser=True).values('username', 'email')
```

### Test Email Configuration
```bash
python manage.py shell
```
```python
from django.core.mail import send_mail
from django.conf import settings
send_mail('Test', 'Test body', settings.DEFAULT_FROM_EMAIL, ['your@email.com'])
```

### View Current Settings
```bash
python manage.py shell
```
```python
from django.conf import settings
print(f"SITE_URL: {settings.SITE_URL}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
```

---

## Support

If you continue to experience issues:

1. Check application logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure your database is accessible from the production environment
4. Test email service credentials independently
5. Verify DNS and SSL certificates are properly configured

