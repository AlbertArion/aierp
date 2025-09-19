from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ...utils.auth.jwt import create_token, verify_token, has_role

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest) -> Dict[str, Any]:
    # 演示：固定账号
    if payload.username == "admin" and payload.password == "admin123":
        token = create_token(sub="admin", roles=["admin"])
        return {"token": token, "user": {"name": "admin", "roles": ["admin"]}}
    if payload.username == "ops" and payload.password == "ops123":
        token = create_token(sub="ops", roles=["ops"])
        return {"token": token, "user": {"name": "ops", "roles": ["ops"]}}
    raise HTTPException(status_code=401, detail="invalid credentials")


def require_auth(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return verify_token(token)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="invalid token") from e


def require_role(role: str):
    def _checker(payload: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        if not has_role(payload, role):
            raise HTTPException(status_code=403, detail="forbidden")
        return payload
    return _checker


