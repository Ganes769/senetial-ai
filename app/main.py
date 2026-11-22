
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.ingestion import router as ingestion_router
from api.routes.theme import router as themes_router

app = FastAPI(title="Sentinel AI API")

# Vite serves the React app on localhost:5173. The browser treats
# localhost and 127.0.0.1 as different origins, so both are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(themes_router)
app.include_router(ingestion_router)

@app.get("/")
def root():
    return {"message": "Sentinel AI is running"}
