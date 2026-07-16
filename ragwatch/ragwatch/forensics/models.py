from pydantic import BaseModel
from typing import Optional

class Evidence(BaseModel):
    query: str
    retrieved_chunks: list[str]
    generated_answer: str
    expected_answer: Optional[str] = None
    judge_reasoning_retrieval: str
    judge_reasoning_generation: str

class Diagnosis(BaseModel):
    trace_id: str
    category: str
    confidence: float
    evidence: Evidence
