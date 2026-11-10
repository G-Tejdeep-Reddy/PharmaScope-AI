import pytest
from app.core import chunks
from app.main import Synthesis
from pydantic import ValidationError

def test_chunk_identity_changes_with_source_version():
    doc={'document_id':'a:v1','sections':{'results':'reported outcome with units'}}
    before=list(chunks(doc)); after=list(chunks({**doc,'document_id':'a:v2'}))
    assert before[0]['chunk_id']!=after[0]['chunk_id']
    assert before[0]['text']=='reported outcome with units'

def test_uncited_claim_is_invalid():
    with pytest.raises(ValidationError):
        Synthesis.model_validate({'claims':[{'text':'unsupported','citation_ids':[]}], 'limitations':[],'insufficient_evidence':False})

def test_empty_filter_returns_no_sources():
    from app.core import Retriever
    r=Retriever.__new__(Retriever); r.rows=[{'drugs':['semaglutide'],'source_type':'pubmed'}]
    assert r.search('question',drug='dulaglutide')==[]

def test_recall_and_rank():
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('evaluation',Path(__file__).resolve().parents[1]/'evaluation/evaluate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.metrics(['irrelevant','right'],{'right','missing'})=={'recall_at_6':.5,'mrr_at_6':.5}

def test_api_rejects_unknown_citations(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    class FakeRetriever:
        rows=[{'chunk_id':'p1','drugs':['semaglutide'],'source_type':'pubmed','text':'A source passage'}]
        def search(self,*a,**kw): return self.rows.copy()
    monkeypatch.setattr(main,'retriever',lambda:FakeRetriever())
    monkeypatch.setattr(main,'outcomes',lambda:[])
    for key in ['LLM_URL','LLM_API_KEY','LLM_MODEL']: monkeypatch.setenv(key,'test')
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':'{"claims":[{"text":"Bad citation","citation_ids":["S999"]}],"limitations":[],"insufficient_evidence":false}'}}]}
    monkeypatch.setattr(main.requests,'post',lambda *a,**kw:Response())
    response=TestClient(main.app).post('/ask',json={'question':'A valid research question','generate':True})
    assert response.status_code==502

def test_api_curated_rows_include_supporting_passages(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    class FakeRetriever:
        rows=[{'chunk_id':'curated','drugs':['semaglutide'],'source_type':'pubmed','text':'Evidence'}]
        def search(self,*a,**kw): return []
    monkeypatch.setattr(main,'retriever',lambda:FakeRetriever())
    monkeypatch.setattr(main,'outcomes',lambda:[{'drug':'semaglutide','source_passage_id':'curated','validated':True}])
    client=TestClient(main.app)
    response=client.post('/ask',json={'question':'Show stored evidence','drug':'semaglutide','generate':False}).json()
    assert response['structured_evidence'][0]['citation_id']=='S1'
    assert response['sources'][0]['chunk_id']=='curated'
    response=client.post('/ask',json={'question':'Show stored evidence','drug':'dulaglutide','generate':False}).json()
    assert response['sources']==[]

def test_generation_is_default_and_returns_cited_claim(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    assert main.Question(question='An evidence question').generate is True
    class FakeRetriever:
        rows=[{'chunk_id':'p1','drugs':['semaglutide'],'source_type':'pubmed','text':'Synthetic test passage'}]
        def search(self,*a,**kw): return self.rows.copy()
    monkeypatch.setattr(main,'retriever',lambda:FakeRetriever())
    monkeypatch.setattr(main,'outcomes',lambda:[])
    for key in ['LLM_URL','LLM_API_KEY','LLM_MODEL']: monkeypatch.setenv(key,'test')
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices':[{'message':{'content':'{"claims":[{"text":"Synthetic test claim","citation_ids":["S1"]}],"limitations":[],"insufficient_evidence":false}'}}]}
    monkeypatch.setattr(main.requests,'post',lambda *a,**kw:Response())
    response=TestClient(main.app).post('/ask',json={'question':'An evidence question'})
    assert response.status_code==200
    assert response.json()['mode']=='generated_unreviewed'
    assert response.json()['answer']['claims'][0]['citation_ids']==['S1']
