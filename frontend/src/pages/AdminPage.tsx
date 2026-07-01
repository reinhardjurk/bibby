import { useEffect, useState, type FormEvent } from "react";
import {
  adminApi,
  adminToken,
  api,
  formatTime,
  type AdminRegistration,
  type AdminRegistrationDetail,
  type AdminRegistrationUpdate,
  type CompetitionDto,
  type DeviceTokenDto,
  type EventDto,
  type ResultList,
} from "../api";
import { TeamInput } from "../components/TeamInput";
import { useI18n } from "../i18n";

export function AdminPage() {
  const { t, lang } = useI18n();
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

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  const has = (role: string) => roles.includes("admin") || roles.includes(role);

  return (
    <div className="card">
      <div className="admin-head">
        <h2>{t("admin.title")}</h2>
        <div>
          <span className="badge">{roles.join(", ")}</span>{" "}
          <button
            onClick={() => {
              adminToken.clear();
              setAuthed(false);
            }}
          >
            {t("admin.logout")}
          </button>
        </div>
      </div>
      <Dashboard canManage={has("race_office")} canTiming={has("timing")} lang={lang} />
    </div>
  );
}

function LoginCard({ onAuthed }: { onAuthed: (roles: string[]) => void }) {
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

function Dashboard({
  canManage,
  canTiming,
  lang,
}: {
  canManage: boolean;
  canTiming: boolean;
  lang: string;
}) {
  const { t } = useI18n();
  const PAGE = 50;
  const [events, setEvents] = useState<EventDto[]>([]);
  const [eventId, setEventId] = useState("");
  const [regs, setRegs] = useState<AdminRegistration[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      if (e[0]) setEventId(e[0].id);
    });
  }, []);

  const reload = () => {
    if (!eventId) return;
    adminApi
      .listRegistrations(eventId, q, PAGE, offset)
      .then((res) => {
        setRegs(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  };
  // Nur die aktuelle Seite laden; Suche mit kleiner Entprellung.
  useEffect(() => {
    if (!eventId) return;
    const h = setTimeout(reload, 250);
    return () => clearTimeout(h);
  }, [eventId, q, offset]);

  return (
    <>
      <label>
        {t("register.event")}
        <select
          value={eventId}
          onChange={(e) => {
            setEventId(e.target.value);
            setOffset(0);
          }}
        >
          {events.map((ev) => (
            <option key={ev.id} value={ev.id}>
              {ev.name} ({ev.year})
            </option>
          ))}
        </select>
      </label>

      <h3>{t("admin.registrations")}</h3>
      <input
        placeholder={t("admin.search")}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOffset(0);
        }}
      />
      {error && <p className="error">{error}</p>}

      <table className="results">
        <thead>
          <tr>
            <th>{t("admin.bib")}</th>
            <th>{t("admin.name")}</th>
            <th>{t("admin.competition")}</th>
            <th>{t("admin.payment")}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {regs.map((r) => (
            <tr key={r.id}>
              <td>{r.bib_number ?? "–"}</td>
              <td>
                {r.first_name} {r.last_name}
              </td>
              <td>{t("register.laps", { n: r.lap_count })}</td>
              <td>
                {r.payment_method ? t(`pay.method.${r.payment_method}`) : "–"} ·{" "}
                {r.payment_status ? t(`pay.status.${r.payment_status}`) : "–"}
              </td>
              <td>
                {canManage && (
                  <button onClick={() => setEditingId(r.id)}>{t("admin.edit")}</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="pager">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          {t("admin.prev")}
        </button>
        <span className="hint">
          {t("admin.showing", {
            from: total === 0 ? 0 : offset + 1,
            to: offset + regs.length,
            total,
          })}
        </span>
        <button disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
          {t("admin.next")}
        </button>
      </div>

      {editingId && (
        <EditRegistration
          id={editingId}
          lang={lang}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            reload();
          }}
        />
      )}

      {eventId && <InternalResults eventId={eventId} lang={lang} />}
      {canTiming && eventId && <DeviceTokens eventId={eventId} />}
    </>
  );
}

type EditForm = {
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  language: string;
  team: string;
  consent_data: boolean;
  consent_publish: boolean;
  status: string;
  bib_number: string;
  competition_id: string;
  payment_method: string;
  payment_status: string;
};

function EditRegistration({
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

  if (!detail || !form) return <div className="card">{t("common.loading")}</div>;

  const set = (patch: Partial<EditForm>) => setForm({ ...form, ...patch });
  const compLabel = (c: CompetitionDto) =>
    c.title_i18n?.[lang] || t("register.laps", { n: c.lap_count });

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
          <input
            type="number"
            value={form.bib_number}
            onChange={(e) => set({ bib_number: e.target.value })}
          />
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

function InternalResults({ eventId, lang }: { eventId: string; lang: string }) {
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
                <td>
                  {r.first_name} {r.last_name}
                </td>
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

function DeviceTokens({ eventId }: { eventId: string }) {
  const { t } = useI18n();
  const [tokens, setTokens] = useState<DeviceTokenDto[]>([]);
  const [label, setLabel] = useState("");
  const [offset, setOffset] = useState(0);
  const [created, setCreated] = useState<string | null>(null);

  const reload = () => adminApi.listDeviceTokens(eventId).then(setTokens).catch(() => {});
  useEffect(() => {
    reload();
  }, [eventId]);

  const create = async () => {
    const tok = await adminApi.createDeviceToken(eventId, label, offset);
    setCreated(tok.token ?? null);
    setLabel("");
    setOffset(0);
    reload();
  };

  return (
    <>
      <h3>{t("admin.deviceTokens")}</h3>
      {created && (
        <p className="success">
          {t("admin.tokenCreated")}: <code>{created}</code>
        </p>
      )}
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
      <table className="results">
        <tbody>
          {tokens.map((tok) => (
            <tr key={tok.id} className={tok.active ? "" : "dnf"}>
              <td>{tok.label}</td>
              <td>{tok.time_offset_seconds}s</td>
              <td>
                {tok.active && (
                  <button onClick={() => adminApi.revokeDeviceToken(tok.id).then(reload)}>
                    {t("admin.revoke")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
