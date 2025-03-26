from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Question, User
from users import get_current_user

router = APIRouter()

@router.get("/datasets/")
def get_datasets(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """✅ Zwraca listę baz pytań przypisanych do zalogowanego użytkownika."""

    datasets = db.query(Question.dataset_name).filter(
        Question.user_id == current_user.id
    ).distinct().all()

    dataset_list = [d[0] for d in datasets] if datasets else []

    return {"datasets": dataset_list}

@router.get("/questions/{dataset_name}")
def get_questions(
    dataset_name: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """✅ Zwraca wszystkie pytania z wybranej bazy pytań użytkownika."""

    questions = db.query(Question).filter(
        Question.user_id == current_user.id,
        Question.dataset_name == dataset_name
    ).all()

    if not questions:
        raise HTTPException(status_code=404, detail=f"❌ Brak pytań w bazie '{dataset_name}'!")

    return {
        "dataset_name": dataset_name,
        "questions": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "answers": [
                    {"id": a.id, "text": a.answer_text, "is_correct": a.is_correct}
                    for a in q.answers
                ]
            }
            for q in questions
        ]
    }

@router.delete("/datasets/{dataset_name}")
def delete_dataset(dataset_name: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    ✅ Usuwa cały zestaw pytań z bazy danych
    """
    questions = db.query(Question).filter(Question.dataset_name == dataset_name).all()

    if not questions:
        raise HTTPException(status_code=404, detail="Zestaw pytań nie istnieje.")

    for question in questions:
        db.delete(question)

    db.commit()

    return {"message": f"Zestaw pytań '{dataset_name}' został usunięty."}
