import json
import pytest
from sqlalchemy import select,func
from backend.app.models.knowledge import KnowledgeDocument,KnowledgeChunk
from backend.app.services.knowledge import ingest_corpus,retrieve,validate_document,CORPUS

@pytest.fixture
def indexed(client):
    with client.sessions() as db:
        report=ingest_corpus(db)
        db.commit()
    return report

def test_ingestion_idempotent_and_cardiovascular_citations(client,indexed):
    assert indexed['indexed_documents']==15
    with client.sessions() as db:
        assert ingest_corpus(db)['changed_documents']==0
        results=retrieve(db,'What controls the rate and rhythm of the heartbeat?')
        assert results
        assert results[0]['citation']['publisher']=='NHLBI / NIH'
        assert 'rate and rhythm' in results[0]['text']
        for result in results:
            row=db.get(KnowledgeChunk,result['chunk_id'])
            assert result['text']==row.text
            assert result['citation']['url'].startswith('https://')
            assert len(result['citation']['text_sha256'])==64

def test_all_six_systems_present(client,indexed):
    with client.sessions() as db:
        assert set(db.scalars(select(KnowledgeDocument.system).where(KnowledgeDocument.category=='fundamentals')))=={'cardiovascular','muscle','bone','balance','kidney','vision','emergency_support'}
        assert retrieve(db,'kidney filtration nephrons')[0]['citation']['source_id']=='niddk-kidneys'
        assert retrieve(db,'retina optic nerve')[0]['citation']['source_id']=='nei-eyes'
        assert retrieve(db,'quasar axolotl')==[]

def test_permissions_and_checksum_are_required():
    doc=json.loads((CORPUS/'fundamentals'/'nhlbi-heart.json').read_text())
    doc['sections'][0]['text']='tampered'
    with pytest.raises(ValueError,match='checksum'):validate_document(doc)
    doc['rights']['status']='unreviewed'
    with pytest.raises(ValueError,match='permissions'):validate_document(doc)

def test_real_search_api_authorization_and_fts_input(client,indexed,astronaut,doctor):
    body={'question':'How does the cardiac conduction system control heart rhythm?'}
    assert client.post('/api/knowledge/search',json=body).status_code==401
    for headers in [astronaut,doctor]:
        response=client.post('/api/knowledge/search',headers=headers,json=body)
        assert response.status_code==200
        assert response.json()['status']=='references_found'
    for question in ['" OR ) MATCH --','the and how','unknownzzxyz']:
        response=client.post('/api/knowledge/search',headers=astronaut,json={'question':question})
        assert response.status_code==200
    assert client.post('/api/knowledge/search',headers=astronaut,json={'question':'a'}).status_code==422


def test_nasa_sources_are_separate_and_cited(client,indexed):
    with client.sessions() as db:
        hits=retrieve(db,'SANS optic nerve swelling',category='space_medicine')
        assert hits and all(r['citation']['publisher']=='NASA' for r in hits)
        assert any(r['citation']['source_id']=='nasa-sans' for r in hits)
        assert 'not a clinical protocol' in hits[0]['citation']['scope']

def test_ingestion_repairs_missing_fts_rows_without_duplicate_sources(client,indexed):
    from sqlalchemy import text
    with client.sessions() as db:
        db.execute(text('DELETE FROM knowledge_fts'))
        assert retrieve(db,'heart rhythm')==[]
        assert ingest_corpus(db)['changed_documents']==15
        assert retrieve(db,'heart rhythm')
        assert db.scalar(select(func.count()).select_from(KnowledgeDocument))==15
