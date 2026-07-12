"""FastAPI dependencies: DB session, current user, role guards.

Role guards: require_roles(Role.esg_manager) — Admin always passes implicitly.
Object-level scoping (e.g. dept-head approval scope) lives in
app.services.org.can_decide_for / managed_dept_ids.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.core import User
from app.models.enums import Role

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = security.decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or deactivated"
        )
    return user


def require_roles(*roles: Role):
    allowed = set(roles) | {Role.admin}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return user

    return checker


# Common shortcuts
require_admin = require_roles()  # admin only
require_esg = require_roles(Role.esg_manager)  # esg_manager or admin
require_head = require_roles(Role.dept_head, Role.esg_manager)  # head, esg or admin
