export type Person = {id:string;name:string;role:string;skills:string;max_shifts:number;unavailable:string;active:boolean;demo:boolean};
export type Access = {activity_id:string;contract_number:string;week:number;night:number;date:string;access_seq:number;eclo:number;crew_ids:string[];crew_names:string[];skill:string};
export type Job = {activity_id:string;contract_number:string;line:string;bound:string;nature:string;activity_type:string;start_location_id:string;end_location_id:string;locations:string[];footprint:string[];affected_lines:string[];access_type:string;predecessor_activity_id:string;total_accesses:number;contract_priority:number;completion_date:string|null;completion_week:number|null;deadline:string;overrun_days:number|null;remaining_workload:number;accesses:Access[];reasons:string[]};
export type Contract = {contract_number:string;description:string;priority:number;completion_date:string|null;planned_completion_date:string;overrun_days:number|null;status:string};
export type Plan = {scenario:string;revision:string;options:Record<string,unknown>;accesses:Access[];activities:Job[];contracts:Contract[];metrics:{accesses:number;last_week:number;remaining_workload:number;late_contracts:number;overrun_days:number;eclo_nights:number;excess_nights:number;objective:number;changed_accesses:number};audit:{passed:boolean;checked_accesses:number;violations:{rule:string;detail:string}[];checks:string[]};assumptions:string[];method:string};
export type Forecast = {id:string;risk_band:string;directly_affected:number;max_delay_days:number;additional_overrun_days:number;explanation:string;changed_activities:{activity_id:string;contract_number:string;priority:number;before:string|null;after:string|null;delay_days:number|null;reason:string}[];candidate:Plan};
export type State = {plan:Plan;people:Person[];instance:{start:string;horizon:number;supply:Record<string,number>;lines:Record<string,{station_id:string}[]>};public_demo?:boolean;ai:{configured:boolean;connected:boolean;message:string;model:string};source:string};
export type ActionReceipt = {kind:string;title:string;details:string[];target:string;query?:string;scenario:string};
export type Chat = {role:'user'|'assistant';text:string;model?:string;request_id?:string;receipt?:ActionReceipt;action_error?:boolean};
export type AssistantRequest = {message:string;scenario:'A'|'B'|'C';history:Chat[];request_id:string;forecast_id?:string;reply_to?:string};
export type AssistantResult = {response:string;model:string;forecast:Forecast|null;request_id:string;receipt?:ActionReceipt;action_error?:boolean;ai_error?:string};
export type Score = {delay:number;extra_access:number;eclo:number;total:number;eligible:boolean;weighted_delay:number};
export type Insights = {
  same_conditions:boolean;
  scenarios:{scenario:'A'|'B'|'C';metrics:Plan['metrics'];score:Score;co_shared_shifts:number;eclo_line_nights:number;applied_change:boolean;options:Record<string,unknown>}[];
  details:{
    score:Score;
    co_shared_shifts:number;shared_location_slots_saved:number;
    sharing:{week:number;night:number;location:string;activities:string[]}[];
    capacity:{week:number;location:string;used:number;nominal:number;excess:number}[];
    passenger:{eclo_line_nights:number;engineering_footprint_stations:number;explanation:string;events:{line:string;week:number;night:number;activities:string[];stations:string[];locations:string[]}[]};
    search:{evaluated:number;method:string;candidates:{order:string;selected:boolean;objective:number;remaining:number;violations:number;changed:number}[]};
    issues:{activity_id:string;contract_number:string;overrun_days:number|null;remaining:number;predecessor:string;reasons:string[];blockers:{rule:string;week:number;night:number|null;detail:string;other_activity:string|null;locations:string[]}[];alternatives:{scenario:'A'|'B'|'C';completion_date:string;eclo_nights:number;excess_nights:number}[]}[];
    contracts:(Contract&{activities:number;workload:number;remaining:number;scheduled_percent:number;shifts:number;dependencies:string[]})[];
    crew:{id:string;name:string;role:string;limit:number;total:number;peak:number;weeks:{week:number;shifts:number}[]}[];
  };
  submission:{passed:boolean;official_validator:boolean;packaged:boolean;files:{name:string;columns:string[];rows:number}[];checks:string[];violations:string[];explanation:string};
};
