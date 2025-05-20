import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database

load_dotenv()

app = FastAPI()

# PostgreSQL connection URL (from environment variables)
DATABASE_URL = os.getenv("POSTGRES_URL")

# SQLAlchemy setup
Base = declarative_base()

class PlateDB(Base):
    __tablename__ = "number_plates"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String)
    time = Column(String)
    track_id = Column(Integer)
    class_name = Column(String)
    numberplate = Column(String)
    timestamp = Column(DateTime)

# Database interface
database = Database(DATABASE_URL)

# Pydantic model
class PlateModel(BaseModel):
    id: Optional[int] = Field(default=None)
    date: str
    time: str
    track_id: int
    class_name: str
    numberplate: str
    timestamp: datetime

    class Config:
        orm_mode = True

# Startup/shutdown events
@app.on_event("startup")
async def startup():
    await database.connect()
    # Create tables if they don't exist
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# API Endpoints
@app.get("/plates", response_model=List[PlateModel])
async def get_plates(limit: int = 100):
    query = "SELECT * FROM number_plates ORDER BY timestamp DESC LIMIT :limit"
    return await database.fetch_all(query=query, values={"limit": limit})

@app.get("/plates/{track_id}", response_model=List[PlateModel])
async def get_plate_by_track_id(track_id: int):
    query = "SELECT * FROM number_plates WHERE track_id = :track_id ORDER BY timestamp DESC"
    plates = await database.fetch_all(query=query, values={"track_id": track_id})
    if not plates:
        raise HTTPException(status_code=404, detail=f"No plates found with track_id {track_id}")
    return plates