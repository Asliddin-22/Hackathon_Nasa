from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database.db import get_db
from ..services.auth import current_user
from ..services.knowledge import retrieve

router=APIRouter(prefix='/api/knowledge',tags=['Knowledge'])
class SearchRequest(BaseModel):
    question: str=Field(min_length=3,max_length=1500)
    limit: int=Field(default=4,ge=1,le=8)

@router.post('/search')
def search(data:SearchRequest,user=Depends(current_user),db:Session=Depends(get_db)):
    results=retrieve(db,data.question,data.limit)
    return {'question':data.question,'status':'references_found' if results else 'no_coverage',
            'results':results,'limitation':'Reference retrieval only. Relevance does not establish a diagnosis or clinical suitability.'}

@router.post('/answer')
def reference_answer(data:SearchRequest,user=Depends(current_user),db:Session=Depends(get_db)):
    from ..services.rag import retrieve_evidence
    result=retrieve_evidence(db,data.question)
    return {**result,'question':data.question,'scope':'Reference evidence planning only; not a patient diagnosis.'}
