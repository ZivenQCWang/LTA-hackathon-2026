import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

export const policies = {
  A: { name: 'Protect capacity', description: 'Stay within available nights. Finish dates can move.' },
  B: { name: 'Meet deadlines', description: 'Protect finish dates using extra access when needed.' },
  C: { name: 'Balanced plan', description: 'Balance delivery dates with limited extra access.' },
};
export type Scenario = keyof typeof policies;
export function formatDate(value: string | null, long = false) {
  if (!value) return 'Not fully scheduled';
  return new Date(value.slice(0,10)+'T12:00:00').toLocaleDateString('en-SG', { day:'numeric', month:'short', ...(long ? {year:'numeric'} : {}) });
}
export function weekDate(start: string, week: number, extraDays = 0) {
  const d = new Date(start+'T12:00:00'); d.setDate(d.getDate()+(week-1)*7+extraDays);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
export function locationName(id: string) {
  const [kind,line,section,bound]=id.split(':');
  return `${line==='ALP'?'Alpha':line==='BET'?'Beta':line} · ${kind==='PLAT'?'Platform ':''}${section?.replaceAll('_',' – ')} · ${bound==='EB'?'Eastbound':'Westbound'}`;
}
export function initials(name: string) { return name.split(' ').map(x=>x[0]).slice(0,2).join(''); }
export function Modal({title,children,onClose,busy=false}:{title:string;children:ReactNode;onClose:()=>void;busy?:boolean}) {
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{const dialog=ref.current; dialog?.showModal(); return()=>dialog?.close();},[]);
  return <dialog ref={ref} className="modal" aria-label={title} onCancel={e=>{e.preventDefault();if(!busy)onClose();}} onClick={e=>{const r=e.currentTarget.getBoundingClientRect();if(e.target===e.currentTarget&&!busy&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))onClose();}}>
    <div className="modal-header"><h2>{title}</h2><button className="icon ghost" aria-label="Close dialog" disabled={busy} onClick={onClose}><X size={20}/></button></div>{children}
  </dialog>;
}
export function Empty({title,detail,action}:{title:string;detail:string;action?:ReactNode}) {
  return <div className="empty"><h3>{title}</h3><p>{detail}</p>{action}</div>;
}
export function Metric({value,label,detail,tone=''}:{value:number|string;label:string;detail:string;tone?:string}) {
  return <div className={'metric '+tone}><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}
