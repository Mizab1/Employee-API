from fastapi import APIRouter, HTTPException
from app.db.client import ping_db

router = APIRouter(tags=["system"])

@router.get("/health")
def health():
    if not ping_db():
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
