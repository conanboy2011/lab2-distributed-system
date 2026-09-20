from datetime import datetime
import os

import httpx
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from sqlalchemy.orm import Session

import models
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Reservation Service")

LIBRARY_SERVICE_URL = os.getenv(
    "LIBRARY_SERVICE_URL",
    "http://library-service:8060"
)

RATING_SERVICE_URL = os.getenv(
    "RATING_SERVICE_URL",
    "http://user-service:8050"
)


def format_date(value):
    return value.strftime("%Y-%m-%d")


def get_library_book(library_uid, book_uid):
    url = (
        f"{LIBRARY_SERVICE_URL}"
        f"/internal/libraries/{library_uid}/books/{book_uid}"
    )

    response = httpx.get(url, timeout=10)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Book or library not found"
        )

    return response.json()


def change_library_count(library_uid, book_uid, action, condition=None):
    url = (
        f"{LIBRARY_SERVICE_URL}"
        f"/internal/libraries/{library_uid}/books/{book_uid}/{action}"
    )

    data = {}

    if condition is not None:
        data["condition"] = condition

    response = httpx.post(url, json=data, timeout=10)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    return response.json()


def get_rating(username):
    response = httpx.get(
        f"{RATING_SERVICE_URL}/rating",
        headers={"X-User-Name": username},
        timeout=10
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Cannot get rating"
        )

    return response.json()


def change_rating(username, delta):
    response = httpx.post(
        f"{RATING_SERVICE_URL}/rating/change",
        json={
            "username": username,
            "delta": delta
        },
        timeout=10
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="Cannot change rating"
        )

    return response.json()


@app.get("/manage/health")
def health_check():
    return {"status": "OK"}


@app.get("/reservations")
def get_reservations(
    x_user_name: str = Header(...),
    db: Session = Depends(get_db)
):
    reservations = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.username == x_user_name,
            models.Reservation.status == "RENTED"
        )
        .all()
    )

    result = []

    for reservation in reservations:
        details = get_library_book(
            str(reservation.library_uid),
            str(reservation.book_uid)
        )

        result.append({
            "reservationUid": str(reservation.reservation_uid),
            "status": reservation.status,
            "startDate": format_date(reservation.start_date),
            "tillDate": format_date(reservation.till_date),
            "book": details["book"],
            "library": details["library"]
        })

    return result


@app.post("/reservations")
def create_reservation(
    data: dict,
    x_user_name: str = Header(...),
    db: Session = Depends(get_db)
):
    book_uid = data.get("bookUid")
    library_uid = data.get("libraryUid")
    till_date = data.get("tillDate")

    if not book_uid or not library_uid or not till_date:
        raise HTTPException(
            status_code=400,
            detail="Invalid request"
        )

    try:
        till_date_value = datetime.fromisoformat(till_date)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid tillDate"
        )

    rented_count = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.username == x_user_name,
            models.Reservation.status == "RENTED"
        )
        .count()
    )

    rating = get_rating(x_user_name)
    stars = rating["stars"]

    if rented_count >= stars:
        raise HTTPException(
            status_code=409,
            detail="Maximum number of rented books reached"
        )

    details = get_library_book(library_uid, book_uid)

    if details["availableCount"] <= 0:
        raise HTTPException(
            status_code=409,
            detail="Book is not available"
        )

    change_library_count(
        library_uid,
        book_uid,
        "borrow"
    )

    reservation = models.Reservation(
        username=x_user_name,
        book_uid=book_uid,
        library_uid=library_uid,
        status="RENTED",
        start_date=datetime.now(),
        till_date=till_date_value
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return {
        "reservationUid": str(reservation.reservation_uid),
        "status": reservation.status,
        "startDate": format_date(reservation.start_date),
        "tillDate": format_date(reservation.till_date),
        "book": details["book"],
        "library": details["library"],
        "rating": {
            "stars": stars
        }
    }


@app.post("/reservations/{reservation_uid}/return")
def return_book(
    reservation_uid: str,
    data: dict,
    x_user_name: str = Header(...),
    db: Session = Depends(get_db)
):
    reservation = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.reservation_uid == reservation_uid,
            models.Reservation.username == x_user_name,
            models.Reservation.status == "RENTED"
        )
        .first()
    )

    if not reservation:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found"
        )

    return_date = data.get("date")
    condition = data.get("condition")

    if not return_date or not condition:
        raise HTTPException(
            status_code=400,
            detail="Invalid request"
        )

    try:
        return_date_value = datetime.fromisoformat(return_date)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid date"
        )

    if condition not in ["EXCELLENT", "GOOD", "BAD"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid condition"
        )

    details = get_library_book(
        str(reservation.library_uid),
        str(reservation.book_uid)
    )

    original_condition = details["book"]["condition"]

    is_late = return_date_value > reservation.till_date
    condition_worsened = (
        ["EXCELLENT", "GOOD", "BAD"].index(condition)
        > ["EXCELLENT", "GOOD", "BAD"].index(original_condition)
    )

    if is_late:
        reservation.status = "EXPIRED"
    else:
        reservation.status = "RETURNED"

    change_library_count(
        str(reservation.library_uid),
        str(reservation.book_uid),
        "return",
        condition
    )

    if is_late or condition_worsened:
        change_rating(x_user_name, -10)
    else:
        change_rating(x_user_name, 1)

    db.commit()

    return Response(status_code=204)

