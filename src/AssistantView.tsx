import { useEffect, useRef } from 'react';
import { ArrowRight, ArrowUpRight, Bot, CheckCircle2, RotateCcw, Send, ShieldCheck } from 'lucide-react';
import type { Chat, Forecast, State } from './types';

function MessageText({text}:{text:string}) {
  return <div className="message-content">{text.split('\n').filter(Boolean).map((line,i)=><p key={i}>{line.split(/(\*\*[^*]+\*\*)/g).map((part,j)=>part.startsWith('**')?<strong key={j}>{part.slice(2,-2)}</strong>:part)}</p>)}</div>;
}
const examples=[
  {title:'Plan around a closure',text:'Simulate SEC:BET:H01_H02:EB closed in week 11 for 2 weeks.'},
  {title:'Add someone to the crew',text:'Add Jamie Tan as a Technician with track and construction skills, maximum 3 shifts per week.'},
  {title:'Save a crew change',text:'Mark Aisha Rahman on leave in weeks 11-12 and update the schedule.'},
  {title:'Create a maintenance job',text:'Add a job under C001 at the Beta H02 eastbound platform, starting week 20, requiring 1 work unit, priority 2.'},
  {title:'Rebuild the plan',text:'Rebuild the plan.'},
  {title:'Understand delays',text:'Which contracts are late, and why?'},
];

type Props={chat:Chat[];prompt:string;setPrompt:(s:string)=>void;ask:(s?:string)=>void;clearChat:()=>void;busy:boolean;data:State;forecast:Forecast|null;openForecast:()=>void;openResult:(view:string,query?:string,scenario?:string)=>void;retry?:()=>void;test:()=>void};
export function AssistantView({chat,prompt,setPrompt,ask,clearChat,busy,data,forecast,openForecast,openResult,retry,test}:Props) {
  const bottom=useRef<HTMLDivElement>(null);
  const promptInput=useRef<HTMLTextAreaElement>(null);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[chat.length,busy]);
  function chooseExample(text:string){setPrompt(text);promptInput.current?.focus();}
  return <div className="assistant-layout">
    <section className="panel chat-panel">
      <div className="chat-header"><span className="tile-icon green"><Bot size={22}/></span><div className="chat-heading"><h2>Your planning assistant</h2><p>Ask a question, or tell me what to update.</p></div><div className="chat-header-actions"><span className="badge">{data.ai.configured?'AI enabled':'Local mode'}</span><button type="button" className="ghost chat-clear" disabled={busy} onClick={()=>{clearChat();promptInput.current?.focus();}}><RotateCcw size={15} aria-hidden="true"/>Clear chat</button></div></div>
      <div className="chat-thread" aria-live="polite">
        {chat.map((c,i)=><div key={c.request_id??i} className={'message '+c.role+(c.action_error?' action-failed':'')}>
          <span className="message-author">{c.role==='user'?'You':'PLiZ assistant'}{c.model==='Local planner'?' · local response':''}</span>
          {c.receipt?<div className="action-receipt"><span className="badge good"><CheckCircle2 size={14}/>Saved · Scenario {c.receipt.scenario}</span><h3>{c.receipt.title}</h3><ul>{c.receipt.details.map((detail,j)=><li key={j}>{detail}</li>)}</ul><button disabled={busy} onClick={()=>openResult(c.receipt!.target,c.receipt!.query,c.receipt!.scenario)}>View {c.receipt.target==='Crew roster'?'crew':'schedule'} <ArrowRight size={15}/></button></div>:<MessageText text={c.text}/>}
        </div>)}
        {busy&&<div className="thinking"><span className="spinner"/>Checking your request and working on the plan…</div>}
        <div ref={bottom}/>
      </div>
      {retry&&<div className="assistant-retry" role="status"><p>The request's result could not be confirmed. Retry safely with the same request ID.</p><button disabled={busy} onClick={retry}><RotateCcw size={15}/>Retry last request</button></div>}
      {forecast&&<button className="forecast-shortcut" onClick={openForecast}><ShieldCheck size={17}/><span>Forecast ready · {forecast.risk_band} impact</span><ArrowRight size={16}/></button>}
      {forecast&&<p className="assistant-apply-hint">Review the forecast, then say <button disabled={busy} onClick={()=>chooseExample('Apply this plan.')}>“Apply this plan”</button> to save it.</p>}
      <form className="chat-form" onSubmit={e=>{e.preventDefault();ask();}}><label className="sr-only" htmlFor="assistant-prompt">Message the assistant</label><textarea ref={promptInput} id="assistant-prompt" value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();if(!busy&&prompt.trim())ask();}}} placeholder="Ask a question, add crew, update leave or plan a job…" required/><button className="primary" aria-label="Send message" disabled={busy||!prompt.trim()}><Send size={19}/></button></form>
      <div className="composer-hint"><span>Enter to send · Shift + Enter for a new line</span><span>Direct requests can save changes.</span></div>
    </section>
    <aside className="assistant-tools"><span className="overline">ASK IT TO HELP</span><h3>What would you like done?</h3><p>Choose an example, edit the details, then send.</p>
      {examples.map(item=><button className="prompt-chip" key={item.title} disabled={busy} onClick={()=>chooseExample(item.text)}><span><strong>{item.title}</strong><small>{item.text}</small></span><ArrowUpRight size={16}/></button>)}
      <div className="assistant-info"><ShieldCheck size={18}/><p>I can save crew and job changes, rebuild the plan, or apply a preview when you ask. Simulations stay as previews until you request Apply.</p></div>
      <details><summary>Connection details</summary><p>{data.ai.configured?data.ai.model:'Local planner'} · {data.ai.message}</p><button disabled={busy} onClick={test}>Check connection</button></details>
    </aside>
  </div>;
}
