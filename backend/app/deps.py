from datetime import datetime, timezone

from bson import ObjectId
from fastapi import Depends, Header, HTTPException, Request, status

from app.database import get_db
from app.services.rate_limit import check_rate_limit
from app.services.security import decode_token


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "created_at": user.get("created_at", datetime.now(timezone.utc)),
    }


async def rate_limit(
    request: Request, user: dict | None = Depends(lambda: None)
) -> None:
    key = request.client.host if request.client else "anon"
    if not check_rate_limit(f"ip:{key}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")


async def user_rate_limit(user: dict = Depends(get_current_user)) -> dict:
    if not check_rate_limit(f"user:{user['id']}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
    return user
