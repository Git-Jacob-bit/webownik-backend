from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db, Question, QuizSession, Answer, UserScore, User
from users import get_current_user
from typing import List
import random

router = APIRouter()

@router.post("/quiz/")
def start_quiz(dataset_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """✅ Tworzy nową sesję quizu dla zalogowanego użytkownika."""

    questions = db.query(Question).filter(
        Question.user_id == current_user.id, Question.dataset_name == dataset_name
    ).all()
    if not questions:
        raise HTTPException(status_code=404, detail="Brak pytań w tej bazie!")

    question_list = questions * 2  
    random.shuffle(question_list)

    for position, question in enumerate(question_list):
        db.add(QuizSession(user_id=current_user.id, question_id=question.id, position=position))

    db.commit()
    return {"message": "✅ Quiz został rozpoczęty!", "total_questions": len(question_list)}

@router.delete("/quiz/reset/")
def reset_quiz(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """✅ Usuwa aktywną sesję quizu użytkownika."""
    db.query(QuizSession).filter(QuizSession.user_id == current_user.id).delete()
    db.commit()
    return {"message": "✅ Sesja quizu została zresetowana!"}

@router.get("/quiz/next/")
def get_next_question(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """✅ Zwraca kolejne pytanie użytkownika zgodnie z kolejnością w bazie."""
    session_entry = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == current_user.id)
        .order_by(QuizSession.position)
        .first()
    )

    if not session_entry:
        return {"message": "✅ Quiz zakończony!", "finished": True}

    question = db.query(Question).filter(Question.id == session_entry.question_id).first()
    answers = db.query(Answer).filter(Answer.question_id == question.id).all()

    return {
        "id": question.id,
        "question_text": question.question_text,
        "answers": [{"id": a.id, "text": a.answer_text} for a in answers],
        "finished": False
    }

@router.get("/quiz/status/")
def get_quiz_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """✅ Zwraca liczbę pozostałych pytań w quizie oraz aktywną bazę."""
    remaining_questions = db.query(QuizSession).filter(QuizSession.user_id == current_user.id).count()
    
    # Pobieramy pierwsze pytanie z aktywnej sesji
    session_entry = db.query(QuizSession).filter(
        QuizSession.user_id == current_user.id
    ).order_by(QuizSession.position).first()

    dataset_name = None
    if session_entry:
        question = db.query(Question).filter(Question.id == session_entry.question_id).first()
        if question:
            dataset_name = question.dataset_name

    return {
        "remaining_questions": remaining_questions,
        "quiz_active": remaining_questions > 0,
        "dataset_name": dataset_name
    }


@router.post("/quiz/answer/")
def submit_answer(
    question_id: int,
    answers: List[int],
    time: int = Query(0),  # czas przesyłany z frontend jako query param
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obsługuje odpowiedź użytkownika i zarządza kolejką quizu poprzez powtarzanie błędnych pytań."""

    # Pobieramy aktywną sesję quizu dla użytkownika
    session_entry = db.query(QuizSession).filter(
        QuizSession.user_id == current_user.id,
        QuizSession.question_id == question_id
    ).first()

    if not session_entry:
        raise HTTPException(status_code=404, detail="Pytanie nie znajduje się w quizie!")

    # Pobieramy poprawne odpowiedzi dla pytania
    correct_answers = db.query(Answer).filter(
        Answer.question_id == question_id, Answer.is_correct == True
    ).all()

    all_answers = db.query(Answer).filter(Answer.question_id == question_id).all()
    correct_answer_ids = {a.id for a in correct_answers}
    valid_answer_ids = {a.id for a in all_answers}

    # **Walidacja:** Czy podane ID odpowiedzi należą do tego pytania?
    if not set(answers).issubset(valid_answer_ids):
        raise HTTPException(status_code=400, detail="Niepoprawne ID odpowiedzi!")

    # **Sprawdzamy, czy użytkownik poprawnie zaznaczył wszystkie odpowiedzi**
    is_correct = set(answers) == correct_answer_ids

    # **Usuwamy pytanie z kolejki (ale jeśli źle, dodamy je ponownie)**
    current_position = session_entry.position
    db.delete(session_entry)
    db.commit()

    # **Zmieniamy wynik użytkownika**
    user_score = db.query(UserScore).filter(UserScore.user_id == current_user.id).first()
    if not user_score:
        user_score = UserScore(user_id=current_user.id, score=0)
        db.add(user_score)

    if is_correct:
        user_score.score += 10
        user_score.correct += 1
    else:
        user_score.score -= 5
        user_score.incorrect += 1

# Dodaj czas (np. z requestu – możesz przesłać jako query param np. ?time=7)
    user_score.time_spent += time_taken


    db.commit()

    # **Jeśli odpowiedź była błędna – pytanie wraca do kolejki**
    if not is_correct:
        # Pobieramy maksymalną pozycję w quizie
        max_position = db.query(QuizSession.position).filter(
            QuizSession.user_id == current_user.id
        ).order_by(QuizSession.position.desc()).first()
        
        max_position = max_position[0] if max_position else 0

        # 🔹 Ustalanie nowej pozycji dla błędnego pytania (co 3-5 pozycji dalej)
        new_position = min(current_position + random.randint(3, 5), max_position + 1)

        # 🔹 Przesuwamy WSZYSTKIE pytania o 1 pozycję w górę od `new_position`
        db.query(QuizSession).filter(
            QuizSession.user_id == current_user.id,
            QuizSession.position >= new_position
        ).update({QuizSession.position: QuizSession.position + 1})

        db.commit()

        # 🔹 Wstawiamy błędne pytanie dokładnie w `new_position`
        db.add(QuizSession(user_id=current_user.id, question_id=question_id, position=new_position))
        db.commit()

    # ✅ **Sprawdzamy, ile pytań jeszcze zostało w kolejce**
    remaining_questions = db.query(QuizSession).filter(QuizSession.user_id == current_user.id).count()

    return {
        "message": "Poprawna odpowiedź!" if is_correct else "Błędna odpowiedź! Pytanie pojawi się ponownie.",
        "correct": is_correct,
        "new_score": user_score.score,
        "remaining_questions": remaining_questions,
        "quiz_finished": remaining_questions == 0,  # ✅ Zwracamy, czy quiz się skończył
        "correct_answers": [a.id for a in correct_answers]  # 🔹 Teraz frontend wie, które odpowiedzi były poprawne!

    }


@router.get("/quiz/debug/")
def debug_quiz(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """✅ Zwraca całą kolejkę pytań użytkownika w quizie."""
    session_entries = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == current_user.id)
        .order_by(QuizSession.position)
        .all()
    )
    
    if not session_entries:
        return {"message": "✅ Brak aktywnego quizu dla tego użytkownika."}
    
    queue = []
    for entry in session_entries:
        question = db.query(Question).filter(Question.id == entry.question_id).first()
        queue.append({
            "id": question.id,
            "question_text": question.question_text,
            "position": entry.position
        })
    
    return {"quiz_queue": queue}

@router.get("/ranking/")
def get_ranking(db: Session = Depends(get_db)):
    """✅ Zwraca ranking użytkowników według punktów."""
    top_users = db.query(UserScore).order_by(UserScore.score.desc()).limit(10).all()
    
    return [
        {"user_id": user.user_id, "score": user.score}
        for user in top_users
    ]
