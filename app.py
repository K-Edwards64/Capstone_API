import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine
from databases import Database
import asyncpg

# --- Models must be defined first ---
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

# --- Application Setup ---
app = FastAPI()

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