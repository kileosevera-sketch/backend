from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TopFailureCause(BaseModel):
    cause: str
    occurrences: int


class TrendPoint(BaseModel):
    date: str
    count: int


class ManagementTrend(BaseModel):
    trend: List[TrendPoint]


class PredictionItem(BaseModel):
    symptom: str
    predicted_cause: str
    probability: float
    evidence_summary: str


class EngineeringPredictions(BaseModel):
    predictions: List[PredictionItem]


class SeverityCount(BaseModel):
    severity: str
    count: int


class SentimentCount(BaseModel):
    sentiment: str
    count: int


class AlertItem(BaseModel):
    type: str
    product_id: Optional[int] = None
    message: str
    severity: str


class QASummary(BaseModel):
    complaints_by_severity: List[SeverityCount]
    complaints_by_sentiment: List[SentimentCount]
    active_alerts: List[AlertItem]


class ComplaintItem(BaseModel):
    id: int
    description: str
    status: str
    channel: Optional[str] = None
    created_at: datetime
    sentiment: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    symptoms: Optional[str] = None


class CustomerServiceComplaints(BaseModel):
    complaints: List[ComplaintItem]


class ManagementSummary(BaseModel):
    total_complaints: int
    total_failures: int
    total_warranty_cost: float
    active_alerts: int
    top_failure_causes: List[TopFailureCause]