import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data'
def tokens(text):
    return re.findall(r'[a-z0-9]+', text.lower())
def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()
def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def write_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
def chunks(doc, size=180, overlap=30, tokenizer=None):
    # Use tokenizer offsets during indexing to avoid silent model truncation.
    # Numerical comparison uses curated rows; chunked prose is not a result database.
    for section, text in doc['sections'].items():
        spans = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False, verbose=False)['offset_mapping'] if tokenizer else [m.span() for m in re.finditer(r'\S+', text)]
        for start in range(0, len(spans), size-overlap):
            window=spans[start:start+size]
            passage = text[window[0][0]:window[-1][1]] if window else ''
            if not passage: continue
            yield {**{k:v for k,v in doc.items() if k!='sections'},
                   'section':section, 'text':passage,
                   'chunk_id':digest(doc['document_id']+section+str(start)+passage)[:24]}
def build_index():
    from sentence_transformers import SentenceTransformer
    docs = read_jsonl(DATA/'processed/documents.jsonl')
    if not docs: raise ValueError('No documents. Run ingestion first.')
    model_name = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    model = SentenceTransformer(model_name)
    window=min(180,model.max_seq_length-8)
    rows = [c for d in docs for c in chunks(d,size=window,overlap=30,tokenizer=model.tokenizer)]
    if not rows: raise ValueError('No sections available to index')
    vectors = model.encode([r['text'] for r in rows], normalize_embeddings=True)
    path = DATA/'index'; path.mkdir(parents=True, exist_ok=True)
    write_jsonl(path/'chunks.jsonl', rows)
    np.save(path/'vectors.npy', vectors)
    (path/'meta.json').write_text(json.dumps({'model':model_name,'count':len(rows),
        'corpus_hash':digest(json.dumps(rows, sort_keys=True)), 'token_window':window,'overlap':30}))
    print(f'Indexed {len(rows)} passages. Inspect chunks.jsonl before evaluation.')

class Retriever:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.rows=read_jsonl(DATA/'index/chunks.jsonl')
        self.vectors=np.load(DATA/'index/vectors.npy')
        meta=json.loads((DATA/'index/meta.json').read_text())
        self.model=SentenceTransformer(meta['model'])
    def search(self, question, mode='hybrid', drug=None, source=None, k=6):
        ids=[i for i,r in enumerate(self.rows) if (not drug or drug in r['drugs']) and (not source or source==r['source_type'])]
        if not ids: return []
        q=tokens(question)
        bm=BM25Okapi([tokens(self.rows[i]['text']) for i in ids]).get_scores(q)
        sparse=[ids[i] for i in np.argsort(-bm) if bm[i]>0][:30]
        dense=[]
        if mode!='bm25':
            v=self.model.encode([question],normalize_embeddings=True)[0]
            scores=self.vectors[ids]@v
            dense=[ids[i] for i in np.argsort(-scores)[:30]]
        if mode=='bm25': ranked=sparse
        elif mode=='dense': ranked=dense
        else:
            fused={}
            for ranking in (sparse,dense):
                for rank,i in enumerate(ranking,1): fused[i]=fused.get(i,0)+1/(60+rank)
            ranked=sorted(fused,key=lambda i:(-fused[i],i))
        return [self.rows[i] for i in ranked[:k]]

def load_curated():
    # Every imported row must explicitly attest manual validation and reference an indexed passage.
    available={r['chunk_id'] for r in read_jsonl(DATA/'index/chunks.jsonl')}
    path=DATA/'curated/outcomes.jsonl'
    rows=read_jsonl(path) if path.exists() else []
    required={'trial_id','drug','arm','population','endpoint','time_point','value','units','measure_type','source_passage_id','validated'}
    for row in rows:
        if not required<=row.keys() or row['validated'] is not True: raise ValueError('Incomplete or unvalidated evidence row')
        if row['source_passage_id'] not in available: raise ValueError('Unknown source passage')
    DATA.mkdir(exist_ok=True)
    with sqlite3.connect(DATA/'evidence.db') as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS outcomes (payload TEXT NOT NULL)')
        conn.execute('DELETE FROM outcomes')
        conn.executemany('INSERT INTO outcomes VALUES (?)',[(json.dumps(r),) for r in rows])
    print(f'Imported {len(rows)} validated outcomes')
def outcomes():
    db=DATA/'evidence.db'
    if not db.exists(): return []
    with sqlite3.connect(db) as conn: return [json.loads(x[0]) for x in conn.execute('SELECT payload FROM outcomes')]
