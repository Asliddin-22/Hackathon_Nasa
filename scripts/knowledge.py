#!/usr/bin/env python3
"""Offline ingestion/search of reviewed source snapshots. Never uses API keys."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.database.db import Base,engine,SessionLocal
from backend.app.models import records,knowledge
from backend.app.services.knowledge import ingest_corpus,retrieve

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question',nargs='?',default='What controls the rate and rhythm of the heartbeat?')
    args=parser.parse_args()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        report=ingest_corpus(db)
        db.commit()
        print(json.dumps({'ingestion':report,'results':retrieve(db,args.question)},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
