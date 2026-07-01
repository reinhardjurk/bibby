/** Typisierter API-Client für die Bibby-API. */

const BASE = (import.meta.env.VITE_API_BASE as string) || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type EventDto = {
  id: string;
  name: string;
  year: number;
  event_date: string;
  registration_deadline: string | null;
};

export type CompetitionDto = {
  id: string;
  lap_count: number;
  title_i18n: Record<string, string> | null;
  price_cents: number;
  currency: string;
};

export type RegistrationOut = {
  id: string;
  status: string;
  competition_id: string;
  bib_number: number | null;
  manage_token?: string | null;
  mandate_reference?: string | null;
};

export type ManageView = {
  registration: RegistrationOut;
  first_name: string;
  last_name: string;
  email: string;
  event_id: string;
  competition_lap_count: number;
  team: string | null;
  suggested_team: string | null;
  payment_method: string | null;
  payment_status: string | null;
  payment_iban_masked: string | null;
  mandate_reference: string | null;
};

export type LapSplit = { lap_index: number; elapsed_seconds: number };
export type ResultRow = {
  rank: number | null;
  bib_number: number;
  first_name: string;
  last_name: string;
  category_code: string | null;
  finish_seconds: number | null;
  splits: LapSplit[];
  participation_count: number;
  published?: boolean;
};
export type ResultList = {
  event_id: string;
  competition_id: string;
  lap_count: number;
  rows: ResultRow[];
};

export const api = {
  listEvents: () => req<EventDto[]>("/events"),
  listCompetitions: (eventId: string) =>
    req<CompetitionDto[]>(`/events/${eventId}/competitions`),
  listTeams: () => req<string[]>("/teams"),

  register: (body: unknown) =>
    req<RegistrationOut>("/registrations", { method: "POST", body: JSON.stringify(body) }),

  getManage: (token: string) =>
    req<ManageView>(`/manage?token=${encodeURIComponent(token)}`),

  updateManage: (token: string, body: unknown) =>
    req<RegistrationOut>(`/manage?token=${encodeURIComponent(token)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  bibPdfUrl: (token: string) => `${BASE}/manage/bib.pdf?token=${encodeURIComponent(token)}`,

  getResults: (eventId: string, competitionId: string) =>
    req<ResultList>(`/events/${eventId}/results?competition_id=${competitionId}`),
};

// --- Admin -----------------------------------------------------------------
const ADMIN_TOKEN_KEY = "bibby.admin";

export const adminToken = {
  get: () => localStorage.getItem(ADMIN_TOKEN_KEY) || "",
  set: (t: string) => localStorage.setItem(ADMIN_TOKEN_KEY, t),
  clear: () => localStorage.removeItem(ADMIN_TOKEN_KEY),
};

function adminReq<T>(path: string, init?: RequestInit): Promise<T> {
  return req<T>(path, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken.get()}` },
  });
}

export type SessionInfo = { token: string; expires_at: string; roles: string[] };

export type AdminRegistration = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  status: string;
  bib_number: number | null;
  competition_id: string;
  lap_count: number;
  payment_method: string | null;
  payment_status: string | null;
};

export type DeviceTokenDto = {
  id: string;
  label: string;
  token?: string | null;
  time_offset_seconds: number;
  active: boolean;
};

export type AdminRegistrationDetail = {
  id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  language: string;
  team: string | null;
  consent_data: boolean;
  consent_publish: boolean;
  status: string;
  bib_number: number | null;
  event_id: string;
  competition_id: string;
  lap_count: number;
  payment_method: string | null;
  payment_status: string | null;
  payment_iban_masked: string | null;
};

export type AdminRegistrationUpdate = Partial<{
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  language: string;
  team: string | null;
  consent_data: boolean;
  consent_publish: boolean;
  status: string;
  bib_number: number | null;
  competition_id: string;
  payment_method: string | null;
  payment_status: string | null;
}>;

export const adminApi = {
  login: (email: string, password: string) =>
    req<SessionInfo>("/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => adminReq<SessionInfo>("/admin/me"),
  listRegistrations: (eventId: string, q = "") =>
    adminReq<AdminRegistration[]>(
      `/admin/registrations?event_id=${eventId}${q ? `&q=${encodeURIComponent(q)}` : ""}`
    ),
  getRegistration: (id: string) =>
    adminReq<AdminRegistrationDetail>(`/admin/registrations/${id}`),
  updateRegistration: (id: string, body: AdminRegistrationUpdate) =>
    adminReq<AdminRegistrationDetail>(`/admin/registrations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  reassign: (regId: string, competitionId: string) =>
    adminReq(`/admin/registrations/${regId}/reassign`, {
      method: "POST",
      body: JSON.stringify({ competition_id: competitionId }),
    }),
  markPaid: (regId: string) =>
    adminReq(`/admin/registrations/${regId}/payment/mark-paid`, { method: "POST" }),
  assignBib: (regId: string, bib: number) =>
    adminReq(`/admin/registrations/${regId}/bib?bib_number=${bib}`, { method: "POST" }),
  listDeviceTokens: (eventId: string) =>
    adminReq<DeviceTokenDto[]>(`/admin/events/${eventId}/device-tokens`),
  createDeviceToken: (eventId: string, label: string, offset: number) =>
    adminReq<DeviceTokenDto>(`/admin/events/${eventId}/device-tokens`, {
      method: "POST",
      body: JSON.stringify({ label, time_offset_seconds: offset }),
    }),
  revokeDeviceToken: (id: string) =>
    adminReq(`/admin/device-tokens/${id}`, { method: "DELETE" }),
  internalResults: (eventId: string, competitionId: string) =>
    adminReq<ResultList>(`/admin/events/${eventId}/results?competition_id=${competitionId}`),
};

export function formatTime(seconds: number | null): string {
  if (seconds == null) return "–";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}
