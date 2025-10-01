from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class City(Base):
    __tablename__ = 'cities'
    city_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    state = Column(String(100))
    region = Column(String(100))   # e.g., South India, North India
    description = Column(Text)

class Site(Base):
    __tablename__ = 'sites'
    site_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    city_id = Column(Integer, ForeignKey("cities.city_id"), nullable=False)
    category = Column(String(50))   # e.g., Palace, Temple, Lake
    description = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    opening_hours = Column(String(100))
    ticket_price = Column(Float)
    best_time_to_visit = Column(String(100))
    image_url = Column(String(250))

# Setup DB connection
engine = create_engine("sqlite:///travel.db")
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()