from passlib.context import CryptContext
from fastapi import Request, HTTPException,status
from fastapi.responses import RedirectResponse


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# เอา hash ที่คุณ generate ใส่ตรงนี้
SYSTEM_ADMIN_PASSWORD_HASH = "$2b$12$xaA57wvXqCDznUsBWB/iLOgGabSb7ib8ocVZsBtFRK72yH633.AdG"

SESSION_SECRET_KEY = "parcel-session-secret"


def verify_admin_password(password: str) -> bool:
    return pwd_context.verify(password, SYSTEM_ADMIN_PASSWORD_HASH)


def require_admin(request: Request):

    admin = request.session.get("admin")

    if not admin:
        raise HTTPException(
            status_code=302,
            headers={"Location": "/login_admin"}
        )

    return admin