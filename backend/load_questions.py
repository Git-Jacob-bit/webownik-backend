from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List
from database import get_db, User, Question, Answer
from users import get_current_user

router = APIRouter()

@router.post("/upload-folder/")
async def upload_folder(
    dataset_name: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Użytkownik pobierany z JWT
):
    """✅ Pozwala zalogowanemu użytkownikowi dodać bazę pytań do swojego profilu."""

    if not files:
        raise HTTPException(status_code=400, detail="❌ Nie przesłano żadnych plików!")

    # 🔹 Sprawdzamy, czy użytkownik ma już bazę o tej nazwie
    existing_dataset = db.query(Question).filter(
        Question.user_id == current_user.id,
        Question.dataset_name == dataset_name
    ).first()

    if existing_dataset:
        raise HTTPException(status_code=400, detail=f"❌ Baza pytań '{dataset_name}' już istnieje!")

    files_processed = 0

    for file in files:
        try:
            contents = await file.read()
            contents = contents.decode("utf-8").strip()
            lines = contents.split("\n")
        except Exception:
            raise HTTPException(status_code=400, detail=f"❌ Nie można odczytać pliku {file.filename}!")

        if len(lines) < 3:
            raise HTTPException(status_code=400, detail=f"❌ Plik {file.filename} ma nieprawidłowy format!")

        answer_key = lines[0].strip()
        if answer_key.startswith("X"):
            answer_key = answer_key[1:]

        # 🔹 Sprawdzamy, czy odpowiedzi są w poprawnym formacie (tylko 0 i 1)
        if not all(c in "01" for c in answer_key):
            raise HTTPException(status_code=400, detail=f"❌ Plik {file.filename} zawiera niepoprawne oznaczenia odpowiedzi!")

        question_text = lines[1].strip()
        answers = [line.strip() for line in lines[2:] if line.strip()]
        correct_answers = [bool(int(x)) for x in answer_key[:len(answers)]]

        # 🔹 Tworzymy pytanie i zapisujemy do bazy
        question = Question(user_id=current_user.id, dataset_name=dataset_name, question_text=question_text)
        db.add(question)
        db.commit()
        db.refresh(question)  # ✅ Pobieramy `id` nowo dodanego pytania

        # 🔹 Tworzymy odpowiedzi i zapisujemy do bazy
        for i in range(len(answers)):
            answer = Answer(
                question_id=question.id,
                answer_text=answers[i],
                is_correct=correct_answers[i]
            )
            db.add(answer)

        db.commit()
        files_processed += 1

    return {
        "message": f"✅ Pytania i odpowiedzi dodane do bazy '{dataset_name}' użytkownika {current_user.username}.",
        "count": files_processed
    }
