# Dorm Finder (Django)

Simple Django app for browsing dorms with search, filters, and a map.

## Setup

### 1) Create virtual env (optional)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Database Configuration

#### Option A: PostgreSQL (Recommended for Production)
1. **Install PostgreSQL** (if not already installed)
   - Download from: https://www.postgresql.org/download/
   - Set a password for the `postgres` user during installation

2. **Create the database**
   ```bash
   # Using psql command line
   psql -U postgres
   CREATE DATABASE dorm_finder;
   \q
   ```

3. **Configure environment variables**
   - Copy `env.example` to `.env`
   - Update `.env` with your PostgreSQL credentials:
     ```env
     DB_ENGINE=django.db.backends.postgresql
     DB_NAME=dorm_finder
     DB_USER=postgres
     DB_PASSWORD=your_password
     DB_HOST=localhost
     DB_PORT=5432
     ```

#### Option B: SQLite (Default - Works immediately)
- No setup needed! Django will use SQLite automatically if PostgreSQL is not configured.
- Database file: `db.sqlite3` (created automatically)

### 4) Run migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5) Create admin user (optional)
```bash
python manage.py createsuperuser
```

### 6) Start the server
```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000/

## Database Management

### Viewing the Database

**Using pgAdmin 4:**
- Search for "pgAdmin 4" in Start Menu
- Connect with your PostgreSQL credentials
- Browse your `dorm_finder` database

**Using Command Line:**
```bash
psql -U postgres -d dorm_finder
```

**Using Django Admin:**
- Run server: `python manage.py runserver`
- Visit: http://127.0.0.1:8000/admin/

## Environment Variables

The project uses `.env` file for configuration. **Never commit `.env` to version control!**

Copy `env.example` to `.env` and update with your settings:
```bash
cp env.example .env
```

## Requirements

- Python 3.8+
- Django 4.2.23
- PostgreSQL 12+ (optional, SQLite works by default)
- See `requirements.txt` for full list

## Notes

- Uses SQLite by default if PostgreSQL is not configured
- `.env` and `venv/` are already in `.gitignore`
- PostgreSQL packages (`psycopg2-binary`, `python-dotenv`, `dj-database-url`) are included in requirements.txt
