from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import engine, get_db

# Tự động tạo bảng trong DB nếu chưa có
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="User Service")

@app.get("/manage/health")
def health_check():
    return {"status": "OK"}

@app.post("/users/")
def create_user(username: str, email: str, db: Session = Depends(get_db)):
    db_user = models.User(username=username, email=email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "email": db_user.email}

@app.get("/users/")
def get_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return users