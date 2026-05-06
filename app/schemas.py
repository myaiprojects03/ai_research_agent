from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class ResearchRequest(BaseModel):
    topic: str
    email_recipient: Optional[str] = None

class ReportResponse(BaseModel):
    id: int
    topic: str
    content: str
    created_at: datetime
    email_sent: bool

    class Config:
        from_attributes = True