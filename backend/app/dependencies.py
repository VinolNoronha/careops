from fastapi import Depends, HTTPException, Header
import jwt
from jwt import PyJWKClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import get_db

JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
jwks_client = PyJWKClient(JWKS_URL)


def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except Exception as e:
        #print("JWT DECODE FAILED:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    result = db.execute(
        text("select id, email, hospital_id, role, department from users where id = :id"),
        {"id": user_id},
    ).fetchone()

    if not result:
        raise HTTPException(status_code=403, detail="User not provisioned")

    if result.role == "pending" or result.hospital_id is None:
        raise HTTPException(status_code=403, detail="Account not yet assigned to a hospital")

    return {
        "id": result.id,
        "email": result.email,
        "hospital_id": result.hospital_id,
        "role": result.role,
        "department": result.department,
    }


def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user