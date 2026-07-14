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
  tshirt_options: string[];
  junior_cutoff_date: string | null;
  tshirt_included: boolean;
  has_certificate_background: boolean;
};

export type CompetitionDto = {
  id: string;
  lap_count: number;
  title_i18n: Record<string, string> | null;
  price_cents: number;
  price_junior_cents: number | null;
  currency: string;
  start_time: string | null;
};

export type TimingPing = { bib_number: number; absolute_time: string; dedup_key: string };

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
  tshirt: string | null;
  tshirt_options: string[];
  finish_seconds: number | null;
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
  gender: string;
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

  certificatePdfUrl: (token: string) =>
    `${BASE}/manage/certificate.pdf?token=${encodeURIComponent(token)}`,

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
  competition_title: Record<string, string> | null;
  lap_count: number;
  payment_method: string | null;
  payment_status: string | null;
  finish_seconds: number | null;
};

export type DeviceTokenDto = {
  id: string;
  label: string;
  token?: string | null;
  time_offset_seconds: number;
  active: boolean;
};

export type AdminRegistrationList = { total: number; items: AdminRegistration[] };

export type TimingRow = {
  id: string;
  absolute_time: string;
  lap_index: number | null;
  status: string;
};

export type EventCreatePayload = {
  name: string;
  year: number;
  event_date: string;
  registration_deadline?: string | null;
  default_start_time?: string | null;
  junior_cutoff_date?: string | null;
  tshirt_included: boolean;
  tshirt_options?: string[] | null;
  competitions: {
    title?: string | null;
    price_cents: number;
    price_junior_cents?: number | null;
    start_time?: string | null;
  }[];
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
  tshirt: string | null;
  tshirt_options: string[];
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
  tshirt: string | null;
}>;

export const adminApi = {
  login: (email: string, password: string) =>
    req<SessionInfo>("/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => adminReq<SessionInfo>("/admin/me"),
  listRegistrations: (eventId: string, q = "", limit = 50, offset = 0) =>
    adminReq<AdminRegistrationList>(
      `/admin/registrations?event_id=${eventId}&limit=${limit}&offset=${offset}` +
        (q ? `&q=${encodeURIComponent(q)}` : "")
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
  updateCompetition: (
    id: string,
    body: { start_time?: string | null; price_cents?: number; price_junior_cents?: number | null }
  ) =>
    adminReq<{ id: string; price_cents: number; price_junior_cents: number | null }>(
      `/admin/competitions/${id}`,
      { method: "PATCH", body: JSON.stringify(body) }
    ),
  updateEvent: (
    eventId: string,
    body: { tshirt_options?: string[]; junior_cutoff_date?: string | null; tshirt_included?: boolean }
  ) =>
    adminReq<{ id: string }>(`/admin/events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  createEvent: (body: EventCreatePayload) =>
    adminReq<{ id: string; year: number; name: string }>("/admin/events", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteEvent: (id: string) => adminReq(`/admin/events/${id}`, { method: "DELETE" }),
  recomputeTimes: (eventId: string) =>
    adminReq<{ updated: number }>(`/admin/events/${eventId}/recompute-times`, { method: "POST" }),
  listTimings: (eventId: string, bib: number) =>
    adminReq<TimingRow[]>(`/events/${eventId}/timings/${bib}`),
  correctTiming: (
    id: string,
    body: { status: string; bib_number?: number; absolute_time?: string }
  ) => adminReq(`/timings/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTiming: (id: string) => adminReq(`/timings/${id}`, { method: "DELETE" }),
  addTiming: (eventId: string, bib: number, absoluteTime: string) =>
    adminReq(`/events/${eventId}/timings/${bib}/manual`, {
      method: "POST",
      body: JSON.stringify({ absolute_time: absoluteTime }),
    }),
  version: () => req<VersionInfo>("/version"),
  certificateGroups: (eventId: string) =>
    adminReq<CertificateGroup[]>(`/admin/events/${eventId}/certificate-groups`),
  getMailSettings: () => adminReq<MailSettings>("/admin/mail-settings"),
  setMailMode: (testMode: boolean) =>
    adminReq<MailSettings>("/admin/mail-settings", {
      method: "PATCH",
      body: JSON.stringify({ test_mode: testMode }),
    }),
};

export type MailSettings = {
  test_mode: boolean;
  test_recipient: string;
  overridden: boolean;
};

export type VersionInfo = { backend: string; db_schema: string | null };

export type CertificateGroup = {
  competition_id: string;
  competition_title: Record<string, string> | null;
  age_class: string | null;
  count: number;
};

/** SEPA-Lastschriften als CSV (mit Auth-Header) laden – gibt Blob + Dateiname. */
export async function downloadSepaExport(
  eventId: string,
  includeExported = false
): Promise<{ blob: Blob; filename: string }> {
  const url =
    `${BASE}/admin/events/${eventId}/sepa-export` +
    (includeExported ? "?include_exported=true" : "");
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken.get()}` },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error((d as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  return { blob: await res.blob(), filename: m ? m[1] : "sepa-export.csv" };
}

/** Authentifizierter Datei-Download (Bearer) -> Blob + Dateiname. */
async function authedBlob(url: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${adminToken.get()}` } });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error((d as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  return { blob: await res.blob(), filename: m ? m[1] : "download.pdf" };
}

/** Sammel-PDF aller Urkunden einer (Lauf × Altersklasse)-Kombination. */
export function downloadCertificateBundle(
  eventId: string,
  competitionId: string,
  ageClass: string | null,
  lang: string
): Promise<{ blob: Blob; filename: string }> {
  const q = new URLSearchParams({ age_class: ageClass ?? "", lang }).toString();
  return authedBlob(
    `${BASE}/admin/events/${eventId}/competitions/${competitionId}/certificates?${q}`
  );
}

/** Einzelne Urkunde für eine Startnummer. */
export function downloadCertificateByBib(
  eventId: string,
  bib: number,
  lang: string
): Promise<{ blob: Blob; filename: string }> {
  const q = new URLSearchParams({ bib: String(bib), lang }).toString();
  return authedBlob(`${BASE}/admin/events/${eventId}/certificate?${q}`);
}

/** Urkunden-Hintergrund (Bild) für ein Event hochladen (Multipart, mit Auth). */
export async function uploadCertificateBackground(
  eventId: string,
  file: File
): Promise<{ ok: boolean; size: number }> {
  const form = new FormData();
  form.append("file", file);
  // Kein Content-Type setzen – der Browser ergänzt den Multipart-Boundary selbst.
  const res = await fetch(`${BASE}/admin/events/${eventId}/certificate-background`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken.get()}` },
    body: form,
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error((d as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** Zeiterfassung: sendet erfasste Paare an die Ingestion-API (Geräte-Token). */
export async function sendTimings(
  eventId: string,
  token: string,
  pings: TimingPing[]
): Promise<{ accepted: number; duplicates: number }> {
  const res = await fetch(`${BASE}/events/${eventId}/timings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ pings }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error((d as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function formatTime(seconds: number | null): string {
  if (seconds == null) return "–";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}
