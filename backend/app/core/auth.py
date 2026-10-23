from typing import Optional
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User, Supplier


def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    """
    Demo authentication dependency (PRD §7 A-7, HLD §2).
    Resolves X-User-Id header against pre-seeded users in PostgreSQL.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing X-User-Id header",
        )

    try:
        user_id_int = int(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-User-Id header format: must be an integer",
        )

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User with ID {user_id_int} not found",
        )

    return user


def require_buyer(current_user: User = Depends(get_current_user)) -> User:
    """Enforces that the user is a BUYER or ADMIN."""
    if current_user.role not in ("BUYER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action restricted to Buyers. Your role is '{current_user.role}'",
        )
    return current_user


def require_supplier(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Supplier:
    """Enforces that the user is a registered, active SUPPLIER."""
    if current_user.role != "SUPPLIER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Action restricted to Suppliers. Your role is '{current_user.role}'",
        )

    supplier = db.query(Supplier).filter(Supplier.user_id == current_user.id).first()
    if not supplier or not supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier profile not found or is currently inactive",
        )

    return supplier
