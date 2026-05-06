from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db, init_db
from app.models import Report
from app.schemas import ResearchRequest, ReportResponse
from app.agent import run_research
from app.email_service import send_report_email
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI(title="AI Research Agent", version="1.0.0")

@app.on_event("startup")
async def startup():
    init_db()
    print("Database initialized.")

@app.get("/")
def root():
    return {"status": "AI Research Agent is running", "version": "1.0.0"}

@app.post("/research", response_model=ReportResponse)
def create_research_report(request: ResearchRequest, db: Session = Depends(get_db)):
    """Accept a topic, run the AI research agent, save to DB, and email the report."""
    try:
        print(f"Starting research for: {request.topic}")
        
        # 1. Run the LangChain + Groq research pipeline
        report_content = run_research(request.topic)
        
        # 2. Save to PostgreSQL
        recipient = request.email_recipient or os.getenv("EMAIL_RECIPIENT")
        db_report = Report(
            topic=request.topic,
            content=report_content,
            email_recipient=recipient,
            email_sent=False
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
        
        # 3. Send email
        email_sent = send_report_email(request.topic, report_content, recipient)
        db_report.email_sent = email_sent
        db.commit()
        db.refresh(db_report)
        
        return db_report
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports", response_model=List[ReportResponse])
def get_all_reports(db: Session = Depends(get_db)):
    return db.query(Report).order_by(Report.created_at.desc()).all()

@app.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report