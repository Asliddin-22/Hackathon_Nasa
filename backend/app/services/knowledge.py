"""Reviewed local text ingestion and SQLite FTS5 retrieval. No network or LLM."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import select, text, delete, func
from ..config import ROOT
from ..models.knowledge import KnowledgeDocument, KnowledgeChunk

CORPUS = ROOT / 'medical_knowledge'
STOP = set('a an the how what why does do is are can i my me to of for and in on with about it this that your please explain tell have has had feel feeling could might would should be been am do does get getting need want know really after before also'.split())
ALIASES = {'cardiovascular':'heart', 'heartbeat':'heart', 'dizzy':'dizziness balance', 'renal':'kidney', 'skeletal':'bone', 'sans':'vision', 'microgravity':'gravity', 'hr':'heart rate'}

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def validate_document(doc):
    required = {'id','title','url','publisher','system','category','rights','sections','text_sha256','reviewed_on','version'}
    if not required <= doc.keys() or not doc['sections']:
        raise ValueError('Incomplete knowledge source')
    if doc['rights'].get('status') != 'reviewed_public_domain_text':
        raise ValueError('Source permissions have not been reviewed')
    for url in [doc['url'], doc['rights'].get('policy_url','')]:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not ((parsed.hostname or '').endswith(('.nih.gov','.nasa.gov')) or parsed.hostname == 'medlineplus.gov'):
            raise ValueError('Unapproved source or policy domain')
    if not doc['rights'].get('attribution') or not doc['rights'].get('reviewed_on'):
        raise ValueError('Attribution and rights review date required')
    if not re.fullmatch(r'[a-z0-9-]{1,80}',doc['id']):
        raise ValueError('Invalid source ID')
    for section in doc['sections']:
        if not isinstance(section.get('text'),str) or not section['text'].strip() or not section.get('heading'):
            raise ValueError('Empty source passage')
        if len(section['text']) > 12000:
            raise ValueError('Split long passages before ingestion')
    if digest(doc['sections']) != doc['text_sha256']:
        raise ValueError('Knowledge source checksum mismatch')

def initialize_fts(db):
    db.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, heading, passage, tokenize='porter unicode61')"))

def ingest_corpus(db, categories=('fundamentals','space_medicine')):
    # Validate the entire batch before making any changes.
    documents = []
    for category in categories:
        for path in sorted((CORPUS / category).glob('*.json')):
            doc = json.loads(path.read_text())
            validate_document(doc)
            documents.append(doc)
    if len({d['id'] for d in documents}) != len(documents):
        raise ValueError('Duplicate source IDs')
    initialize_fts(db)
    changed = 0
    for doc in documents:
        row = db.get(KnowledgeDocument, doc['id'])
        metadata = {k:v for k,v in doc.items() if k != 'sections'}
        fts_count=db.execute(text('SELECT count(*) FROM knowledge_fts WHERE document_id=:id'),{'id':doc['id']}).scalar()
        if row and row.metadata_hash == digest(doc) and fts_count==len(doc['sections']):
            continue
        if row:
            db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == row.id))
            db.execute(text('DELETE FROM knowledge_fts WHERE document_id=:id'),{'id':row.id})
        else:
            row=KnowledgeDocument(id=doc['id'])
            db.add(row)
        row.title,row.url,row.publisher,row.system,row.category = doc['title'],doc['url'],doc['publisher'],doc['system'],doc['category']
        row.content_hash,row.metadata_hash,row.provenance=doc['text_sha256'],digest(doc),metadata
        db.flush()
        for ordinal, section in enumerate(doc['sections']):
            chunk_id=f'{row.id}:{ordinal+1}'
            db.add(KnowledgeChunk(id=chunk_id, document_id=row.id, heading=section['heading'],text=section['text'],ordinal=ordinal))
            db.execute(text('INSERT INTO knowledge_fts(chunk_id,document_id,heading,passage) VALUES (:id,:doc,:heading,:passage)'),{'id':chunk_id,'doc':row.id,'heading':section['heading'],'passage':section['text']})
        changed += 1
    db.flush()
    return {'indexed_documents':db.scalar(select(func.count()).select_from(KnowledgeDocument)), 'indexed_chunks':db.scalar(select(func.count()).select_from(KnowledgeChunk)), 'changed_documents':changed}

def retrieve(db, question, limit=4, category=None):
    tokens=re.findall(r'[a-z0-9]+',question.lower())[:80]
    terms=[]
    for token in tokens:
        if token not in STOP:
            terms.extend((token+' '+ALIASES.get(token,'')).split())
    terms=list(dict.fromkeys(terms))[:40]
    if not terms:
        return []
    # Only quoted alphanumeric terms reach FTS; SQL and FTS operators from the
    # user are never executed. BM25 is a relevance ranking, not clinical confidence.
    query=' OR '.join('"'+t+'"' for t in terms)
    sql='''SELECT chunk_id, bm25(knowledge_fts,0,0,2,1) AS score FROM knowledge_fts
           JOIN knowledge_documents d ON d.id=knowledge_fts.document_id
           WHERE knowledge_fts MATCH :query'''
    if category:
        sql+=' AND d.category=:category'
    sql+=' ORDER BY score,chunk_id LIMIT :limit'
    rows=db.execute(text(sql),{'query':query,'limit':max(1,min(limit,8)),'category':category}).all()
    results=[]
    for rank, (chunk_id,score) in enumerate(rows,1):
        chunk=db.get(KnowledgeChunk,chunk_id)
        doc=db.get(KnowledgeDocument,chunk.document_id)
        results.append({'chunk_id':chunk.id,'heading':chunk.heading,'text':chunk.text,'rank':rank,
                        'citation':{'source_id':doc.id,'title':doc.title,'url':doc.url,'publisher':doc.publisher,
                                    'category':doc.category,'system':doc.system,'source_updated':doc.provenance.get('source_updated'),
                                    'reviewed_on':doc.provenance['reviewed_on'],'version':doc.provenance['version'],
                                    'text_sha256':doc.content_hash,'attribution':doc.provenance['rights']['attribution'],
                                    'scope':doc.provenance.get('scope')}})
    return results


def retrieve_balanced(db,question):
    """Keep the small evidence packet diverse across source documents."""
    selected=[]
    for category,limit in [('fundamentals',4),('space_medicine',3)]:
        hits=retrieve(db,question,8,category=category)
        chosen=[]
        seen=set()
        for hit in hits:
            source=hit['citation']['source_id']
            if source not in seen:
                chosen.append(hit);seen.add(source)
            if len(chosen)==limit:break
        for hit in hits:
            if len(chosen)>=limit:break
            if hit not in chosen:chosen.append(hit)
        selected.extend(chosen)
    return selected
