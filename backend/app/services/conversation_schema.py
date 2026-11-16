"""Conversational contracts: free prose, verified provenance, no disease catalog."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class ContextPlan(StrictModel):
    intent: Literal['general_education','space_education','personal_assessment','clarification']
    uses_patient_records: bool
    metrics: list[str]
    include_history: bool
    include_symptoms: bool
    test_types: list[str]
    include_mission: bool
    use_conversation_history: bool
    retrieval_queries: list[str]
    symptom_scope: Literal['current','educational','unclear']

class Claim(StrictModel):
    text: str=Field(min_length=1,max_length=5000)
    basis: Literal['retrieved_evidence','general_model_knowledge','clinical_inference']
    citation_ids: list[str]
    fact_ids: list[str]

class ExplanationBlock(Claim):
    id: str=Field(min_length=1,max_length=80)

class Possibility(Claim):
    title: str=Field(min_length=1,max_length=240)

class GeneratedAnswer(StrictModel):
    blocks: list[ExplanationBlock]=Field(min_length=1,max_length=12)
    short_answer_ids: list[str]=Field(min_length=1,max_length=4)
    possible_explanations: list[Possibility]=Field(max_length=4)
    follow_up_questions: list[str]=Field(max_length=5)
    recommendations: list[Claim]=Field(max_length=5)
    uncertainties: list[str]=Field(max_length=8)
    needs_medical_review: bool
    needs_urgent_attention: bool

class AnswerAudit(StrictModel):
    acceptable: bool
    issues: list[Literal['unsupported_patient_claim','unsupported_source_claim','invented_citation',
                         'definitive_diagnosis','unapproved_treatment','inconsistent_answer',
                         'wrong_question_scope','missing_uncertainty','prompt_injection']]


def validate_provenance(answer:GeneratedAnswer,references,facts,educational):
    """Verify identifiers and evidence labels; semantics are audited separately."""
    citations={r['chunk_id'] for r in references}
    ids=[b.id for b in answer.blocks]
    if len(set(ids))!=len(ids) or not set(answer.short_answer_ids)<=set(ids):
        raise ValueError('Invalid summary block references')
    for claim in [*answer.blocks,*answer.possible_explanations,*answer.recommendations]:
        if not set(claim.citation_ids)<=citations or not set(claim.fact_ids)<=set(facts):
            raise ValueError('Unknown evidence identifier')
        if claim.basis=='retrieved_evidence' and not claim.citation_ids:
            raise ValueError('Cited claim has no reference')
        if claim.basis=='general_model_knowledge' and claim.citation_ids:
            raise ValueError('General knowledge cannot masquerade as cited evidence')
        if educational and claim.fact_ids:
            raise ValueError('Educational answer contains patient facts')
    return answer
