import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  adminApi,
  adminToken,
  api,
  formatTime,
  type AdminRegistrationDetail,
  type AdminRegistrationUpdate,
  type CompetitionDto,
  type DeviceTokenDto,
  type EventDto,
  type ResultList,
} from "../api";
import { TeamInput } from "../components/TeamInput";
import { useI18n } from "../i18n";

// --- Session / Auth (geteilt zwischen Admin und Special-Admin) -------------
export function useAdminSession() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [roles, setRoles] = useState<string[]>([]);

  useEffect(() => {
    if (adminToken.get()) {
      adminApi
        .me()
        .then((s) => {
          setRoles(s.roles);
          setAuthed(true);
        })
        .catch(() => {
          adminToken.clear();
          setAuthed(false);
        });
    } else {
      setAuthed(false);
    }
  }, []);

  const onAuthed = (r: string[]) => {
    setRoles(r);
    setAuthed(true);
  };
  const logout = () => {
    adminToken.clear();
    setRoles([]);
    setAuthed(false);
  };
  return { authed, roles, onAuthed, logout };
}

export function LoginCard({ onAuthed }: { onAuthed: (roles: string[]) => void }) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const s = await adminApi.login(email, password);
      adminToken.set(s.token);
      onAuthed(s.roles);
    } catch {
      setError(t("admin.loginFailed"));
    }
  };

  return (
    <form className="card" onSubmit={submit}>
      <h2>{t("admin.login")}</h2>
      {error && <p className="error">{error}</p>}
      <label>
        {t("register.email")}
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        {t("admin.password")}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      <button className="primary" type="submit">
        {t("admin.login")}
      </button>
    </form>
  );
}

export function AdminChrome({
  title,
  roles,
  logout,
  children,
}: {
  title: string;
  roles: string[];
  logout: () => void;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="card">
      <div className="admin-head">
        <h2>{title}</h2>
        <div>
          <span className="badge">{roles.join(", ")}</span>{" "}
          <button onClick={logout}>{t("admin.logout")}</button>
        </div>
      </div>
      {children}
    </div>
  );
}

export const canManage = (roles: string[]) =>
  roles.includes("admin") || roles.includes("race_office");
export const canTiming = (roles: string[]) =>
  roles.includes("admin") || roles.includes("timing");

// Gemeinsamer Event-Selector (Liste laden, robuste Auswahl).
export function useEventSelector() {
  const [events, setEvents] = useState<EventDto[]>([]);
  const [eventId, setEventId] = useState("");
  const loadEvents = (selectId?: string) =>
    api.listEvents().then((e) => {
      setEvents(e);
      setEventId((cur) => {
        if (selectId) return selectId;
        if (cur && e.some((x) => x.id === cur)) return cur;
        return e[0]?.id ?? "";
      });
    });
  useEffect(() => {
    loadEvents();
  }, []);
  return { events, eventId, setEventId, loadEvents };
}

export function EventSelect({
  events,
  eventId,
  onChange,
}: {
  events: EventDto[];
  eventId: string;
  onChange: (id: string) => void;
}) {
  const { t } = useI18n();
  return (
    <label>
      {t("register.event")}
      <select value={eventId} onChange={(e) => onChange(e.target.value)}>
        {events.map((ev) => (
          <option key={ev.id} value={ev.id}>{ev.name} ({ev.year})</option>
        ))}
      </select>
    </label>
  );
}

// --- Voll-Bearbeitung einer Anmeldung --------------------------------------
type EditForm = {
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  language: string;
  team: string;
  tshirt: string;
  consent_data: boolean;
  consent_publish: boolean;
  status: string;
  bib_number: string;
  competition_id: string;
  payment_method: string;
  payment_status: string;
};

export function EditRegistration({
  id,
  lang,
  onClose,
  onSaved,
}: {
  id: string;
  lang: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<AdminRegistrationDetail | null>(null);
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [form, setForm] = useState<EditForm | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .getRegistration(id)
      .then((d) => {
        setDetail(d);
        setForm({
          first_name: d.first_name,
          last_name: d.last_name,
          birth_date: d.birth_date,
          gender: d.gender,
          email: d.email,
          language: d.language,
          team: d.team ?? "",
          tshirt: d.tshirt ?? "",
          consent_data: d.consent_data,
          consent_publish: d.consent_publish,
          status: d.status,
          bib_number: d.bib_number != null ? String(d.bib_number) : "",
          competition_id: d.competition_id,
          payment_method: d.payment_method ?? "",
          payment_status: d.payment_status ?? "",
        });
        return api.listCompetitions(d.event_id);
      })
      .then((c) => c && setCompetitions(c))
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }, [id]);

  if (error && (!detail || !form))
    return (
      <div className="card">
        <p className="error">{error}</p>
        <button onClick={onClose}>{t("admin.cancel")}</button>
      </div>
    );
  if (!detail || !form) return <div className="card">{t("common.loading")}</div>;

  const set = (patch: Partial<EditForm>) => setForm({ ...form, ...patch });
  const compLabel = (c: CompetitionDto) =>
    c.title_i18n?.[lang] || "Lauf";

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const body: AdminRegistrationUpdate = {
      first_name: form.first_name,
      last_name: form.last_name,
      birth_date: form.birth_date,
      gender: form.gender,
      email: form.email,
      language: form.language,
      team: form.team,
      tshirt: form.tshirt,
      consent_data: form.consent_data,
      consent_publish: form.consent_publish,
      status: form.status,
      competition_id: form.competition_id,
      bib_number: form.bib_number === "" ? undefined : Number(form.bib_number),
      payment_method: form.payment_method || undefined,
      payment_status: form.payment_status || undefined,
    };
    try {
      await adminApi.updateRegistration(id, body);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  };

  return (
    <form className="card edit-panel" onSubmit={save}>
      <div className="admin-head">
        <h3>{t("admin.editTitle")}</h3>
        <button type="button" onClick={onClose}>
          {t("admin.cancel")}
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="row">
        <label>
          {t("register.firstName")}
          <input value={form.first_name} onChange={(e) => set({ first_name: e.target.value })} required />
        </label>
        <label>
          {t("register.lastName")}
          <input value={form.last_name} onChange={(e) => set({ last_name: e.target.value })} required />
        </label>
      </div>

      <div className="row">
        <label>
          {t("register.birthDate")}
          <input type="date" value={form.birth_date} onChange={(e) => set({ birth_date: e.target.value })} required />
        </label>
        <label>
          {t("register.gender")}
          <select value={form.gender} onChange={(e) => set({ gender: e.target.value })}>
            <option value="f">{t("register.gender.f")}</option>
            <option value="m">{t("register.gender.m")}</option>
            <option value="x">{t("register.gender.x")}</option>
          </select>
        </label>
      </div>

      <label>
        {t("register.email")}
        <input type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} required />
      </label>

      <div className="row">
        <label>
          {t("admin.language")}
          <select value={form.language} onChange={(e) => set({ language: e.target.value })}>
            <option value="de">DE</option>
            <option value="en">EN</option>
          </select>
        </label>
        <label>
          {t("register.team")}
          <TeamInput value={form.team} onChange={(v) => set({ team: v })} />
        </label>
        <label>
          {t("register.tshirt")}
          <select value={form.tshirt} onChange={(e) => set({ tshirt: e.target.value })}>
            <option value="">–</option>
            {detail.tshirt_options.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="row">
        <label>
          {t("register.competition")}
          <select value={form.competition_id} onChange={(e) => set({ competition_id: e.target.value })}>
            {competitions.map((c) => (
              <option key={c.id} value={c.id}>{compLabel(c)}</option>
            ))}
          </select>
        </label>
        <label>
          {t("admin.bib")}
          <input type="number" value={form.bib_number} onChange={(e) => set({ bib_number: e.target.value })} />
        </label>
      </div>

      <div className="row">
        <label>
          {t("admin.status")}
          <select value={form.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="confirmed">{t("regstatus.confirmed")}</option>
            <option value="cancelled">{t("regstatus.cancelled")}</option>
          </select>
        </label>
        <label>
          {t("admin.paymentMethod")}
          <select value={form.payment_method} onChange={(e) => set({ payment_method: e.target.value })}>
            <option value="on_site">{t("pay.method.on_site")}</option>
            <option value="sepa_debit">{t("pay.method.sepa_debit")}</option>
          </select>
        </label>
        <label>
          {t("admin.paymentStatus")}
          <select value={form.payment_status} onChange={(e) => set({ payment_status: e.target.value })}>
            <option value="pending">{t("pay.status.pending")}</option>
            <option value="paid">{t("pay.status.paid")}</option>
            <option value="cancelled">{t("pay.status.cancelled")}</option>
          </select>
        </label>
      </div>

      {detail.payment_iban_masked && (
        <p className="hint">{t("manage.iban")}: {detail.payment_iban_masked}</p>
      )}

      <label className="check">
        <input type="checkbox" checked={form.consent_data} onChange={(e) => set({ consent_data: e.target.checked })} />
        {t("register.consentData")}
      </label>
      <label className="check">
        <input type="checkbox" checked={form.consent_publish} onChange={(e) => set({ consent_publish: e.target.checked })} />
        {t("register.consentPublish")}
      </label>

      <button className="primary" type="submit">{t("manage.save")}</button>
    </form>
  );
}

// --- Strecken / Startzeiten -------------------------------------------------
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function CompetitionSettings({ eventId, lang }: { eventId: string; lang: string }) {
  const { t } = useI18n();
  const [comps, setComps] = useState<CompetitionDto[]>([]);

  const reload = () => api.listCompetitions(eventId).then(setComps);
  useEffect(() => {
    reload();
  }, [eventId]);

  return (
    <>
      <h3>{t("admin.competitions")}</h3>
      <table className="results">
        <thead>
          <tr>
            <th>{t("admin.competition")}</th>
            <th>{t("admin.startTime")}</th>
            <th>{t("admin.priceAdult")}</th>
            <th>{t("admin.priceJunior")}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {comps.map((c) => (
            <CompetitionRow key={c.id} comp={c} lang={lang} onSaved={reload} />
          ))}
        </tbody>
      </table>
    </>
  );
}

function CompetitionRow({
  comp,
  lang,
  onSaved,
}: {
  comp: CompetitionDto;
  lang: string;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState(toLocalInput(comp.start_time));
  const [priceAdult, setPriceAdult] = useState((comp.price_cents / 100).toFixed(2));
  const [priceJunior, setPriceJunior] = useState(
    comp.price_junior_cents != null ? (comp.price_junior_cents / 100).toFixed(2) : ""
  );
  const [saved, setSaved] = useState(false);
  const label = comp.title_i18n?.[lang] || t("register.laps", { n: comp.lap_count });
  const touch = () => setSaved(false);

  const save = async () => {
    await adminApi.updateCompetition(comp.id, {
      start_time: value ? new Date(value).toISOString() : null,
      price_cents: Math.round(Number(priceAdult) * 100),
      price_junior_cents: priceJunior === "" ? null : Math.round(Number(priceJunior) * 100),
    });
    setSaved(true);
    onSaved();
  };

  return (
    <tr>
      <td>{label}</td>
      <td>
        <input
          type="datetime-local"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            touch();
          }}
        />
      </td>
      <td>
        <input
          type="number"
          step="0.01"
          style={{ width: 80 }}
          value={priceAdult}
          onChange={(e) => {
            setPriceAdult(e.target.value);
            touch();
          }}
        />
      </td>
      <td>
        <input
          type="number"
          step="0.01"
          style={{ width: 80 }}
          placeholder="–"
          value={priceJunior}
          onChange={(e) => {
            setPriceJunior(e.target.value);
            touch();
          }}
        />
      </td>
      <td>
        <button onClick={save}>{t("manage.save")}</button>
        {saved && " ✓"}
      </td>
    </tr>
  );
}

// --- Interne Ergebnisliste (inkl. nicht-veröffentlichter Läufer) -----------
export function InternalResults({ eventId, lang }: { eventId: string; lang: string }) {
  const { t } = useI18n();
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [competitionId, setCompetitionId] = useState("");
  const [data, setData] = useState<ResultList | null>(null);

  useEffect(() => {
    setCompetitionId("");
    setData(null);
    api.listCompetitions(eventId).then(setCompetitions);
  }, [eventId]);

  useEffect(() => {
    if (competitionId) adminApi.internalResults(eventId, competitionId).then(setData).catch(() => {});
    else setData(null);
  }, [competitionId, eventId]);

  const compLabel = (c: CompetitionDto) =>
    c.title_i18n?.[lang] || t("register.laps", { n: c.lap_count });

  return (
    <>
      <h3>{t("admin.internalResults")}</h3>
      <select value={competitionId} onChange={(e) => setCompetitionId(e.target.value)}>
        <option value="">{t("common.choose")}</option>
        {competitions.map((c) => (
          <option key={c.id} value={c.id}>{compLabel(c)}</option>
        ))}
      </select>
      {data && data.rows.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>{t("results.rank")}</th>
              <th>{t("results.bib")}</th>
              <th>{t("results.name")}</th>
              <th>{t("results.time")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.bib_number} className={r.finish_seconds == null ? "dnf" : ""}>
                <td>{r.rank ?? t("results.dnf")}</td>
                <td>{r.bib_number}</td>
                <td>{r.first_name} {r.last_name}</td>
                <td>{r.finish_seconds == null ? t("results.dnf") : formatTime(r.finish_seconds)}</td>
                <td>
                  {r.published === false && <span className="badge">{t("admin.notPublic")}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

// --- Geräte-Tokens für die Zeitnahme ---------------------------------------
export function DeviceTokens({ eventId }: { eventId: string }) {
  const { t } = useI18n();
  const [tokens, setTokens] = useState<DeviceTokenDto[]>([]);
  const [label, setLabel] = useState("");
  const [offset, setOffset] = useState(0);

  const reload = () => adminApi.listDeviceTokens(eventId).then(setTokens).catch(() => {});
  useEffect(() => {
    reload();
  }, [eventId]);

  const create = async () => {
    await adminApi.createDeviceToken(eventId, label, offset);
    setLabel("");
    setOffset(0);
    reload();
  };

  return (
    <>
      <h3>{t("admin.deviceTokens")}</h3>
      <div className="row">
        <input placeholder={t("admin.tokenLabel")} value={label} onChange={(e) => setLabel(e.target.value)} />
        <input
          type="number"
          placeholder={t("admin.offset")}
          value={offset}
          onChange={(e) => setOffset(Number(e.target.value))}
          style={{ width: 120 }}
        />
        <button className="primary" onClick={create} disabled={!label}>
          {t("admin.create")}
        </button>
      </div>

      {tokens.map((tok) => (
        <div key={tok.id} className={`token-created${tok.active ? "" : " dnf"}`}>
          <p>
            <strong>{tok.label}</strong> · {tok.time_offset_seconds}s
            {!tok.active && ` · ${t("admin.tokenRevoked")}`}
          </p>
          {tok.token && <code>{tok.token}</code>}
          {tok.active && tok.token && (
            <>
              <QRCodeSVG
                value={`${window.location.origin}/team/zeiterfassung?token=${encodeURIComponent(tok.token)}&event=${eventId}`}
                size={160}
              />
              <p className="hint">{t("admin.tokenScan")}</p>
            </>
          )}
          {tok.active && (
            <button onClick={() => adminApi.revokeDeviceToken(tok.id).then(reload)}>
              {t("admin.revoke")}
            </button>
          )}
        </div>
      ))}
    </>
  );
}
