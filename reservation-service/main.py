from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import engine, get_db

# Tự động tạo bảng reservations trong DB
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Reservation Service")

@app.get("/manage/health")
def health_check():
    return {"status": "OK"}

@app.post("/reservations/")
def create_reservation(user_id: int, book_id: int, db: Session = Depends(get_db)):
    db_reservation = models.Reservation(user_id=user_id, book_id=book_id, status="active")
    db.add(db_reservation)
    db.commit()
    db.refresh(db_reservation)
    return {"id": db_reservation.id, "user_id": db_reservation.user_id, "book_id": db_reservation.book_id, "status": db_reservation.status}

@app.get("/reservations/")
def get_reservations(db: Session = Depends(get_db)):
    reservations = db.query(models.Reservation).all()
    return reservations