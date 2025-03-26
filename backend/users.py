from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import timedelta, datetime
from jose import jwt, JWTError
from database import get_db, User
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Request
from email_utils import send_reset_email
from database import UsedResetToken
import time
import os



ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")


# słownik: email → timestamp ostatniego żądania
last_reset_request = {}


# 🔹 Klucz JWT
SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

router = APIRouter()

# 🔹 Hashowanie haseł
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 🔹 Nowa konfiguracja JWT – teraz Swagger pozwala wpisać token ręcznie
oauth2_scheme = HTTPBearer()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Tworzy token JWT dla użytkownika"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register/")
def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """✅ Rejestracja nowego użytkownika"""
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Użytkownik o tej nazwie już istnieje.")
    
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Użytkownik z tym adresem e-mail już istnieje.")


    hashed_password = pwd_context.hash(password)
    new_user = User(username=username, email=email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Użytkownik zarejestrowany!", "user_id": new_user.id}

@router.post("/token/")
def login_user(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """✅ Logowanie użytkownika i zwracanie tokena"""
    user = db.query(User).filter(User.email == email).first()
    if not user or not pwd_context.verify(password, user.password):
        raise HTTPException(status_code=401, detail="Niepoprawne dane logowania.")

    token = create_access_token({
    "sub": str(user.id),
    "email": user.email,
    "is_admin": user.is_admin
})
 # 🔹 Teraz zapisujemy ID, a nie username!
    return {"access_token": token, "token_type": "bearer"}

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """✅ Pobiera aktualnie zalogowanego użytkownika z JWT"""
    token = credentials.credentials  # Pobieramy tylko wartość tokena, bez "Bearer"
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Nieprawidłowy token")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Nie znaleziono użytkownika")

        return user  # ✅ Zwracamy OBIEKT `User`, a nie słownik
    except JWTError:
        raise HTTPException(status_code=401, detail="Nie można zweryfikować tokena")

def require_admin(user: User = Depends(get_current_user)):
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Nie masz uprawnień")
    return user


@router.get("/me/")
def read_users_me(current_user: User = Depends(get_current_user)):
    """✅ Zwraca dane aktualnie zalogowanego użytkownika"""
    return {"user_id": current_user.id, "username": current_user.username}

@router.get("/all/")
def list_all_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
            "is_admin": user.is_admin,
        }
        for user in users
    ]

@router.delete("/{user_id}/")
def delete_user_by_id(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")

    db.delete(user)
    db.commit()
    return {"message": f"Użytkownik {user.username} został usunięty."}


@router.post("/password-reset-request")
def password_reset_request(email: str = Form(...), db: Session = Depends(get_db)):
    """🔐 Generuje token do zresetowania hasła i (na razie) zwraca go"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik z takim e-mailem nie istnieje.")

    # Tworzymy token z krótką ważnością (np. 15 minut)
    reset_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=15)
    )

    now = time.time()
    last_time = last_reset_request.get(email)

    if last_time and now - last_time < 60:
        raise HTTPException(
            status_code=429,
            detail="Poczekaj chwilę przed kolejnym resetem hasła."
        )

    # zaktualizuj znacznik czasu
    last_reset_request[email] = now


    # return {"reset_token": reset_token}
    send_reset_email(user.email, reset_token)
    return {"message": "E-mail z linkiem został wysłany!"}


    
@router.post("/reset-password")
def reset_password(
    token: str,
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """🛠 Ustawia nowe hasło użytkownika na podstawie tokena"""
    try:
        used = db.query(UsedResetToken).filter(UsedResetToken.token == token).first()
        if used:
            raise HTTPException(status_code=400, detail="Token został już użyty.")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy lub wygasły token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")

    # Haszujemy i zapisujemy nowe hasło
    user.password = pwd_context.hash(new_password)
    db.add(UsedResetToken(token=token))
    db.commit()

    return {"message": "Hasło zostało zmienione"}


