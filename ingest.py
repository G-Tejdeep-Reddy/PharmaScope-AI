import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .core import DATA, digest, write_jsonl, read_jsonl

SESSION=requests.Session()
SESSION.mount('https://', HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
def get(url,params=None):
    r=SESSION.get(url,params=params,timeout=60); r.raise_for_status(); return r

def fetch():
    stamp=datetime.now(timezone.utc).isoformat()
    folder=DATA/'raw'/stamp.replace(':','-'); folder.mkdir(parents=True)
    documents=[]; manifest=[]
    def add(kind,sid,title,url,raw,sections,date,drugs):
        raw_text=raw if isinstance(raw,str) else json.dumps(raw,ensure_ascii=False)
        h=digest(raw_text); filename=f'{kind}-{sid}-{h[:12]}.txt'
        (folder/filename).write_text(raw_text)
        doc={'document_id':f'{kind}:{sid}:{h[:12]}','source_id':sid,'source_type':kind,
             'title':title,'url':url,'retrieved_at':stamp,'source_date':date,
             'content_hash':h,'drugs':sorted(set(drugs)|{d for d in ('semaglutide','dulaglutide') if d in raw_text.lower()}),
             'trial_ids':sorted(set(re.findall(r'NCT\d{8}',raw_text))), 'sections':sections}
        documents.append(doc); manifest.append({**{k:v for k,v in doc.items() if k!='sections'},'raw_path':str((folder/filename).relative_to(DATA))})
    for drug,brand in [('semaglutide','Ozempic'),('dulaglutide','Trulicity')]:
        payload=get('https://clinicaltrials.gov/api/v2/studies',{'query.cond':'type 2 diabetes','query.intr':drug,'pageSize':6,'format':'json'}).json()
        studies=payload.get('studies',[])
        if drug=='semaglutide':
            # Verified head-to-head seed; broad search alone is not a curated corpus.
            studies=[get('https://clinicaltrials.gov/api/v2/studies/NCT02648204').json()]+studies
        for study in studies:
            p=study['protocolSection']; ident=p['identificationModule']; sid=ident['nctId']
            sections={name:json.dumps(value,ensure_ascii=False) for name,value in p.items()}
            # Keep registry results groups, units, denominators, and measurements together in raw JSON.
            if study.get('resultsSection'):
                for name,value in study['resultsSection'].items(): sections['POSTED_RESULTS_'+name]=json.dumps(value,ensure_ascii=False)
            date=p.get('statusModule',{}).get('lastUpdatePostDateStruct',{}).get('date')
            add('clinicaltrials',sid,ident.get('briefTitle',sid),f'https://clinicaltrials.gov/study/{sid}',study,sections,date,[d for d in ('semaglutide','dulaglutide') if d in json.dumps(study).lower()])
        label=get('https://api.fda.gov/drug/label.json',{'search':f'openfda.brand_name:"{brand}"','limit':3}).json()
        for row in label.get('results',[]):
            sections={key:'\n'.join(row[key]) for key in ['indications_and_usage','dosage_and_administration','boxed_warning','warnings_and_cautions','adverse_reactions','clinical_studies'] if row.get(key)}
            add('fda',row['id'],f'{brand} label',f'https://api.fda.gov/drug/label.json?search=id:%22{row["id"]}%22',row,sections,row.get('effective_time'),[drug])
        base='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
        time.sleep(.4)
        search=get(base+'esearch.fcgi',{'db':'pubmed','term':f'{drug}[Title/Abstract] AND type 2 diabetes[Title/Abstract] AND randomized controlled trial[Publication Type]','retmax':4,'retmode':'json'}).json()
        ids=search['esearchresult']['idlist']
        if drug=='semaglutide': ids=list(dict.fromkeys(['29397376']+ids))
        if ids:
            time.sleep(.4)
            xml=get(base+'efetch.fcgi',{'db':'pubmed','id':','.join(ids),'retmode':'xml'}).text
            for article in ET.fromstring(xml).findall('.//PubmedArticle'):
                sid=article.findtext('.//MedlineCitation/PMID'); title=''.join(article.find('.//ArticleTitle').itertext())
                sections={f'abstract_{i}_{part.get("Label", "text")}':''.join(part.itertext()) for i,part in enumerate(article.findall('.//Abstract/AbstractText'))}
                # Publication dates may be partial; preserve the original structure.
                date_node=article.find('.//JournalIssue/PubDate')
                date=ET.tostring(date_node,encoding='unicode') if date_node is not None else None
                add('pubmed',sid,title,f'https://pubmed.ncbi.nlm.nih.gov/{sid}/',ET.tostring(article,encoding='unicode'),sections,date,[drug])
    unique={r['document_id']:r for r in documents}
    write_jsonl(DATA/'candidates.jsonl',unique.values()); write_jsonl(folder/'manifest.jsonl',manifest)
    print(f'{len(unique)} candidates. Review data/candidates.jsonl; put approved document_ids in data/selected_ids.txt.')
def approve():
    ids={s.strip() for s in (DATA/'selected_ids.txt').read_text().splitlines() if s.strip() and not s.startswith('#')}
    candidates=read_jsonl(DATA/'candidates.jsonl'); known={r['document_id'] for r in candidates}
    if not ids or ids-known: raise ValueError('Selection empty or contains unknown IDs')
    write_jsonl(DATA/'processed/documents.jsonl',[r for r in candidates if r['document_id'] in ids])
    print(f'Approved {len(ids)} documents')
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['fetch','list','approve','index','curate']); args=parser.parse_args()
    if args.command=='fetch': fetch()
    elif args.command=='list':
        for row in read_jsonl(DATA/'candidates.jsonl'):
            print(f"{row['document_id']} | {row['title']}\n  {row['url']}")
    elif args.command=='approve': approve()
    else:
        from dotenv import load_dotenv
        from .core import ROOT,build_index,load_curated
        load_dotenv(ROOT/'.env')
        build_index() if args.command=='index' else load_curated()
