from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules import attendance, auth, billing, branches, members, onboarding, platform, reports

settings = get_settings()
app = FastAPI(title="Gym-OS API", version="0.1.0",
              description="Multi-tenant gym management SaaS — powered by Manima AI Tech Solutions",
              docs_url=None if settings.is_prod else "/docs")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

API = "/api/v1"
for m in (auth, onboarding, platform, branches, members, billing, attendance, reports):
    app.include_router(m.router, prefix=API)


@app.get("/health")
def health():
    return {"status": "ok"}
