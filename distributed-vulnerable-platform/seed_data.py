"""Seed data script — populates all service databases with test data.

Run after docker-compose up:
  docker-compose exec auth-service python /app/shared/../seed_data.py
  OR: python seed_data.py (with DATABASE_URLs set)

Creates:
- 2 organizations (Acme Corp, Globex Inc)
- 6 users across both orgs
- 3 projects per org, 5 tasks each
- Subscriptions, invoices, payments
- API tokens
- Coupons
"""

import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── Configuration ──────────────────────────────────────────────

POSTGRES_USER = os.getenv("POSTGRES_USER", "platform_admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "platform_secret_2024")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DB_URLS = {
    "auth": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/auth_db",
    "user": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/user_db",
    "project": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/project_db",
    "billing": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/billing_db",
    "payment": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/payment_db",
    "notification": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/notification_db",
    "reporting": f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/reporting_db",
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEFAULT_PASSWORD = "Password123!"

now = datetime.now(timezone.utc)


def get_session(db_key: str):
    engine = create_engine(DB_URLS[db_key])
    Session = sessionmaker(bind=engine)
    return Session()


def seed_auth():
    """Seed auth_db with users."""
    session = get_session("auth")

    # Create tables if they don't exist
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS auth_users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token VARCHAR(500) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            revoked BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    session.commit()

    users = [
        ("admin@acme.com", "admin"),
        ("alice@acme.com", "user"),
        ("bob@acme.com", "viewer"),
        ("admin@globex.com", "admin"),
        ("eve@globex.com", "user"),
        ("system@internal", "admin"),
    ]

    for email, role in users:
        session.execute(text("""
            INSERT INTO auth_users (email, password_hash, role, is_active)
            VALUES (:email, :password_hash, :role, TRUE)
            ON CONFLICT (email) DO NOTHING
        """), {"email": email, "password_hash": pwd_context.hash(DEFAULT_PASSWORD), "role": role})

    session.commit()
    print(f"[auth] Seeded {len(users)} users")
    session.close()


def seed_users():
    """Seed user_db with profiles, orgs, memberships, tokens."""
    session = get_session("user")

    # Create tables
    for ddl in [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, auth_user_id INTEGER UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL, full_name VARCHAR(255) DEFAULT '',
            phone VARCHAR(50) DEFAULT '', ssn_last4 VARCHAR(4) DEFAULT '',
            internal_notes TEXT DEFAULT '', password_hash VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) UNIQUE NOT NULL, owner_id INTEGER NOT NULL,
            plan_type VARCHAR(50) DEFAULT 'free', created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS org_memberships (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, org_id INTEGER NOT NULL,
            role VARCHAR(50) DEFAULT 'member', invited_by INTEGER,
            joined_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS api_tokens (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, org_id INTEGER NOT NULL,
            token_hash VARCHAR(255) NOT NULL, token_plain VARCHAR(255) NOT NULL,
            name VARCHAR(255) DEFAULT 'default', scopes VARCHAR(500) DEFAULT 'read',
            last_used TIMESTAMP, created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS invites (
            id SERIAL PRIMARY KEY, org_id INTEGER NOT NULL, email VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'member', token VARCHAR(255) UNIQUE NOT NULL,
            accepted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]:
        session.execute(text(ddl))
    session.commit()

    # Users (matching auth_users IDs)
    users_data = [
        (1, 1, "admin@acme.com", "Admin Acme", "+1-555-0101", "1234", "System administrator", pwd_context.hash(DEFAULT_PASSWORD)),
        (2, 2, "alice@acme.com", "Alice Smith", "+1-555-0102", "5678", "Regular engineer", pwd_context.hash(DEFAULT_PASSWORD)),
        (3, 3, "bob@acme.com", "Bob Jones", "+1-555-0103", "9012", "Read-only auditor", pwd_context.hash(DEFAULT_PASSWORD)),
        (4, 4, "admin@globex.com", "Admin Globex", "+1-555-0201", "3456", "Globex admin", pwd_context.hash(DEFAULT_PASSWORD)),
        (5, 5, "eve@globex.com", "Eve Hacker", "+1-555-0202", "7890", "Security tester — attacker persona", pwd_context.hash(DEFAULT_PASSWORD)),
        (6, 6, "system@internal", "System Account", "", "", "Internal service account — do not expose", pwd_context.hash(DEFAULT_PASSWORD)),
    ]
    for uid, auth_id, email, name, phone, ssn, notes, phash in users_data:
        session.execute(text("""
            INSERT INTO users (id, auth_user_id, email, full_name, phone, ssn_last4, internal_notes, password_hash)
            VALUES (:id, :auth_id, :email, :name, :phone, :ssn, :notes, :phash)
            ON CONFLICT (email) DO NOTHING
        """), {"id": uid, "auth_id": auth_id, "email": email, "name": name, "phone": phone, "ssn": ssn, "notes": notes, "phash": phash})

    # Organizations
    session.execute(text("INSERT INTO organizations (id, name, slug, owner_id, plan_type) VALUES (1, 'Acme Corp', 'acme', 1, 'pro') ON CONFLICT (slug) DO NOTHING"))
    session.execute(text("INSERT INTO organizations (id, name, slug, owner_id, plan_type) VALUES (2, 'Globex Inc', 'globex', 4, 'starter') ON CONFLICT (slug) DO NOTHING"))

    # Memberships
    memberships = [
        (1, 1, "owner"), (2, 1, "member"), (3, 1, "viewer"),  # Acme
        (4, 2, "owner"), (5, 2, "member"),  # Globex
    ]
    for user_id, org_id, role in memberships:
        session.execute(text("""
            INSERT INTO org_memberships (user_id, org_id, role)
            VALUES (:uid, :oid, :role)
        """), {"uid": user_id, "oid": org_id, "role": role})

    # API Tokens
    for org_id in [1, 2]:
        raw_token = secrets.token_urlsafe(48)
        session.execute(text("""
            INSERT INTO api_tokens (user_id, org_id, token_hash, token_plain, name, scopes)
            VALUES (:uid, :oid, :hash, :plain, :name, :scopes)
        """), {
            "uid": org_id,  # owner
            "oid": org_id,
            "hash": hashlib.sha256(raw_token.encode()).hexdigest(),
            "plain": raw_token,
            "name": f"org-{org_id}-token",
            "scopes": "read,write",
        })

    session.commit()
    print("[user] Seeded users, orgs, memberships, tokens")
    session.close()


def seed_projects():
    """Seed project_db."""
    session = get_session("project")

    for ddl in [
        """CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY, org_id INTEGER NOT NULL, name VARCHAR(255) NOT NULL,
            description TEXT DEFAULT '', status VARCHAR(50) DEFAULT 'active',
            created_by INTEGER NOT NULL, created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL, title VARCHAR(255) NOT NULL,
            description TEXT DEFAULT '', assignee_id INTEGER,
            status VARCHAR(50) DEFAULT 'todo', priority VARCHAR(50) DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY, task_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
            body TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]:
        session.execute(text(ddl))
    session.commit()

    project_id = 1
    task_id = 1
    for org_id, owner_id in [(1, 1), (2, 4)]:
        for i in range(1, 4):
            session.execute(text("""
                INSERT INTO projects (id, org_id, name, description, status, created_by)
                VALUES (:id, :org, :name, :desc, 'active', :owner)
                ON CONFLICT DO NOTHING
            """), {"id": project_id, "org": org_id, "name": f"Project {i} (Org {org_id})", "desc": f"Test project {i}", "owner": owner_id})

            for j in range(1, 6):
                assignee = owner_id + (j % 2)
                session.execute(text("""
                    INSERT INTO tasks (id, project_id, title, description, assignee_id, status, priority)
                    VALUES (:id, :pid, :title, :desc, :assignee, :status, :priority)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": task_id, "pid": project_id,
                    "title": f"Task {j} in Project {i}",
                    "desc": f"Description for task {j}",
                    "assignee": assignee,
                    "status": ["todo", "in_progress", "review", "done"][j % 4],
                    "priority": ["low", "medium", "high", "urgent"][j % 4],
                })
                task_id += 1
            project_id += 1

    session.commit()
    print("[project] Seeded 6 projects, 30 tasks")
    session.close()


def seed_billing():
    """Seed billing_db."""
    session = get_session("billing")

    for ddl in [
        """CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY, org_id INTEGER NOT NULL,
            plan VARCHAR(50) DEFAULT 'free', status VARCHAR(50) DEFAULT 'active',
            started_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY, org_id INTEGER NOT NULL, subscription_id INTEGER,
            amount FLOAT NOT NULL, tax FLOAT DEFAULT 0, discount FLOAT DEFAULT 0,
            status VARCHAR(50) DEFAULT 'pending', due_date TIMESTAMP, paid_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS coupons (
            id SERIAL PRIMARY KEY, code VARCHAR(100) UNIQUE NOT NULL,
            discount_percent INTEGER NOT NULL, max_uses INTEGER DEFAULT 100,
            current_uses INTEGER DEFAULT 0, expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )""",
        """CREATE TABLE IF NOT EXISTS applied_coupons (
            id SERIAL PRIMARY KEY, invoice_id INTEGER NOT NULL,
            coupon_id INTEGER NOT NULL, discount_amount FLOAT NOT NULL
        )""",
    ]:
        session.execute(text(ddl))
    session.commit()

    # Subscriptions
    session.execute(text("INSERT INTO subscriptions (id, org_id, plan, status, expires_at) VALUES (1, 1, 'pro', 'active', :exp) ON CONFLICT DO NOTHING"),
                    {"exp": now + timedelta(days=365)})
    session.execute(text("INSERT INTO subscriptions (id, org_id, plan, status, expires_at) VALUES (2, 2, 'starter', 'active', :exp) ON CONFLICT DO NOTHING"),
                    {"exp": now + timedelta(days=30)})

    # Invoices
    invoices = [
        (1, 1, 1, 99.99, 8.0, 0, "paid", now - timedelta(days=30), now - timedelta(days=25)),
        (2, 1, 1, 99.99, 8.0, 0, "pending", now + timedelta(days=5), None),
        (3, 2, 2, 29.99, 2.4, 0, "paid", now - timedelta(days=15), now - timedelta(days=10)),
        (4, 2, 2, 29.99, 2.4, 0, "draft", now + timedelta(days=20), None),
    ]
    for inv_id, org, sub, amount, tax, disc, status, due, paid in invoices:
        session.execute(text("""
            INSERT INTO invoices (id, org_id, subscription_id, amount, tax, discount, status, due_date, paid_at)
            VALUES (:id, :org, :sub, :amount, :tax, :disc, :status, :due, :paid)
            ON CONFLICT DO NOTHING
        """), {"id": inv_id, "org": org, "sub": sub, "amount": amount, "tax": tax, "disc": disc, "status": status, "due": due, "paid": paid})

    # Coupons
    session.execute(text("""
        INSERT INTO coupons (id, code, discount_percent, max_uses, current_uses, expires_at, is_active)
        VALUES (1, 'SAVE20', 20, 100, 5, :exp, TRUE) ON CONFLICT DO NOTHING
    """), {"exp": now + timedelta(days=90)})
    session.execute(text("""
        INSERT INTO coupons (id, code, discount_percent, max_uses, current_uses, expires_at, is_active)
        VALUES (2, 'HALFOFF', 50, 10, 2, :exp, TRUE) ON CONFLICT DO NOTHING
    """), {"exp": now + timedelta(days=30)})

    session.commit()
    print("[billing] Seeded subscriptions, invoices, coupons")
    session.close()


def seed_payments():
    """Seed payment_db."""
    session = get_session("payment")

    for ddl in [
        """CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY, invoice_id INTEGER NOT NULL, org_id INTEGER NOT NULL,
            amount FLOAT NOT NULL, method VARCHAR(50) DEFAULT 'card',
            card_number VARCHAR(20) DEFAULT '', card_expiry VARCHAR(10) DEFAULT '',
            status VARCHAR(50) DEFAULT 'pending', transaction_ref VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS refunds (
            id SERIAL PRIMARY KEY, payment_id INTEGER NOT NULL, amount FLOAT NOT NULL,
            reason TEXT DEFAULT '', status VARCHAR(50) DEFAULT 'pending',
            requested_by INTEGER, approved_by INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]:
        session.execute(text(ddl))
    session.commit()

    # Payments for paid invoices
    session.execute(text("""
        INSERT INTO payments (id, invoice_id, org_id, amount, method, card_number, card_expiry, status, transaction_ref)
        VALUES (1, 1, 1, 99.99, 'card', '4111111111111111', '12/27', 'completed', 'TXN-001')
        ON CONFLICT DO NOTHING
    """))
    session.execute(text("""
        INSERT INTO payments (id, invoice_id, org_id, amount, method, card_number, card_expiry, status, transaction_ref)
        VALUES (2, 3, 2, 29.99, 'card', '5500000000000004', '06/26', 'completed', 'TXN-002')
        ON CONFLICT DO NOTHING
    """))

    session.commit()
    print("[payment] Seeded 2 payments")
    session.close()


def seed_notifications():
    """Seed notification_db."""
    session = get_session("notification")

    for ddl in [
        """CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY, user_id INTEGER, org_id INTEGER,
            type VARCHAR(100) DEFAULT '', title VARCHAR(255) NOT NULL, body TEXT DEFAULT '',
            channel VARCHAR(50) DEFAULT 'in_app', status VARCHAR(50) DEFAULT 'pending',
            metadata_json TEXT, webhook_response TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS notification_preferences (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, channel VARCHAR(50) NOT NULL,
            enabled BOOLEAN DEFAULT TRUE, webhook_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]:
        session.execute(text(ddl))
    session.commit()

    # Sample notifications
    session.execute(text("""
        INSERT INTO notifications (user_id, org_id, type, title, body, channel, status)
        VALUES (1, 1, 'payment', 'Payment Received', 'Invoice #1 paid successfully', 'in_app', 'sent')
    """))
    session.execute(text("""
        INSERT INTO notifications (user_id, org_id, type, title, body, channel, status)
        VALUES (4, 2, 'payment', 'Payment Received', 'Invoice #3 paid successfully', 'in_app', 'sent')
    """))

    session.commit()
    print("[notification] Seeded notifications")
    session.close()


def seed_reporting():
    """Seed reporting_db."""
    session = get_session("reporting")

    session.execute(text("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY, org_id INTEGER NOT NULL, requested_by INTEGER NOT NULL,
            report_type VARCHAR(50) NOT NULL, status VARCHAR(50) DEFAULT 'queued',
            parameters_json TEXT, file_path VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    session.commit()

    session.execute(text("""
        INSERT INTO reports (org_id, requested_by, report_type, status, parameters_json)
        VALUES (1, 1, 'billing', 'ready', '{"date_from": "2024-01-01", "date_to": "2024-12-31"}')
    """))
    session.commit()
    print("[reporting] Seeded reports")
    session.close()


def main():
    print("=" * 60)
    print("Seeding Distributed Vulnerable Platform databases...")
    print("=" * 60)
    print(f"PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}")
    print()

    seed_auth()
    seed_users()
    seed_projects()
    seed_billing()
    seed_payments()
    seed_notifications()
    seed_reporting()

    print()
    print("=" * 60)
    print("Seeding complete!")
    print()
    print("Test credentials:")
    print(f"  Password for all users: {DEFAULT_PASSWORD}")
    print("  Users:")
    print("    admin@acme.com (admin, Org 1 - Acme)")
    print("    alice@acme.com (user, Org 1 - Acme)")
    print("    bob@acme.com (viewer, Org 1 - Acme)")
    print("    admin@globex.com (admin, Org 2 - Globex)")
    print("    eve@globex.com (user, Org 2 - Globex)")
    print("    system@internal (admin, no org)")
    print("=" * 60)


if __name__ == "__main__":
    main()
