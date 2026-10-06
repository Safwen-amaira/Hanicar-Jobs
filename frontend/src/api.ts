const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function download(path: string) {
  window.open(`${API_BASE}${path}`, "_blank", "noopener,noreferrer");
}

export type OpportunityType = {
  id: string;
  code: string;
  label_en: string;
  label_fr: string;
  label_ar: string;
  is_system: boolean;
};

export type Candidate = {
  id: string;
  name: string;
  email: string;
  locale: string;
  created_at: string;
};

export type SearchProfile = {
  id: string;
  candidate_id: string;
  name: string;
  keywords: string[];
  locations: string[];
  opportunity_type_codes: string[];
  active: boolean;
  created_at: string;
};

export type Opportunity = {
  id: string;
  title: string;
  description: string;
  company_id?: string;
  company_name?: string;
  opportunity_type_code?: string;
  source: string;
  source_url?: string;
  location?: string;
  remote: boolean;
  deadline?: string;
  status: string;
  match_score?: number;
  match_reasons: string[];
  skill_gaps: string[];
  exclusion_reasons: { code: string; detail: string }[];
  collected_at: string;
};

export type Application = {
  id: string;
  opportunity_id: string;
  candidate_id: string;
  status: string;
  draft_body: string;
  override_log: unknown[];
  follow_up_due_at?: string;
  applied_at?: string;
  interview_at?: string;
  decision_at?: string;
  next_action_at?: string;
  contact_name: string;
  contact_email: string;
  notes: string;
  created_at: string;
  updated_at?: string;
  opportunity_title?: string;
  company_name?: string;
  source?: string;
  source_url?: string;
};

export type CandidateProfile = {
  id: string;
  candidate_id: string;
  cv_text: string;
  skills: string[];
  preferences: {
    cv_attachment?: {
      filename: string;
      content_type: string;
      data_base64?: string;
    };
    cover_letter_attachment?: {
      filename: string;
      content_type: string;
      data_base64?: string;
    };
    [key: string]: unknown;
  };
};

export type SmtpSettings = {
  host: string;
  port: number;
  username: string;
  password: string;
  from_email: string;
  from_name: string;
  use_tls: boolean;
};

export type SmtpTestResult = {
  ok: boolean;
  status: string;
  detail: string;
};

export type EmailCompose = {
  application_id: string;
  to: string;
  subject: string;
  body: string;
  suggested_attachments: { filename: string; kind: string }[];
  warnings: string[];
  ready: boolean;
};

export type ContactDiscovery = {
  application_id: string;
  emails: string[];
  apply_urls: string[];
  selected_email: string;
  note: string;
};

export type FollowUpDraft = {
  application_id: string;
  draft: string;
  due_at?: string;
  auto_send: boolean;
  note: string;
};

export type BatchPreviewItem = {
  application_id: string;
  opportunity_title?: string;
  company_name?: string;
  source?: string;
  status: string;
  to?: string;
  subject?: string;
  warnings?: string[];
  ready?: boolean;
  detail?: string;
};

export type BatchSendResult = {
  attempted: number;
  sent: number;
  skipped: number;
  dry_run: boolean;
  results: BatchPreviewItem[];
};

export type BatchPrepareResult = {
  attempted: number;
  queued: number;
  needs_review: number;
  skipped: number;
  results: BatchPreviewItem[];
};

export type SourceHealth = {
  source_name: string;
  last_run?: string;
  success_count: number;
  error_count: number;
  last_error?: string;
  success_rate: number;
};

export type SearchRun = {
  id: string;
  profile_id: string;
  status: string;
  stats: Record<string, number>;
  events: Record<string, unknown>[];
};

export type Health = {
  status: string;
  tagline: string;
  ai_enabled: boolean;
  llm_provider: string;
  llm_model: string;
  llm_live: boolean;
  human_in_the_loop: boolean;
  auto_send: boolean;
  llm_hint: string;
  auto_draft_enabled: boolean;
  auto_polish_with_llm: boolean;
};

export type LlmStatus = {
  ai_enabled: boolean;
  requested_provider: string;
  provider: string;
  model: string;
  live: boolean;
  human_in_the_loop: boolean;
  auto_send: boolean;
  auto_draft_enabled: boolean;
  auto_polish_with_llm: boolean;
  chain: string[];
  hint: string;
};

export type LlmPing = {
  ok: boolean;
  live: boolean;
  provider: string;
  model: string;
  sample: string;
  human_in_the_loop: boolean;
  auto_send: boolean;
  hint: string;
};

export type AutoQueueResult = {
  created: number;
  skipped: number;
  application_ids: string[];
  note: string;
};

export const api = {
  health: () => request<Health>("/api/health"),
  llmPing: () => request<LlmPing>("/api/health/llm"),
  llmStatus: () => request<LlmStatus>("/api/health/llm-status"),
  meta: () => request<Record<string, unknown>>("/api/meta"),
  opportunityTypes: () => request<OpportunityType[]>("/api/opportunity-types"),
  createOpportunityType: (body: { code: string; label_en: string; label_fr?: string; label_ar?: string }) =>
    request<OpportunityType>("/api/opportunity-types", { method: "POST", body: JSON.stringify(body) }),
  candidates: () => request<Candidate[]>("/api/candidates"),
  createCandidate: (body: { name: string; email: string; locale?: string }) =>
    request<Candidate>("/api/candidates", { method: "POST", body: JSON.stringify(body) }),
  updateProfile: (id: string, body: { cv_text: string; skills: string[]; preferences: Record<string, unknown> }) =>
    request(`/api/candidates/${id}/profile`, { method: "PUT", body: JSON.stringify(body) }),
  profile: (id: string) => request<CandidateProfile>(`/api/candidates/${id}/profile`),
  updateCvAttachment: (id: string, body: { filename: string; content_type: string; data_base64: string }) =>
    request<CandidateProfile>(`/api/candidates/${id}/cv-attachment`, { method: "PUT", body: JSON.stringify(body) }),
  updateCoverLetterAttachment: (id: string, body: { filename: string; content_type: string; data_base64: string }) =>
    request<CandidateProfile>(`/api/candidates/${id}/cover-letter-attachment`, { method: "PUT", body: JSON.stringify(body) }),
  searchProfiles: (candidateId?: string) =>
    request<SearchProfile[]>(`/api/search-profiles${candidateId ? `?candidate_id=${candidateId}` : ""}`),
  createSearchProfile: (body: {
    candidate_id: string;
    name: string;
    keywords: string[];
    locations: string[];
    opportunity_type_codes: string[];
  }) => request<SearchProfile>("/api/search-profiles", { method: "POST", body: JSON.stringify(body) }),
  opportunities: (status?: string) =>
    request<Opportunity[]>(`/api/opportunities${status ? `?status=${status}` : ""}`),
  webSearchOpportunities: (body: { query: string; locations?: string[]; candidate_id?: string; limit?: number }) =>
    request<Opportunity[]>("/api/opportunities/web-search", { method: "POST", body: JSON.stringify(body) }),
  opportunity: (id: string) => request<Opportunity>(`/api/opportunities/${id}`),
  suppressed: () => request<Opportunity[]>("/api/suppressed"),
  runSearch: (profileId: string) =>
    request<SearchRun>(`/api/search/${profileId}/run`, { method: "POST" }),
  resolveCompany: (body: { name: string; domain?: string; country?: string }) =>
    request("/api/companies/resolve", { method: "POST", body: JSON.stringify(body) }),
  upsertContact: (body: { company_id: string; candidate_id: string; status: string; notes?: string }) =>
    request("/api/contacts", { method: "PUT", body: JSON.stringify(body) }),
  applications: () => request<Application[]>("/api/applications"),
  createApplication: (body: { opportunity_id: string; candidate_id: string; override_notes?: string; manual_recontact_override?: boolean }) =>
    request<Application>("/api/applications", { method: "POST", body: JSON.stringify(body) }),
  updateApplication: (id: string, body: {
    status?: string;
    override_notes?: string;
    follow_up_due_at?: string;
    applied_at?: string;
    interview_at?: string;
    decision_at?: string;
    next_action_at?: string;
    contact_name?: string;
    contact_email?: string;
    notes?: string;
  }) =>
    request<Application>(`/api/applications/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  regenerateApplication: (id: string, body: { instructions?: string; tone?: string; include_email_subject?: boolean }) =>
    request<Application>(`/api/applications/${id}/regenerate`, { method: "POST", body: JSON.stringify(body) }),
  composeEmail: (id: string) => request<EmailCompose>(`/api/applications/${id}/email`),
  discoverContact: (id: string) => request<ContactDiscovery>(`/api/applications/${id}/discover-contact`),
  followUpDraft: (id: string) => request<FollowUpDraft>(`/api/applications/${id}/follow-up`),
  dueFollowUps: () => request<Application[]>("/api/applications/due/follow-ups"),
  testSmtp: (body: SmtpSettings) =>
    request<SmtpTestResult>("/api/applications/smtp/test", { method: "POST", body: JSON.stringify(body) }),
  sendEmail: (id: string, body: {
    to: string;
    subject: string;
    body: string;
    smtp?: SmtpSettings;
    attach_cv: boolean;
    attach_cover_letter: boolean;
    manual_recontact_override?: boolean;
    human_verified?: boolean;
  }) => request<{ sent: boolean; status: string; detail: string; attachments: string[] }>(
    `/api/applications/${id}/send-email`,
    { method: "POST", body: JSON.stringify(body) }
  ),
  batchSend: (body: {
    max_to_send: number;
    delay_seconds: number;
    statuses: string[];
    smtp?: SmtpSettings;
    attach_cv: boolean;
    attach_cover_letter: boolean;
    dry_run: boolean;
    manual_recontact_override?: boolean;
    human_verified_ids?: string[];
  }) => request<BatchSendResult>("/api/applications/batch-send", { method: "POST", body: JSON.stringify(body) }),
  prepareBatch: (body: {
    max_to_prepare: number;
    statuses: string[];
    persist_contacts?: boolean;
    polish_with_llm?: boolean;
  }) => request<BatchPrepareResult>("/api/applications/batch-prepare", { method: "POST", body: JSON.stringify(body) }),
  autoQueue: (body: {
    candidate_id: string;
    min_score?: number;
    max_to_draft?: number;
    polish_with_llm?: boolean;
  }) => request<AutoQueueResult>("/api/applications/auto-queue", { method: "POST", body: JSON.stringify(body) }),
  downloadApplicationPdf: (id: string) => download(`/api/applications/${id}/pdf`),
  downloadCoverLetter: (id: string) => download(`/api/applications/${id}/cover-letter.pdf`),
  downloadCvPdf: (id: string) => download(`/api/applications/${id}/cv.pdf`),
  sources: () => request<SourceHealth[]>("/api/sources/health"),
};
