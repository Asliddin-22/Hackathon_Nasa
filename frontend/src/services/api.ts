export type User = { id: string; name: string; role: 'astronaut' | 'doctor' };
export type Measurement = { id: string; user_id: string; metric: string; value: number; unit: string; timestamp: string; source: string; origin: string; quality: string };
export type Finding = {module: string; status: string; observation: string; certainty: string; doctor_review: boolean; timestamp: string; references: string[]; statistics: {baseline?: number; current_mean?: number; change_percent?: number; unit?: string; data_status: string; window_days?: number; previous_mean?: number; excluded_count?: number; missing_days?: number}; explanation: {mode: string; evidence: string[]; guidance_status: string}; rule?: {threshold_percent: number; direction: string; authority: string}; actions: {code: string; text: string}[]};
export type Alert = {id: string; user_id: string; module: string; title: string; severity: string; status: string; created_at: string; evidence: {assistant_response?: AssistantAnswer; description?: string; actions?: {code: string; text: string}[]}};
export type Review = {id: string; user_id: string; alert_id: string; doctor_id: string; assessment: string; feedback: string; created_at: string; delivered_at: string | null; acknowledged_at: string | null};
export type HealthRecord = {user: User; captured_at: string; latest: Record<string, Measurement>; baselines: {metric: string; value: number; unit: string; origin: string}[]; measurements: Measurement[]; tests: {id: string; test_type: string; results: {note: string}; timestamp: string; origin: string}[]; assessments: Finding[]; alerts: Alert[]; symptoms: {description: string; severity: number; timestamp: string; origin: string}[]; reviews: Review[]; assistant_messages?: AssistantAnswer[]};
export type GroundRecord = {user_id: string; captured_at: string; received_at: string; snapshot: HealthRecord};
export type Mission = {profile: string; environment: string; gravity: string; start_time: string; online: boolean; delay_seconds: number; last_sync: string | null; equipment: string[]};
export type SyncState = {queued: number; events: {id: string; destination: string; kind: string; status: string; retry_count: number; created_at: string; available_at: string; delivered_at: string | null}[]};
export type Session = {token: string; user: User};

export async function request<T>(path: string, token?: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {method, headers: {'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {})}, ...(body !== undefined ? {body: JSON.stringify(body)} : {})});
  if (!response.ok) {
    const error = await response.json().catch(() => ({detail: 'The backend did not return a valid response.'}));
    const detail = typeof error.detail === 'string' ? error.detail : Array.isArray(error.detail) ? error.detail.map((d: {msg: string}) => d.msg).join('; ') : 'Request failed';
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json();
}
export const labels: Record<string,string> = {resting_hr:'Resting heart rate',hrv:'Heart rate variability',strength:'Muscle strength',balance_sway:'Balance sway',exercise_minutes:'Exercise duration',hydration:'Hydration',systolic_bp:'Systolic blood pressure',diastolic_bp:'Diastolic blood pressure'};
export const modules: Record<string,string> = {cardiovascular:'Cardiovascular',muscle:'Muscle health',balance:'Balance & coordination',bone:'Bone health',kidney:'Kidney health',vision:'Vision / SANS',symptoms:'Reported symptoms',assistant:'AI assistant review'};
export const dateTime = (s?: string | null) => s ? new Date(s).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : 'Not yet received';
export const day = (s: string) => new Date(s).toLocaleDateString([], {month:'short',day:'numeric'});

export type ReferencePassage = {chunk_id:string; heading:string; text:string; rank:number; citation:{source_id:string; title:string; url:string; publisher:string; category:string; system:string; source_updated:string|null; reviewed_on:string; version:string; text_sha256:string; attribution:string; scope:string}};
export type AssistantAnswer = {
 id?:string; conversation_id?:string; parent_id?:string|null; intent?:string; generation_status?:string; short_answer_block_ids?:string[]; schema_version:string; question:string; short_answer:string; mode:string; coverage:string; origin:string; created_at:string;
 safety:{immediate_guidance?:{code:string;text:string;citation_ids:string[]}[]; protocol_status?:string; approved_procedures?:{id:string;title:string;version:string;steps:unknown[];references:unknown[]}[]; communication?:{online:boolean;delay_seconds:number;simulation:boolean}; support?:{medical_personnel_available?:boolean|null}; urgent:boolean; matched_warning_signs:string[]; warning:string; scope:string; actions:{code:string;text:string}[]};
 detailed:{patient_observations:{id:string;metric:string;value:number;unit:string;collected_at:string;origin:string;source:string;quality:string;stale:boolean;baseline:number|null;change_percent:number|null}[];
 historical_evidence:{module:string;status:string;observation:string;statistics:{current_mean?:number;previous_mean?:number;change_percent?:number;unit?:string;data_status:string}}[];
 mission:{environment?:string;gravity?:string;earth_online?:boolean;delay_seconds?:number};
 reported_symptoms:{description:string;severity:number;timestamp:string;origin:string}[];medical_tests?:{test_type:string;results:Record<string,unknown>;timestamp:string;origin:string}[];
 reasoning:{id?:string;text:string;citation_ids:string[];fact_ids?:string[];kind:string;basis?:string}[];
 possible_explanations:{id:string;title:string;reasoning:string;certainty:string;citation_ids:string[];basis?:string;fact_ids?:string[]}[];
 follow_up_questions:string[];recommendations:{code:string;text:string;basis?:string;citation_ids?:string[];fact_ids?:string[]}[];uncertainties:string[];references:ReferencePassage[];ranking_note:string;
 };
};
