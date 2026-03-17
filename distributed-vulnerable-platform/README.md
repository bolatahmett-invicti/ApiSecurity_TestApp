# Distributed Vulnerable Platform

A **deliberately vulnerable** distributed SaaS platform for testing API security scanners, DAST engines, and business logic vulnerability detection systems.

> **WARNING**: This platform contains intentional security vulnerabilities. It is designed exclusively for security research and testing. Do NOT deploy in production or expose to the internet.

## Architecture

```
                    ┌─────────────┐
                    │   Gateway   │ :8000
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
    │ Auth :8001  │ │ User :8002  │ │Project:8003 │
    └─────────────┘ └─────────────┘ └─────────────┘
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │Billing:8004 │ │Payment:8005 │ │Notif. :8006 │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────┬───────┘───────┬───────┘
            ┌──────┴──────┐ ┌──────┴──────┐
            │  RabbitMQ   │ │  PostgreSQL  │
            └─────────────┘ └─────────────┘
    ┌─────────────┐
    │Report :8007 │
    └─────────────┘
```

**Tech Stack**: Python FastAPI, PostgreSQL, SQLAlchemy, RabbitMQ, JWT, Docker

## Quick Start

```bash
# Start all services
docker-compose up --build -d

# Wait for services to be healthy (~30 seconds)
docker-compose ps

# Seed test data
pip install psycopg2-binary passlib[bcrypt] sqlalchemy
python seed_data.py

# Verify
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

## Test Credentials

| Email | Password | Role | Organization |
|-------|----------|------|-------------|
| admin@acme.com | Password123! | admin | Acme Corp (Org 1) |
| alice@acme.com | Password123! | user | Acme Corp (Org 1) |
| bob@acme.com | Password123! | viewer | Acme Corp (Org 1) |
| admin@globex.com | Password123! | admin | Globex Inc (Org 2) |
| eve@globex.com | Password123! | user | Globex Inc (Org 2) |
| system@internal | Password123! | admin | — |

## API Endpoints

### Auth Service (via Gateway: /api/auth/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/register | No | Register |
| POST | /api/auth/login | No | Login → JWT |
| POST | /api/auth/refresh | No | Refresh token |
| GET | /api/auth/me | JWT | Current user |
| POST | /api/auth/reset-password | No | Reset password |

### User Service (via Gateway: /api/users/*, /api/orgs/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/users | JWT | List users |
| GET | /api/users/{id} | JWT | Get user |
| PUT | /api/users/{id} | JWT | Update user |
| DELETE | /api/users/{id} | JWT | Delete user |
| GET | /api/orgs | JWT | List orgs |
| POST | /api/orgs | JWT | Create org |
| GET | /api/orgs/{id} | JWT | Get org |
| GET | /api/orgs/{id}/members | JWT | List members |
| POST | /api/orgs/{id}/invite | JWT | Invite member |
| POST | /api/orgs/{id}/api-tokens | JWT | Create token |
| GET | /api/orgs/{id}/api-tokens | JWT | List tokens |

### Project Service (via Gateway: /api/projects/*, /api/tasks/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/projects | JWT | List projects |
| POST | /api/projects | JWT | Create project |
| GET | /api/projects/{id} | JWT | Get project |
| PUT | /api/projects/{id} | JWT | Update project |
| DELETE | /api/projects/{id} | JWT | Delete project |
| GET | /api/projects/{id}/tasks | JWT | List tasks |
| POST | /api/projects/{id}/tasks | JWT | Create task |
| GET | /api/tasks/{id} | JWT | Get task |
| PUT | /api/tasks/{id} | JWT | Update task |

### Billing Service (via Gateway: /api/billing/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/billing/subscriptions | JWT | List subscriptions |
| POST | /api/billing/subscriptions | JWT | Create subscription |
| PUT | /api/billing/subscriptions/{id} | JWT | Update subscription |
| GET | /api/billing/invoices | JWT | List invoices |
| POST | /api/billing/invoices | JWT | Create invoice |
| GET | /api/billing/invoices/{id} | JWT | Get invoice |
| POST | /api/billing/invoices/{id}/apply-coupon | JWT | Apply coupon |
| POST | /api/billing/invoices/{id}/refund | JWT | Refund invoice |
| POST | /api/billing/coupons | JWT | Create coupon |
| GET | /api/billing/coupons/{code} | JWT | Validate coupon |

### Payment Service (via Gateway: /api/payments/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/payments | JWT | Create payment |
| GET | /api/payments/{id} | JWT | Get payment |
| GET | /api/payments | JWT | List payments |
| POST | /api/payments/{id}/refund | JWT | Request refund |
| PUT | /api/payments/{id}/refund/approve | JWT | Approve refund |
| POST | /internal/payments/confirm | Internal | Confirm payment |

### Notification Service (via Gateway: /api/notifications/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/notifications | JWT | List notifications |
| POST | /api/notifications/send | JWT | Send notification |
| POST | /api/notifications/broadcast | JWT | Broadcast |
| PUT | /api/notifications/preferences | JWT | Update prefs |
| POST | /internal/events | Internal | Receive event |

### Reporting Service (via Gateway: /api/reports/*)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/reports/generate | JWT | Generate report |
| GET | /api/reports/{id} | JWT | Get report |
| GET | /api/reports | JWT | List reports |
| GET | /api/reports/{id}/download | JWT | Download report |

## Intentional Vulnerability Catalog

### 1. BOLA (Broken Object Level Authorization)
| Service | Endpoint | Description |
|---------|----------|-------------|
| user-service | `GET /users/{id}` | Any user can access any user's profile |
| user-service | `PUT /users/{id}` | Any user can update any user |
| user-service | `GET /orgs/{id}` | No membership verification |
| project-service | `GET /projects/{id}` | Cross-org project access |
| project-service | `GET /tasks/{id}` | Direct task access without org check |
| billing-service | `GET /billing/invoices/{id}` | No ownership check |
| payment-service | `GET /payments/{id}` | No org check |
| reporting-service | `GET /reports/{id}` | No ownership verification |

### 2. Broken Function Level Authorization
| Service | Endpoint | Description |
|---------|----------|-------------|
| user-service | `DELETE /users/{id}` | No admin role check |
| billing-service | `POST /billing/coupons` | Admin endpoint, no role check |
| payment-service | `PUT /payments/{id}/refund/approve` | No admin verification |
| notification-service | `POST /notifications/broadcast` | Checks header instead of JWT role |

### 3. Workflow Bypass
| Service | Endpoint | Description |
|---------|----------|-------------|
| billing-service | `POST /billing/invoices/{id}/refund` | Refund without prior payment |
| billing-service | `PUT /billing/subscriptions/{id}` | Upgrade without payment |
| payment-service | `POST /payments` | Pay already-paid invoice |

### 4. State Confusion / Race Conditions
| Service | Endpoint | Description |
|---------|----------|-------------|
| payment-service | `POST /payments` | Concurrent payments both succeed (double-charge) |
| billing-service | `POST /billing/invoices/{id}/apply-coupon` | No idempotency, coupon applied multiple times |
| billing-service | Invoice status | Can go draft → refunded skipping paid |

### 5. Cross-Service Trust Exploitation
| Service | Endpoint | Description |
|---------|----------|-------------|
| payment-service | `POST /internal/payments/confirm` | Trusts X-Service-Name header |
| billing-service | RabbitMQ consumer | Trusts payment_completed events blindly |
| notification-service | `POST /internal/events` | No auth on internal endpoint |
| gateway | All routes | Forwards attacker-injected headers |

### 6. Bulk Data Harvesting
| Service | Endpoint | Description |
|---------|----------|-------------|
| user-service | `GET /users?page_size=10000` | No max page size, no org filter |
| project-service | `GET /projects` | Returns all projects globally |
| payment-service | `GET /payments` | Returns all payments cross-org |
| All services | Sequential IDs | Enumerable integer primary keys |

### 7. Sensitive Data Exposure
| Service | Endpoint | Description |
|---------|----------|-------------|
| user-service | `GET /users/{id}` | Returns ssn_last4, internal_notes, password_hash |
| user-service | `GET /orgs/{id}/api-tokens` | Plaintext API tokens in response |
| auth-service | `POST /auth/login` | "User not found" vs "Incorrect password" |
| auth-service | `POST /auth/reset-password` | Password reset without email verification |
| payment-service | `GET /payments/{id}` | Full card_number and card_expiry |
| All services | Error responses | Stack traces via debug=True |

### 8. Event Injection
| Service | Endpoint | Description |
|---------|----------|-------------|
| notification-service | RabbitMQ consumer | Accepts unverified events |
| billing-service | RabbitMQ consumer | Fake payment_completed marks invoice as paid |
| RabbitMQ | :15672 | Default guest/guest, management UI exposed |

### 9. Resource Amplification
| Service | Endpoint | Description |
|---------|----------|-------------|
| reporting-service | `POST /reports/generate` | No rate limit, expensive queries |
| notification-service | `POST /notifications/send` | target="all_users" fans out to all |
| notification-service | Webhook channel | SSRF via webhook_url |

## Service Ports

| Service | Port | OpenAPI Docs |
|---------|------|-------------|
| Gateway | 8000 | http://localhost:8000/docs |
| Auth | 8001 | http://localhost:8001/docs |
| User | 8002 | http://localhost:8002/docs |
| Project | 8003 | http://localhost:8003/docs |
| Billing | 8004 | http://localhost:8004/docs |
| Payment | 8005 | http://localhost:8005/docs |
| Notification | 8006 | http://localhost:8006/docs |
| Reporting | 8007 | http://localhost:8007/docs |
| RabbitMQ Mgmt | 15672 | http://localhost:15672 (guest/guest) |
| PostgreSQL | 5432 | — |

## Example: Exploit BOLA

```bash
# Login as eve@globex.com (Org 2)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"eve@globex.com","password":"Password123!"}' | jq -r .access_token)

# Access Acme Corp's admin profile (Org 1, user_id=1) — should be forbidden, but works
curl -s http://localhost:8000/api/users/1 -H "Authorization: Bearer $TOKEN" | jq .

# See SSN, internal notes, password hash in response
```

## Example: Workflow Bypass

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@acme.com","password":"Password123!"}' | jq -r .access_token)

# Refund invoice #2 which is still "pending" (never paid)
curl -s -X POST http://localhost:8000/api/billing/invoices/2/refund \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## Example: Cross-Service Trust

```bash
# Confirm a payment via internal endpoint — no JWT needed, just a header
curl -s -X POST http://localhost:8005/internal/payments/confirm \
  -H "Content-Type: application/json" \
  -H "X-Service-Name: billing-service" \
  -d '{"payment_id": 1}'
```
