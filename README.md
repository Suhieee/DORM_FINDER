Dorm Finder (Django)

Simple Django app for browsing dorms with search, filters, and a map.

Setup
1) Create virtual env (optional)
   - Windows: python -m venv venv && venv\Scripts\activate
   - Mac/Linux: python3 -m venv venv && source venv/bin/activate

2) Install dependencies
   - pip install -r requirements.txt

3) Run migrations
   - python manage.py makemigrations
   - python manage.py migrate

4) Create admin user (optional)
   - python manage.py createsuperuser

5) Start the server
   - python manage.py runserver

Notes
- Uses SQLite by default.
- Do not commit .env or venv/ (already in .gitignore).
