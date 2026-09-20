from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from database import engine, get_db

# Tự động tạo bảng books trong DB
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Library Service")

@app.get("/manage/health")
def health_check():
    return {"status": "OK"}

@app.post("/books/")
def create_book(title: str, author: str, isbn: str, db: Session = Depends(get_db)):
    db_book = models.Book(title=title, author=author, isbn=isbn)
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return {"id": db_book.id, "title": db_book.title, "author": db_book.author, "isbn": db_book.isbn}

@app.get("/books/")
def get_books(db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    return books