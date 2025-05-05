from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, ChatHistory, SessionToken

# --------- Config ---------
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# --------- Password hashing ---------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --------- User operations ---------
def register_user(db: Session, username: str, password: str, email: Optional[str] = None, gender: Optional[str] = None) -> User:
    hashed_password = pwd_context.hash(password)
    user = User(username=username, email=email, gender=gender, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    try:
        if not pwd_context.verify(password, user.hashed_password):
            return None
    except Exception:
        if password != user.hashed_password:
            return None
    return user

# --------- JWT operations ---------
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# --------- Chat history ---------
def save_chat(username: str, user_message: str, bot_reply: str, thread_id: int = None) -> int:
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return None

        chat = ChatHistory(
            user_id   = user.id,
            message   = user_message,
            response  = bot_reply,
            thread_id = thread_id or 0
        )
        session.add(chat)
        session.commit()
        session.refresh(chat)

        if not thread_id:
            chat.thread_id = chat.id
            session.commit()

        return chat.thread_id
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()

def get_chat_history(username: str) -> list[tuple[str, str]]:
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return []
        chats = session.query(ChatHistory).filter_by(user_id=user.id).order_by(ChatHistory.timestamp.asc()).all()
        return [(c.message, c.response) for c in chats]
    finally:
        session.close()

# --------- Session Token operations ---------
def save_token_to_db(db: Session, user_id: int, token: str):
    try:
        existing = db.query(SessionToken).filter_by(user_id=user_id).first()
        if existing:
            existing.token = token
        else:
            new_token = SessionToken(user_id=user_id, token=token)
            db.add(new_token)
        db.commit()
    except Exception as e:
        db.rollback()
        print("❌ Token kayıt hatası:", e)

def delete_token_from_db(db: Session, token: str):
    try:
        payload = decode_token(token)
        if not payload:
            return False
        user_id = payload.get("id")
        db.query(SessionToken).filter_by(user_id=user_id).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print("❌ Token silme hatası:", e)
        return False