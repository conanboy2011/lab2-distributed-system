from sqlalchemy import Column, Integer, String
from database import Base

class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    book_id = Column(Integer, nullable=False)
    status = Column(String, default="active", nullable=False) # active, returned, cancelled