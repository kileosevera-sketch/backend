from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from app.routers import auth, dashboards, users

app = FastAPI(title="Post-Sales AI Analytics Platform — Backend API")

app.include_router(auth.router)
app.include_router(dashboards.router)
app.include_router(users.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}