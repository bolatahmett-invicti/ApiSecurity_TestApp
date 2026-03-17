FROM python:3.12-slim

RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn==0.30.6 \
    sqlalchemy==2.0.35 \
    psycopg2-binary==2.9.9 \
    pydantic==2.9.2 \
    "pydantic[email]" \
    PyJWT==2.9.0 \
    "passlib[bcrypt]==1.7.4" \
    pika==1.3.2 \
    httpx==0.27.0

WORKDIR /app

CMD ["python", "main.py"]
