from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))
