/**
 * Public transport contracts from backend/schemas and organization_routes.py.
 * Dates are JSON strings; responses are parsed bodies, without a data envelope.
 * These static contracts do not replace server validation or validate JSON.
 * @typedef {number|string} ID
 * @typedef {Record<string, unknown>} QueryParams
 * @typedef {{organization?:boolean,handleAuth?:boolean,params?:QueryParams,headers?:Record<string,string>,responseType?:'json'|'blob'}} RequestOptions
 * @typedef {RequestOptions & {method?:string,data?:unknown}} TransportOptions
 * @typedef {{organizationId:number|null,unauthorized:()=>void,forbidden:()=>void}} ApiConfiguration
 * @typedef {{get:<T=unknown>(endpoint:string,options?:RequestOptions)=>Promise<T>,post:<T=unknown>(endpoint:string,data?:unknown,options?:RequestOptions)=>Promise<T>,put:<T=unknown>(endpoint:string,data?:unknown,options?:RequestOptions)=>Promise<T>,patch:<T=unknown>(endpoint:string,data?:unknown,options?:RequestOptions)=>Promise<T>,delete:<T=unknown>(endpoint:string,options?:RequestOptions)=>Promise<T>}} ApiClient
 * @typedef {{id:number,email:string,is_active:boolean}} User
 * @typedef {{id:number,name:string,slug:string,role:string}} Organization
 * @typedef {{user:User}} LoginResponse
 * @typedef {{user:User|null,organizations:Organization[],organization:Organization|null,loading:boolean,error:string,accessMessage:string,login:(email:string,password:string)=>Promise<void>,logout:()=>Promise<void>,restoreSession:()=>Promise<void>,selectOrganization:(id:ID)=>void,clearAuth:()=>void}} AuthContextValue
 * @typedef {'New'|'Qualified'|'Contacted'|'Meeting'|'Won'|'Lost'} LeadLifecycle
 * @typedef {'Hot'|'Warm'|'Cold'} LeadPriority
 * @typedef {'pending'|'processing'|'completed'|'failed'} ProcessingStatus
 * @typedef {{id:number,lead_id:number|null,priority:LeadPriority,lead_score:number,result:Record<string,unknown>,created_at:string}} Analysis
 * @typedef {{id:number,company:string,email:string,source:string,industry:string|null,lead_score:number|null,priority:LeadPriority|null,ai_reason:string|null,next_action:string|null,status:LeadLifecycle,processing_status:ProcessingStatus,notes:string|null,last_contacted:string|null,next_follow_up:string|null,created_at:string}} Lead
 * @typedef {Lead & {current_analysis:Analysis|null}} LeadDetail
 * @typedef {Lead & {current_analysis:{id:number,lead_score:number,priority:LeadPriority}|null}} LeadListItem
 * @typedef {{items:LeadListItem[],page:number,page_size:number,total:number,pages:number}} LeadPage
 * @typedef {{company:string,email:string,source:string}} LeadCreate
 * @typedef {{status?:LeadLifecycle|null,notes?:string|null,last_contacted?:string|null,next_follow_up?:string|null}} LifecycleUpdate
 * @typedef {{id:number,company:string,email:string,source:string,analysis:Analysis|null}} LeadIntelligence
 * @typedef {{items:Analysis[],total:number,limit:number,offset:number}} AnalysisHistory
 * @typedef {{lead_id:number,processing_status:ProcessingStatus,analysis:Analysis|null,error:string|null}} LeadProcessing
 * @typedef {{lead_id:number,company:string,status:LeadLifecycle,processing_status:ProcessingStatus,lead_score:number,priority:LeadPriority}} CurrentOpportunity
 * @typedef {{analysis_id:number,lead_id:number|null,company:string,lead_score:number,priority:LeadPriority|'High'|'Unknown',created_at:string}} AnalysisActivity
 * @typedef {{pipeline:{total_leads:number,analyzed_leads:number,unanalyzed_leads:number,average_current_score:number|null},priority_distribution:{Hot:number,Warm:number,Cold:number,Unanalyzed:number},lifecycle_distribution:Record<LeadLifecycle,number>,processing_distribution:Record<ProcessingStatus,number>,top_opportunities:CurrentOpportunity[],recent_analysis_activity:AnalysisActivity[]}} DashboardOverview
 * @typedef {{analysis_id:number,lead_id:number|null,company:string,email:string,score:number,priority:string,created_at:string}} ReportEvent
 * @typedef {{period:{preset:'today'|'7d'|'30d'|'custom',start:string,end:string,timezone:'UTC'},summary:{analysis_events:number,unique_analyzed_leads:number,average_analysis_score:number|null,hot_events:number,warm_events:number,cold_events:number,other_priority_events:number},activity:{bucket:string,analysis_events:number}[],priority_distribution:Record<string,number>,top_opportunities:ReportEvent[],recent_analysis_events:ReportEvent[]}} ReportOverview
 * @typedef {{id:number,company:string,email:string,priority:string,lead_score:number}} ReportLead
 * @typedef {{total_leads:number,hot_leads:number,warm_leads:number,cold_leads:number,average_lead_score:number}} LegacyReportOverview
 * @typedef {LegacyReportOverview & {period:string,start_date:string,end_date:string,top_leads:ReportLead[]}} LegacyReport
 * @typedef {{period:string,overview:LegacyReportOverview,top_leads:ReportLead[],recommendations:string[]}} ExecutiveReport
 * @typedef {{row_number:number,company:string,email:string,source:string,status:'ready'|'duplicate'|'invalid',errors:string[]}} ImportRow
 * @typedef {{token:string,summary:{total:number,ready:number,duplicates:number,invalid:number},rows:ImportRow[],preview_limit:number,ignored_headers:string[]}} ImportPreview
 * @typedef {{total:number,imported:number,duplicates:number,invalid:number}} ImportResult
 * @typedef {{account:{email:string},workspace:{id:number,name:string,slug:string,role:'owner'|'admin'|'member'},ai:{provider:'mock'|'gemini'|'ollama'|'deepseek'|'unsupported',display_name:string,configured:boolean,processing_available:boolean,status:'development_only'|'configuration_ready'|'configuration_required'|'not_available',detail:string},capabilities:{csv_import:boolean,historical_reports:boolean,report_csv_export:boolean,crm_sync:boolean,automation_integration:boolean}}} SettingsOverview
 */
export {};
