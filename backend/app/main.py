from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies import get_current_user
from app.routers import ask, documents, conversations, audit

app = FastAPI(title="CareOps API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(audit.router)

@app.get("/me")
def whoami(user: dict = Depends(get_current_user)):
    return user