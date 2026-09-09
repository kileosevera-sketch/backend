# Post-Sales AI Analytics Platform — Sprint 1

Sprint 1 deliverable: the foundation of the system — a real PostgreSQL
database, a simulated organization API (stands in for the real
organization's system until we get access), and a basic authentication +
role-based access system.

This has been built and tested end-to-end (login, wrong-password
rejection, role-based 403s, first-login password change, and the mock
data endpoints all verified working).

## Project structure

```
postsales-platform/
├── backend/                   # Main system backend (FastAPI + psycopg)
│   ├── app/
│   │   ├── core/
│   │   │   ├── security.py    # password hashing, JWT create/verify
│   │   │   └── deps.py        # get_current_user, require_role()
│   │   ├── db/
│   │   │   └── database.py    # psycopg connection helper
│   │   ├── ingestion/
│   │   │   ├── client.py      # HTTP calls to the organization system
│   │   │   └── pipeline.py    # Extract → validate → transform → load → log
│   │   ├── models/            # (reserved for Sprint 2+)
│   │   ├── schemas/
│   │   │   ├── auth.py        # Login/Token/ChangePassword schemas
│   │   │   └── user.py        # UserCreate/UserOut schemas
│   │   ├── routers/
│   │   │   ├── auth.py        # POST /auth/login
│   │   │   └── users.py       # POST /users, GET /users/me, change-password
│   │   └── main.py            # FastAPI app entrypoint
│   ├── schema.sql             # All Sprint 1 database tables
│   ├── seed.py                # Creates the first admin account
│   ├── ingest.py               # CLI: manually trigger an ingestion run
│   ├── requirements.txt
│   └── .env.example
│
└── mock_org_api/               # Simulated "organization" system
    ├── main.py                 # /org/complaints, /org/warranty-claims, etc.
    ├── data_generator.py        # Faker-based realistic sample data
    └── requirements.txt
```

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ installed and running locally

## Setup

### 1. Create the database

```bash
psql -U postgres -c "CREATE DATABASE postsales;"
```

### 2. Set up the backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env if your DB credentials differ from the defaults
```

Load the environment variables and apply the schema:

```bash
export $(cat .env | xargs)      # on Windows, set these manually or use python-dotenv
psql -h localhost -U postgres -d postsales -f schema.sql
```

### 3. Create the first admin account

```bash
PYTHONPATH=. python seed.py
```

This prints the admin email/password — you'll use these to log in the
first time, then create other users (management, engineering, qa,
customer_service) through the API.

### 4. Run the backend

```bash
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

### 5. Run the ingestion pipeline

With the backend's `.env` loaded and the mock organization API running
(step 6 below), pull data into the system database:

```bash
cd backend
PYTHONPATH=. python ingest.py --limit 50
```

This calls each of the 5 mock endpoints, validates and cleans the
records, creates/matches customers and products, loads everything into
PostgreSQL, and writes a row to `sync_logs` per source. Records already
ingested (matched by `source_record_id`) are skipped automatically — safe
to re-run any time.

### 6. Run the mock organization API (separate terminal)

```bash
cd mock_org_api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Try it: http://localhost:8001/org/complaints

## How authentication works

1. `POST /auth/login` with `email` + `password` → returns a JWT containing
   the user's `role`, plus `must_change_password` if this is their first
   login.
2. Send that token as `Authorization: Bearer <token>` on every other
   request.
3. `GET /users/me` returns the logged-in user's profile.
4. `POST /users` is **admin-only** — creates a new user and assigns a role.
5. `POST /users/me/change-password` — used to satisfy the forced
   first-login password change.

Role checking happens on the backend (`require_role(...)` dependency), not
just the frontend — so even a direct API call from the wrong role is
rejected with `403`.

## Switching from mock data to the real organization system later

`mock_org_api/` exists only so we have something to build the ingestion
pipeline against before we get real database/API access from the
organization. When that access is granted, Sprint 2's ingestion service
just points at the real base URL/credentials instead of
`http://localhost:8001` — nothing else in the architecture changes.

## What's NOT in Sprint 1 (by design — see project plan)

- NLP/ML processing — sentiment, symptoms, severity, failure prediction (Sprint 2)
- Role-based dashboard UI in Streamlit (Sprint 3)
- Incremental sync (only pulling records newer than the last run) — current
  pipeline does a full pull each time and relies on duplicate-skipping,
  which is fine at this data volume; worth revisiting once volumes grow
- Email/SMTP invites, Celery/Redis scheduling — later, if needed
