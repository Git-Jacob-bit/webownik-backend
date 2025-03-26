from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


# Konfiguracja bazy danych
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Konfiguracja JWT
SECRET_KEY = "supersecretkey"  # 🔹 Zmień to na bardziej bezpieczny klucz!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Konfiguracja bcrypt do haszowania haseł
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_db():
    """Tworzy tabele w bazie, jeśli nie istnieją."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Tworzy sesję bazy danych i zamyka ją po zakończeniu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    is_admin = Column(Boolean, default=False)
    username = Column(String, unique=True, nullable=False) 
    email = Column(String, unique=True, nullable=False) 
    password = Column(String, nullable=False)  # ✅ Hasło będzie przechowywane w postaci hashowanej
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacje
    questions = relationship("Question", back_populates="user", cascade="all, delete-orphan")
    scores = relationship("UserScore", back_populates="user", cascade="all, delete-orphan")

    # Metody dla haseł i tokenów
    def set_password(self, password: str):
        """Haszuje hasło użytkownika"""
        self.password = pwd_context.hash(password)  # ✅ Poprawione przechowywanie hasha

    def verify_password(self, password: str):
        """Sprawdza czy podane hasło jest poprawne"""
        return pwd_context.verify(password, self.password)  # ✅ Poprawione porównywanie hasła

    def get_jwt_token(self):
        """Generuje token JWT dla użytkownika"""
        expiration = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": self.id, "exp": expiration}  # 🔹 ID zamiast username
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_jwt_token(token: str):
        """Dekoduje token JWT i zwraca ID użytkownika"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub")  # ✅ Poprawione zwracanie ID użytkownika
        except jwt.ExpiredSignatureError:
            return None  # Token wygasł
        except jwt.PyJWTError:
            return None  # Token nieprawidłowy

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  
    dataset_name = Column(String, nullable=False)  
    question_text = Column(Text, nullable=False)

    user = relationship("User", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    question = relationship("Question", back_populates="answers")

class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  
    question_id = Column(Integer, nullable=False)  
    position = Column(Integer, nullable=False)  

class UserScore(Base):
    __tablename__ = "user_scores"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, default=0)

    user = relationship("User", back_populates="scores")

class UsedResetToken(Base):
    __tablename__ = "used_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)

