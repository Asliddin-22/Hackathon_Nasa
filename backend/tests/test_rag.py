import io,json
import pytest
from backend.app.services.knowledge import ingest_corpus
from backend.app.services import meta_model

@pytest.fixture
def corpus(client):
    with client.sessions() as db:ingest_corpus(db);db.commit()

def test_grounded_muse_request_and_response(client,corpus,astronaut,monkeypatch):
    monkeypatch.setattr('backend.app.services.rag.llm_enabled',lambda:True)
    monkeypatch.setattr(meta_model,'get_api_key',lambda:'mock-rag-key')
    def provider(request,**kwargs):
        payload=json.loads(request.data)
        data=json.loads(payload['input'][1]['content'][0]['text'])
        assert data['references'] and data['context']['question']
        assert len(data['references'])<=7
        assert payload['model']=='muse-wonder-1.0'
        selected={'focus':[data['references'][0]['chunk_id']],'explanations':[],'questions':[]}
        return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(selected)}]}]}).encode())
    monkeypatch.setattr(meta_model,'open_response',provider)
    r=client.post('/api/knowledge/answer',headers=astronaut,json={'question':'What controls heart rhythm?'})
    assert r.status_code==200 and r.json()['mode']=='muse_wonder_grounded'
    assert r.json()['plan']['focus'][0] in {x['chunk_id'] for x in r.json()['references']}

def test_invalid_citation_and_provider_failure_fall_back(client,corpus,astronaut,monkeypatch):
    monkeypatch.setattr('backend.app.services.rag.llm_enabled',lambda:True)
    monkeypatch.setattr(meta_model,'get_api_key',lambda:'mock-rag-key')
    def bad(request,**kwargs):
        return io.BytesIO(b'{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"{\\"focus\\":[\\"invented\\"],\\"explanations\\":[],\\"questions\\":[]}"}]}]}')
    monkeypatch.setattr(meta_model,'open_response',bad)
    r=client.post('/api/knowledge/answer',headers=astronaut,json={'question':'heart rhythm'})
    assert r.json()['mode']=='offline_provider_fallback'
    assert 'invented' not in r.text
    def fail(*args,**kwargs):raise TimeoutError()
    monkeypatch.setattr(meta_model,'open_response',fail)
    assert client.post('/api/knowledge/answer',headers=astronaut,json={'question':'heart rhythm'}).json()['references']

def test_no_coverage_does_not_call_model(client,corpus,astronaut,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('No model call for absent evidence')
    monkeypatch.setattr(meta_model,'request_grounded_plan',forbidden)
    result=client.post('/api/knowledge/answer',headers=astronaut,json={'question':'spaceship rocket fuel'}).json()
    assert result['coverage']=='no_coverage' and result['references']==[]
