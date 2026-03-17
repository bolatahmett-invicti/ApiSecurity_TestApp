import uvicorn
from fastapi import FastAPI
from database import engine, Base
from routes import router

app = FastAPI(title="Reporting Service", debug=True)

app.include_router(router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "reporting-service"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
