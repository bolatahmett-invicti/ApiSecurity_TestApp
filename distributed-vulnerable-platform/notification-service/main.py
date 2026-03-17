import threading
import uvicorn
from fastapi import FastAPI
from database import engine, Base
from routes import router
from consumer import start_consumer

app = FastAPI(title="Notification Service", debug=True)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification-service"}


@app.on_event("startup")
def on_startup():
    # Create all database tables
    Base.metadata.create_all(bind=engine)

    # Start RabbitMQ consumer in a background thread
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()
    print("[startup] RabbitMQ consumer thread started")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8006)
