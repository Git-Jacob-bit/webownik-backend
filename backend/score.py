from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, UserScore
from users import get_current_user

router = APIRouter()

@router.get("/score/me")
def get_my_score(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    score = db.query(UserScore).filter(UserScore.user_id == current_user.id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Brak wyników")

    return {
        "score": score.score,
        "correct": score.correct,
        "incorrect": score.incorrect,
        "time_spent": score.time_spent,
    }
