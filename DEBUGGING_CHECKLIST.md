# Worker Timeout Debugging Checklist

## 🔍 Issues Found:

### 1. **Context Processors Running on EVERY Request** ⚠️

**Problem:** These run on every single page request and do database queries:

#### `accounts.context_processors.notifications`
- Runs: **Every request** (even for non-authenticated users)
- Query: `Notification.objects.filter(user=request.user, is_read=False).count()`
- Impact: Database query on every page load

#### `dormitory.views.user_context`
- Runs: **Every request** for authenticated users
- Queries:
  - Students: `Reservation.objects.filter(...).select_related('dorm')`
  - Landlords: `Reservation.objects.filter(...).count()`
- Impact: Database queries on every page load

**Solution:** Optimize or cache these queries

---

### 2. **Database Connection Issues** ⚠️

**Problem:** No connection pooling configured (we just added it, but need to verify)

**Check:**
- Is `CONN_MAX_AGE` set? (We added it)
- Are database connections being reused?
- Is there connection timeout?

---

### 3. **Email Sending Blocking** ⚠️

**Problem:** Email sending is synchronous (even though we removed threading)

**Check:**
- Is `EMAIL_TIMEOUT` set? (Yes, 10 seconds)
- Are emails timing out?
- Is SendGrid responding slowly?

---

### 4. **Heavy Queries in Views** ⚠️

**Problem:** Some views do complex queries with multiple joins

**Check:**
- Dashboard view loads ALL dorms for students
- Complex annotations and aggregations
- No pagination on some lists

---

## 🔧 Immediate Fixes to Try:

### Fix 1: Optimize Context Processors

**File:** `accounts/context_processors.py`
- Cache notification count
- Only query if user is authenticated

**File:** `dormitory/views.py` (user_context function)
- Cache reservation counts
- Use select_related/prefetch_related
- Limit queries

### Fix 2: Add Query Logging

Add to `settings.py`:
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

### Fix 3: Check Railway Logs

Look for:
- Slow queries
- Database connection errors
- Email timeout errors
- Memory issues

### Fix 4: Add Database Indexes

Check if these fields are indexed:
- `Notification.user` + `is_read`
- `Reservation.student` + `status`
- `Reservation.dorm__landlord` + `status`

---

## 📊 What to Check in Railway Logs:

1. **Before timeout:**
   - Any slow queries?
   - Database connection errors?
   - Email sending errors?

2. **During timeout:**
   - What was the last log entry?
   - Any error messages?
   - Memory usage?

3. **After timeout:**
   - Worker restart messages
   - Any stack traces?

---

## 🎯 Quick Wins:

1. **Optimize notifications context processor:**
   - Cache for 30 seconds
   - Only query if authenticated

2. **Optimize user_context:**
   - Cache reservation counts
   - Use select_related

3. **Add database indexes:**
   - Create migrations for indexes

4. **Reduce worker timeout:**
   - We already increased to 300 seconds
   - But should find root cause

---

## 🔬 Debugging Steps:

1. **Enable query logging** (see above)
2. **Check Railway metrics:**
   - CPU usage
   - Memory usage
   - Database connection count
3. **Test locally:**
   - Run with same database
   - Check if timeout happens
4. **Profile slow requests:**
   - Use Django Debug Toolbar (if DEBUG=True)
   - Or add timing logs

---

## 🚨 Most Likely Causes (in order):

1. **Context processors doing queries on every request** (HIGH PROBABILITY)
2. **Database connection timeout** (MEDIUM)
3. **Email sending blocking** (MEDIUM)
4. **Heavy queries without optimization** (LOW)
5. **Memory issues** (LOW)

---

## ✅ Next Steps:

1. Optimize context processors (highest priority)
2. Add query logging
3. Check Railway logs for specific errors
4. Test with optimized code
5. Monitor after deployment

