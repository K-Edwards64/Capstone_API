import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer,String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from databases import Database
import asyncpg
from sqlalchemy import DateTime
from sqlalchemy.sql import func

load_dotenv()

# SQLAlchemy base and model
Base = declarative_base()

class PlateDB(Base):
    __tablename__ = "number_plates"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String)
    time = Column(String)
    track_id = Column(Integer)
    class_name = Column(String)
    numberplate = Column(String)
    #timestamp = Column(DateTime(timezone=True), server_default=func.now())
"""
class AuthorizedPlateDB(Base):
    __tablename__ = "authorized_plates"
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True)
    owner_name = Column(String, nullable=True)  #optional
    created_at = Column(DateTime(timezone=True), server_default=func.now())
"""
class AuthorizedPlateDB(Base):
    __tablename__ = "authorized_plates"
    plate_number = Column(String, primary_key=True)  # Changed to primary key
    owner_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

# --- Models must be defined first ---
class PlateModel(BaseModel):
    id: Optional[int] = Field(default=None)
    date: Optional[str]= None
    time: str
    track_id: int
    class_name: str
    numberplate: str
    #timestamp: datetime

    class Config:
        orm_mode = True

class PlateCreate(BaseModel):
    date: str
    time: str
    track_id: int
    class_name: str
    numberplate: str
    #timestamp: Optional[datetime] = None



#add new classes for authorized plate numbers
class AuthorizedPlateModel(BaseModel):
    #id: Optional[int] = Field(default=None)
    plate_number: str
    owner_name: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True

class AuthorizedPlateCreate(BaseModel):
    plate_number: str
    owner_name: Optional[str] = None

# --- Application Setup ---
app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_oracle_cloud_db_url():
    return (
        f"postgresql+asyncpg://"
        f"{os.getenv('DB_USER', 'oracle_user')}:"
        f"{os.getenv('DB_PASSWORD', 'oracle_password')}@"
        f"{os.getenv('DB_HOST', 'your.vm.public.ip')}:"
        f"{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'oracle_db')}"
    )

DATABASE_URL = get_oracle_cloud_db_url()
database = Database(DATABASE_URL)

# Create synchronous engine for table creation
sync_engine = create_engine(DATABASE_URL.replace("+asyncpg", ""))

def create_tables():
    """Create database tables if they don't exist"""
    Base.metadata.create_all(bind=sync_engine)

# --- Connection Handling ---
async def test_connection():
    try:
        conn = await asyncpg.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )
        await conn.close()
        return True
    except Exception as e:
        print(f"Oracle Cloud Connection Failed: {e}")
        return False

@app.on_event("startup")
async def startup():
    #creates table if not already in existence
    create_tables()

    if not await test_connection():
        raise RuntimeError("Failed to connect to Oracle Cloud PostgreSQL")
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# --- Routes ---
@app.get("/plates", response_model=List[PlateModel])
async def get_plates():
    query = "SELECT * FROM number_plates LIMIT 100"
    return await database.fetch_all(query)


@app.post("/plates", response_model=PlateModel, status_code=status.HTTP_201_CREATED)
async def create_plate(plate: PlateCreate):   

    """
    Create a new plate entry in the database.
    """

    query = """
    INSERT INTO number_plates (date, time, track_id, class_name, numberplate)
    VALUES (:date, :time, :track_id, :class_name, :numberplate)
    RETURNING id, date, time, track_id, class_name, numberplate
    """
    
    values = plate.model_dump()

    values = plate.dict()
    
    try:
        record = await database.fetch_one(query=query, values=values)
        return record
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating plate: {str(e)}"
        )
    
@app.delete("/number-plates", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_number_plates():
    """Delete all entries from the number_plates table"""
    try:
        await database.execute("TRUNCATE TABLE number_plates RESTART IDENTITY CASCADE")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing table: {str(e)}"
        )
    
#New endpoints for authorized plates
@app.post("/authorized-plates", response_model=AuthorizedPlateModel, status_code=status.HTTP_201_CREATED)
async def add_authorized_plate(plate: AuthorizedPlateCreate):
    """Add a new authorized plate"""
    query = """
    INSERT INTO authorized_plates (plate_number, owner_name)
    VALUES (:plate_number, :owner_name)
    RETURNING plate_number, owner_name, created_at
    """
    values = plate.model_dump()
    try:
        return await database.fetch_one(query, values)
    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Plate already exists")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.get("/authorized-plates", response_model=List[AuthorizedPlateModel])
async def get_authorized_plates():
    """List all authorized plates"""
    return await database.fetch_all("SELECT * FROM authorized_plates ORDER BY created_at DESC")

@app.delete("/authorized-plates", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_authorized_plates():
    """Delete all entries from the authorized_plates table"""
    try:
        await database.execute("TRUNCATE TABLE authorized_plates RESTART IDENTITY CASCADE")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing table: {str(e)}"
        )

#endpoint for determining authorized plates

@app.get("/matching-plates", response_model=List[PlateModel])
async def get_matching_plates():
    """
    Get all detected plates (PlateDB) that have matching authorized plates (AuthorizedPlateDB)
    Returns: List of PlateDB entries where numberplate exists in authorized_plates
    """
    query = """
    SELECT np.* 
    FROM number_plates np
    INNER JOIN authorized_plates ap ON np.numberplate = ap.plate_number
    ORDER BY np.date DESC, np.time DESC
    """
    
    try:
        matching_plates = await database.fetch_all(query)
        return matching_plates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching matching plates: {str(e)}"
        )