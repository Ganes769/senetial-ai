
from fastapi import FastAPI
from api.routes.theme import router as themes_router

app = FastAPI(title="Sentinel AI API")

app.include_router(themes_router)

@app.get("/")
def root():
    return {"message": "Sentinel AI is running"}
