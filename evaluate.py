"""Run from repository root: PYTHONPATH=backend python evaluation/evaluate.py evaluation/test.jsonl"""
import json
import sys
from pathlib import Path
import numpy as np
from app.core import Retriever, read_jsonl

def metrics(ranking,gold):
    if not gold: raise ValueError('Answerable retrieval questions need gold passage IDs')
    hits=[int(x in gold) for x in ranking]
    return {'recall_at_6':len(set(ranking)&gold)/len(gold),
            'mrr_at_6':next((1/(i+1) for i,h in enumerate(hits) if h),0)}
def main():
    questions=read_jsonl(sys.argv[1]); r=Retriever(); report=[]
    if not questions: raise ValueError('Benchmark is empty; annotate real questions first')
    known={x['chunk_id'] for x in r.rows}
    for q in questions:
        if not q['answerable']: continue  # Abstention must be scored separately on generated answers.
        gold=set(q['gold_evidence_ids'])
        if not gold<=known: raise ValueError('Stale benchmark IDs; corpus/index changed')
        for mode in ['bm25','dense','hybrid']:
            found=r.search(q['question'],mode,q.get('drug'),q.get('source'))
            report.append({'question_id':q['question_id'],'group_id':q['group_id'],'mode':mode,
                           **metrics([x['chunk_id'] for x in found],gold)})
    if not report: raise ValueError('No answerable questions')
    print(json.dumps(report,indent=2))
    Path('evaluation/retrieval_results.json').write_text(json.dumps(report,indent=2))
    # Paired cluster bootstrap: resample trial/topic groups, keeping questions together.
    groups=sorted({x['group_id'] for x in report}); rng=np.random.default_rng(42)
    paired=[]
    for group in groups:
        m={mode:np.mean([x['recall_at_6'] for x in report if x['mode']==mode and x['group_id']==group]) for mode in ['bm25','dense','hybrid']}
        paired.append(m['hybrid']-m['dense'])
    if len(groups)>=2:
        boot=[np.mean(rng.choice(paired,len(paired),replace=True)) for _ in range(2000)]
        print('Hybrid minus dense: mean group recall difference, 95% percentile CI:',float(np.mean(paired)),np.quantile(boot,[.025,.975]).tolist())
    else: print('Need multiple independent groups for a meaningful grouped confidence interval.')
if __name__=='__main__': main()
