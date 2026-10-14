from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.client import close_client, get_db
from app.db.indexes import create_indexes
from app.routers import admin, analytics, attendance, employees, health

@asynccontextmanager
async def lifespan(app):
    db = get_db()
    create_indexes(db)
    yield
    close_client()


app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(analytics.router)
app.include_router(admin.router)
