import { useEffect, useRef, useState } from 'react';
import { Activity, ArrowRight, Bot, CalendarDays, CheckCircle2, ChevronDown, Database, Gauge, HelpCircle, Menu, MessageSquareText, RefreshCw, ShieldCheck, Users, X } from 'lucide-react';
import type { AssistantRequest, AssistantResult, Chat, Forecast, Person, State } from './types';
import { Overview, ScheduleView } from './PlanningViews';
import { CrewWorkspace, RiskWorkspace } from './PeopleAndRisk';
import { AssistantView } from './AssistantView';
import { InsightsWorkspace } from './InsightsWorkspace';
import PublicReportsWorkspace from './public-reports/PublicReportsWorkspace';
import { formatDate, Metric, Modal, policies, type Scenario } from './ui';

const API=import.meta.env.VITE_API_URL ?? '/api';
function Brand({onClick}:{onClick:()=>void}){
  return <button className="brand brand-lockup" onClick={onClick} aria-label="PLiZ home">
    <span className="brand-art"><img className="brand-wordmark" src="/brand/pliz-wordmark.png" alt="PLiZ"/></span>
    <small>PLANNING, SIMPLIFIED.</small>
  </button>;
}
const initialChat:Chat[]=[{role:'assistant',text:'Hi! I can explain the schedule, add crew, update availability, create maintenance jobs, and rebuild the plan. Ask for a closure or absence preview, then say “Apply this plan” when you want to save it. What would you like done?'}];
async function api<T>(path:string,body?:unknown,method='POST'):Promise<T>{
  const response=await fetch(API+path,body===undefined?undefined:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!response.ok){const err=await response.json().catch(()=>({detail:response.statusText}));throw new Error(typeof err.detail==='string'?err.detail:'Check the form values and try again.');}
  return response.json();
}
const navigation=[
  {id:'Overview',label:'Overview',icon:Gauge},
  {id:'Schedule',label:'Schedule',icon:CalendarDays},
  {id:'Crew roster',label:'Your crew',icon:Users},
  {id:'Risk forecast',label:'Test a change',icon:Activity},
  {id:'Assistant',label:'AI assistant',icon:Bot},
  {id:'Checks & data',label:'Insights & checks',icon:ShieldCheck},
  {id:'Public reports',label:"Public's report",icon:MessageSquareText},
];
const titles:Record<string,string>={'Overview':'Let’s plan a better night.','Schedule':'Schedule','Crew roster':'Your crew','Risk forecast':'Test a change','Assistant':'AI assistant','Checks & data':'Plan insights & checks','Public reports':"Public's report"};

export default function App(){
  const [data,setData]=useState<State|null>(null),[scenario,setScenario]=useState<Scenario>('A'),[view,setView]=useState('Overview');
  const [busy,setBusy]=useState('Loading your workspace'),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [forecast,setForecast]=useState<Forecast|null>(null),[week,setWeek]=useState(11),[duration,setDuration]=useState(1),[location,setLocation]=useState('SEC:BET:H01_H02:EB'),[absent,setAbsent]=useState<string[]>([]);
  const [capacity,setCapacity]=useState<number|null>(null),[noEclo,setNoEclo]=useState(false);
  const [scheduleQuery,setScheduleQuery]=useState(''),[prompt,setPrompt]=useState(''),[help,setHelp]=useState(false),[rebuildConfirm,setRebuildConfirm]=useState(false);
  const [chat,setChat]=useState<Chat[]>(initialChat);
  const [retryRequest,setRetryRequest]=useState<AssistantRequest|null>(null);
  const [mobileMenu,setMobileMenu]=useState(false);
  const [history,setHistory]=useState<{id:string;scenario:string;created_at:string;risk_band:string}[]>([]);
  const working=useRef(false);
  const absentKey=absent.join('|');
  useEffect(()=>setForecast(null),[week,duration,location,absentKey,capacity,noEclo]);
  useEffect(()=>{window.scrollTo({top:0});},[view]);
  useEffect(()=>{
    let active=true;setBusy('Loading your workspace');setNotice('');
    api<State>('/state?scenario='+scenario).then(next=>{if(active){setData(next);setForecast(null);setError('');}}).catch(e=>active&&setError(e.message)).finally(()=>active&&setBusy(''));
    return()=>{active=false;};
  },[scenario]);
  async function load(s=scenario){
    const next=await api<State>('/state?scenario='+s);setData(next);
    setAbsent(ids=>ids.filter(id=>next.people.some(p=>p.id===id)));
    setLocation(loc=>loc&&!next.instance.supply.hasOwnProperty(loc)?Object.keys(next.instance.supply)[0]:loc);
    return next;
  }
  async function action(label:string,fn:()=>Promise<void>){
    if(working.current)return false;
    working.current=true;setBusy(label);setError('');setNotice('');
    try{await fn();return true;}catch(e){setError(e instanceof Error?e.message:'The request failed. Please try again.');return false;}
    finally{working.current=false;setBusy('');}
  }
  function open(next:string,query=''){if(busy)return;setMobileMenu(false);setView(next);setScheduleQuery(query);setError('');if(next==='Risk forecast')void api<typeof history>('/runs').then(setHistory).catch(()=>setError('Could not load saved forecasts. You can still run a new preview.'));}
  async function rebuild(){setRebuildConfirm(false);await action('Rebuilding your plan',async()=>{await api('/plan',{scenario});await load();setForecast(null);setNotice('Your fresh plan is ready. Crew skills, leave and track constraints have been checked.');});}
  async function runRisk(){
    await action('Checking the change and replanning',async()=>{
      const result=await api<Forecast>('/risk',{scenario,closure_location:capacity===null?location||null:null,capacity_location:capacity!==null?location:null,capacity_nights:capacity,no_eclo:noEclo,week,duration,absent_ids:absent});setForecast(result);
      setHistory(await api('/runs'));
    });
  }
  async function apply(){
    if(!forecast)return;
    await action('Saving the updated plan',async()=>{
      await api('/runs/'+forecast.id+'/apply',{});const next=forecast.candidate.scenario as Scenario;
      const updated=await load(next);setScenario(next);setData(updated);setForecast(null);setView('Schedule');setScheduleQuery('week:'+String(forecast.candidate.options.week));
      setNotice('Updated plan saved. You’re viewing the first week affected by the change.');
    });
  }
  function clearChat(){
    if(busy||working.current)return;
    setChat(initialChat);setPrompt('');setForecast(null);setError('');setRetryRequest(null);
    setNotice('Chat cleared. Start a new conversation.');
  }
  async function sendAssistant(request:AssistantRequest){
    if(request.scenario!==scenario){setError('Switch to Scenario '+request.scenario+' before retrying that request.');return;}
    const ok=await action('Working on your request',async()=>{
      let result:AssistantResult;
      try{result=await api<AssistantResult>('/copilot',request);}
      catch(e){
        const saved=await api<{status:string;result:AssistantResult}>('/chat/'+request.request_id).catch(()=>null);
        if(saved?.status==='complete')result=saved.result;else throw e;
      }
      setRetryRequest(null);
      setChat(c=>[...c,{role:'assistant',text:result.response,model:result.model,request_id:result.request_id,receipt:result.receipt,action_error:result.action_error}]);
      if(result.forecast)setForecast(result.forecast);
      if(result.receipt){setForecast(null);setNotice(result.receipt.title);}
      if(result.ai_error)setError(result.ai_error);
      try{await load(request.scenario);}catch{setError('Your request finished, but the workspace could not refresh. Use Refresh workspace to see the saved result.');}
    });
    if(!ok)setRetryRequest(request);
  }
  async function ask(text=prompt){
    if(!text.trim()||busy||working.current)return;
    const request:AssistantRequest={message:text,scenario,history:chat.slice(-10),request_id:crypto.randomUUID(),forecast_id:forecast?.id,reply_to:[...chat].reverse().find(c=>c.role==='assistant')?.request_id};
    setChat(c=>[...c,{role:'user',text}]);setPrompt('');setRetryRequest(null);
    await sendAssistant(request);
  }
  async function savePerson(person:Person){return action('Saving crew changes',async()=>{await api('/people/'+person.id,person,'PUT');await load();setForecast(null);setNotice(person.name+' updated. The generated plan now uses their new availability and skills.');});}
  async function addPeople(names:string[],role:string){return action('Adding your crew',async()=>{await api('/people/bulk',{people:names.map(name=>({name,role,skills:'track;construction;consist',max_shifts:3}))});await load();setForecast(null);setNotice(names.length+' crew members added to your team.');});}
  const p=data?.plan,m=p?.metrics;
  return <div className="shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="mobile-topbar">
      <Brand onClick={()=>open('Overview')}/>
      <span className="mobile-connection"><i className={data?'status-dot':'status-dot pending'}/>{data?'Workspace ready':'Connecting'}</span>
    </div>
    <aside className="rail"><Brand onClick={()=>open('Overview')}/>
      <div className="workspace-tag"><span className="status-dot"/>NebulaX workspace<ChevronDown size={13}/></div>
      <span className="overline rail-caption">YOUR WORKSPACE</span>
      <nav aria-label="Main navigation">{navigation.map(({id,label,icon:Icon})=><button disabled={!!busy} aria-current={view===id?'page':undefined} className={view===id?'active':''} key={id} onClick={()=>open(id)}><Icon size={19}/><span>{label}</span>{id==='Crew roster'&&<small>{data?.people.length??'—'}</small>}{id==='Assistant'&&<span className="nav-ai">AI</span>}</button>)}</nav>
      <div className="rail-bottom"><button className="help-button" onClick={()=>setHelp(true)}><HelpCircle size={17}/>How to use PLiZ</button><div className="user-chip"><span className="avatar">OC</span><div><strong>Operations controller</strong><small>Demo workspace</small></div></div></div>
    </aside>
    <main id="main-content"><header><div><div className="breadcrumbs">Workspace <span>/</span> {navigation.find(n=>n.id===view)?.label}</div><h1>{titles[view]}</h1></div><div className="header-actions"><span className="connection"><i className={data?'status-dot':'status-dot pending'}/>{data?'Workspace connected':'Connecting'}</span><button className="icon" aria-label="Refresh workspace" disabled={!!busy} onClick={()=>void action('Refreshing workspace',async()=>{await load();setForecast(null);})}><RefreshCw size={17}/></button><button className="icon" aria-label="Help" onClick={()=>setHelp(true)}><HelpCircle size={18}/></button></div></header>
      {view!=='Public reports'&&<div className="plan-bar"><div><span className="plan-label">PLANNING APPROACH</span><label className="sr-only" htmlFor="scenario">Planning approach</label><select id="scenario" value={scenario} disabled={!!busy} onChange={e=>setScenario(e.target.value as Scenario)}>{Object.entries(policies).map(([s,policy])=><option key={s} value={s}>{s} · {policy.name}</option>)}</select><span className="policy-description">{policies[scenario].description}</span></div><button disabled={!!busy||!data} onClick={()=>p&&Object.keys(p.options).length?setRebuildConfirm(true):void rebuild()}><RefreshCw size={15}/>Rebuild plan</button></div>}
      {busy&&<div className="banner loading" role="status"><span className="spinner"/>{busy}…</div>}
      {error&&<div className="banner error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={17}/></button></div>}
      {notice&&<div className="banner success" role="status"><CheckCircle2 size={18}/><span>{notice}</span><button aria-label="Dismiss notification" onClick={()=>setNotice('')}><X size={17}/></button></div>}
      {view==='Public reports'?<PublicReportsWorkspace/>:data&&p&&m?<div className="page-content">
        {view==='Overview'&&<Overview data={data} open={open}/>}
        {view==='Schedule'&&<ScheduleView key={scenario+'-'+scheduleQuery} plan={p} people={data.people} start={data.instance.start} initialQuery={scheduleQuery} exportUrl={API+'/export?scenario='+scenario}/>}
        {view==='Crew roster'&&<CrewWorkspace key={scheduleQuery} initialQuery={scheduleQuery} people={data.people} plan={p} busy={!!busy} error={error} save={savePerson} add={addPeople}/>}
        {view==='Risk forecast'&&<>
          <RiskWorkspace data={data} week={week} duration={duration} location={location} absent={absent} capacity={capacity} noEclo={noEclo} setCapacity={setCapacity} setNoEclo={setNoEclo} busy={!!busy} forecast={forecast} setWeek={setWeek} setDuration={setDuration} setLocation={setLocation} setAbsent={setAbsent} run={()=>void runRisk()} apply={()=>void apply()} openSchedule={()=>open('Schedule')}/>
          <details className="panel history-panel"><summary>Previous previews <span className="count">{history.length}</span></summary><div className="history">{history.map(r=><button disabled={!!busy} key={r.id} onClick={()=>void action('Opening saved preview',async()=>{setForecast(await api('/runs/'+r.id));})}><strong>Scenario {r.scenario} · {r.risk_band} impact</strong><small>{new Date(r.created_at.endsWith('Z')?r.created_at:r.created_at+'Z').toLocaleString()}</small><ChevronRightIcon/></button>)}{!history.length&&<p className="muted">Your previews will appear here after the first simulation.</p>}</div></details>
        </>}
        {view==='Assistant'&&<AssistantView chat={chat} prompt={prompt} setPrompt={setPrompt} ask={text=>void ask(text)} clearChat={clearChat} busy={!!busy} data={data} forecast={forecast} openForecast={()=>open('Risk forecast')} openResult={(target,query,nextScenario)=>{if(nextScenario&&nextScenario!==scenario)setScenario(nextScenario as Scenario);open(target,query);}} retry={retryRequest?()=>void sendAssistant(retryRequest):undefined} test={()=>void action('Checking AI connection',async()=>{const result=await api<{message:string}>('/ai/test',{});await load();setNotice(result.message);})}/>}
    {view==='Checks & data'&&<InsightsWorkspace key={scheduleQuery} initialContract={scheduleQuery} data={data} apiBase={API} selectScenario={setScenario} open={open}><Metrics items={[[p.audit.violations.length,'Violations','Independent output audit'],[p.audit.checked_accesses,'Activity-nights checked','Including named crew'],[m.objective,'Objective penalty','Lower is better; meaningful for complete valid plans'],[m.remaining_workload,'Remaining work units','Must be zero to export']]}/><div className="two-col"><section className="panel"><Heading kicker="LOCAL VALIDATION" title={p.audit.passed?'All implemented checks passed':'Plan needs attention'}/>{p.audit.checks.map(check=><div className="check" key={check}><CheckCircle2 size={17}/>{check}</div>)}{p.audit.violations.map((v,i)=><p className="violation" key={i}><b>{v.rule}</b> — {v.detail}</p>)}<div className="note">These are PLiZ’s local checks. The organisers’ reference validator is not included, so this is not a claim of official validation.</div></section><section className="panel"><Heading kicker="DATA & ASSUMPTIONS" title={data.source}/><p>{data.instance.start} · {data.instance.horizon}-week input horizon · {p.activities.length} activities</p><p className="muted">{p.method}</p><ul>{p.assumptions.map(a=><li key={a}>{a}</li>)}</ul><a className="text-link" href="https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/blob/main/PS1/PS1_README.md" target="_blank" rel="noreferrer">Read the problem statement ↗</a><hr/><label>Load a new PS1 instance (all eight CSVs)<input type="file" accept=".csv" multiple disabled={!!busy} onChange={e=>{const files=Array.from(e.target.files??[]);if(!files.length)return;void action('Validating and loading instance',async()=>{const form=new FormData();files.forEach(f=>form.append('files',f));const response=await fetch(API+'/instance',{method:'POST',body:form});if(!response.ok){const result=await response.json();throw new Error(result.detail);}await load();setForecast(null);setNotice('Instance loaded and scheduled.');});e.target.value='';}}/></label><button disabled={!!busy} onClick={()=>void action('Restoring official instance',async()=>{await api('/instance/reset',{});await load();setForecast(null);setNotice('Official synthetic instance restored.');})}>Restore official instance</button></section></div></InsightsWorkspace>}

        <footer><span><Database size={13}/>{data.public_demo?'Shared demo · Changes are visible to everyone':'Saved to workspace · PLiZ demo'}</span><span>Planning starts {formatDate(data.instance.start,true)} · Synthetic data</span></footer>
      </div>:!busy?<section className="panel empty"><h2>Let’s reconnect your workspace.</h2><p>The local service isn’t responding. Check that start.ps1 is running, then try again.</p><button className="primary" onClick={()=>void action('Reconnecting',async()=>{await load();})}>Try again</button></section>:<div className="skeleton-layout" aria-hidden="true"><div/><div/><div/><div/></div>}
    </main>
    <nav className="mobile-nav" aria-label="Phone navigation">
      {navigation.filter(item=>['Overview','Schedule','Risk forecast','Assistant'].includes(item.id)).map(({id,label,icon:Icon})=><button key={id} disabled={!!busy} className={view===id?'active':''} aria-current={view===id?'page':undefined} aria-label={label} onClick={()=>open(id)}><Icon size={22}/><span>{id==='Risk forecast'?'Test change':id==='Assistant'?'Assistant':label}</span></button>)}
      <button className={['Crew roster','Checks & data','Public reports'].includes(view)?'active':''} aria-label="More workspace options" aria-haspopup="dialog" aria-expanded={mobileMenu} onClick={()=>setMobileMenu(true)}><Menu size={22}/><span>More</span></button>
    </nav>
    {mobileMenu&&<Modal title="Your workspace" onClose={()=>setMobileMenu(false)}><p className="muted">Your crew, data and planning help.</p><div className="mobile-menu-options">{navigation.filter(item=>['Crew roster','Checks & data','Public reports'].includes(item.id)).map(({id,label,icon:Icon})=><button key={id} disabled={!!busy} onClick={()=>open(id)}><span className="tile-icon"><Icon size={22}/></span><span><strong>{label}</strong><small>{id==='Crew roster'?'People, skills and availability':id==='Public reports'?'Reports and photos from the public':'Validation and GitHub source data'}</small></span><ArrowRight size={18}/></button>)}<button onClick={()=>{setMobileMenu(false);setHelp(true);}}><span className="tile-icon"><HelpCircle size={22}/></span><span><strong>How to use PLiZ</strong><small>A quick guide to the workspace</small></span><ArrowRight size={18}/></button></div></Modal>}
    {help&&<Modal title="A simple way to plan" onClose={()=>setHelp(false)}><p className="muted">Start with the existing demo plan. Everything below uses your current scenario.</p><ol className="help-steps"><li><b>Review the schedule</b><p>Browse by week. Open a shift to see its crew, track locations and dates.</p></li><li><b>Keep your crew up to date</b><p>Add people, choose their skills and enter leave. Saving automatically recalculates the generated plan.</p></li><li><b>Test before changing</b><p>Choose a closure or absence, preview the impact, then apply the plan when you’re happy with it.</p></li><li><b>Ask when you need context</b><p>The assistant can explain assignments and deadlines, or run a what-if preview for you.</p></li></ol><details><summary>Common terms</summary><dl className="detail-list"><div><dt>Activity</dt><dd>A maintenance job needing one or more night shifts.</dd></div><div><dt>Access</dt><dd>A night when a job is allowed to use a track section.</dd></div><div><dt>ECLO</dt><dd>Early closure / late opening: extended engineering hours.</dd></div><div><dt>Scenario</dt><dd>A planning policy that balances capacity and deadlines.</dd></div></dl></details><button className="primary full" onClick={()=>setHelp(false)}>Got it — let’s plan <ArrowRight size={16}/></button></Modal>}
    {rebuildConfirm&&<Modal title="Start from a fresh plan?" onClose={()=>setRebuildConfirm(false)}><p>This replaces the currently applied disruption plan with a fresh schedule using your latest crew and original track availability. Your saved preview history stays available.</p><div className="modal-actions"><button onClick={()=>setRebuildConfirm(false)}>Keep current plan</button><button className="primary" onClick={()=>void rebuild()}>Rebuild plan</button></div></Modal>}
  </div>;
}
function Heading({kicker,title}:{kicker:string;title:string}){return <div className="panel-heading"><div><span className="overline">{kicker}</span><h3>{title}</h3></div></div>;}
function Metrics({items}:{items:[number,string,string][]}){return <div className="metrics">{items.map(([value,label,detail])=><Metric key={label} value={value} label={label} detail={detail}/>)}</div>;}
function ChevronRightIcon(){return <ArrowRight size={15}/>;}
