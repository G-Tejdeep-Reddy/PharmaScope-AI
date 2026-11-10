import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
type Source={citation_id:string;chunk_id:string;title:string;text:string;url:string;source_type:string;source_date:string|null;retrieved_at:string};
type Result={mode:string;latency_ms:number;answer:{claims:{text:string;citation_ids:string[]}[];limitations:string[];insufficient_evidence:boolean};sources:Source[]};
const API= 'http://127.0.0.1:8000';
function App(){
 const [question,setQuestion]=useState('What primary endpoints were measured in the indexed trials?');
 const [drug,setDrug]=useState(''); const [source,setSource]=useState(''); const [mode,setMode]=useState('hybrid');
 const [generate,setGenerate]=useState(true); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
 const [result,setResult]=useState<Result|null>(null); const [rows,setRows]=useState<Record<string,unknown>[]>([]);
 async function ask(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');setResult(null);
 try{const r=await fetch(API+'/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,drug:drug||null,source:source||null,mode,generate})});const data=await r.json();if(!r.ok)throw Error(data.detail||'Request failed');setResult(data);}catch(e){setError(String(e))}finally{setBusy(false)}}
 async function compare(){try{const r=await fetch(API+'/outcomes');if(!r.ok)throw Error('Could not load outcomes');setRows(await r.json());}catch(e){setError(String(e))}}
 return <main><header><small>PHARMA EVIDENCE INTELLIGENCE</small><h1>PharmaScope AI</h1><p>Competitive intelligence, grounded in evidence.</p></header>
 <p className="notice">Research prototype • Semaglutide and dulaglutide • Type 2 diabetes • No individual treatment recommendations</p>
 <form onSubmit={ask}><label htmlFor="q">Research question</label><textarea id="q" minLength={5} maxLength={2000} value={question} onChange={e=>setQuestion(e.target.value)} required/>
 <div className="controls"><label>Drug<select value={drug} onChange={e=>setDrug(e.target.value)}><option value="">Both</option><option>semaglutide</option><option>dulaglutide</option></select></label>
 <label>Source<select value={source} onChange={e=>setSource(e.target.value)}><option value="">All</option><option>clinicaltrials</option><option>pubmed</option><option>fda</option></select></label>
 <label>Retrieval<select value={mode} onChange={e=>setMode(e.target.value)}><option>hybrid</option><option>bm25</option><option>dense</option></select></label>
 <label><input type="checkbox" checked={generate} onChange={e=>setGenerate(e.target.checked)}/>Generate cited answer</label><button disabled={busy}>{busy?'Searching…':'Search evidence'}</button></div></form>
 {error&&<p role="alert">{error}</p>}
 {result&&<section><h2>{result.mode==='retrieval_only'?'Retrieved evidence':'Generated synthesis — verify against sources'}</h2><small>{result.latency_ms} ms</small>
 {result.answer.insufficient_evidence&&<p>Insufficient evidence in this response.</p>}
 {result.answer.claims.map((c,i)=><p key={i}>{c.text} {c.citation_ids.map(id=><a key={id} href={'#'+id}>[{id}] </a>)}</p>)}
 {result.answer.limitations.map((l,i)=><p className="notice" key={i}>{l}</p>)}
 {result.sources.map(s=><details key={s.citation_id} id={s.citation_id}><summary>[{s.citation_id}] {s.title} · {s.source_type}</summary><p>{s.text}</p><small>Source date: {s.source_date||'Unavailable'} · Retrieved: {s.retrieved_at}</small><p>Passage ID: <code>{s.chunk_id}</code></p><a href={s.url} target="_blank" rel="noreferrer">Original source ↗</a></details>)}</section>}
 <section><h2>Validated outcome evidence</h2><p>Rows preserve trial context. Different trials may not support direct comparison.</p><button onClick={compare}>Load curated evidence</button>{rows.length===0?<p>No rows loaded. Complete manual curation before numerical comparison.</p>:<div className="table"><table><thead><tr>{Object.keys(rows[0]).map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{Object.values(row).map((v,j)=><td key={j}>{String(v??'Missing')}</td>)}</tr>)}</tbody></table></div>}</section>
 <footer><a href="https://www.ncbi.nlm.nih.gov/About/disclaimer.html">NCBI disclaimer and copyright</a> · Abstracts may carry publisher copyright. Indexed records require relevance review.</footer></main>
}
createRoot(document.getElementById('root')!).render(<App/>);
