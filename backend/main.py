from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from database import init_db
from load_questions import router as questions_router
from get_questions import router as get_questions_router
from quiz import router as quiz_router
from users import router as users_router

app = FastAPI()

# 🔹 Konfiguracja CORS (umożliwia dostęp do API z innych domen, np. frontend React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔹 Tu można podać konkretne adresy np. ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 OAuth2 dla Swagger UI (teraz poprawnie działa z JWT)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 🔹 Rejestracja routerów
app.include_router(users_router, prefix="/users")
app.include_router(questions_router, prefix="/questions")
app.include_router(get_questions_router, prefix="/datasets")
app.include_router(quiz_router, prefix="/quiz")

# 🔹 Inicjalizacja bazy danych (na końcu, aby uniknąć problemów z importami)
init_db()
