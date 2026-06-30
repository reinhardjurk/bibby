import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  adminApi,
  adminToken,
  api,
  formatTime,
  type AdminRegistration,
  type CompetitionDto,
  type DeviceTokenDto,
  type EventDto,
  type ResultList,
} from "../api";
import { useI18n } from "../i18n";

export function AdminPage() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const [authed, setAuthed] = useState<boolean | null>(null);
  const [roles, setRoles] = useState<string[]>([]);

  // Token aus dem Magic-Link übernehmen, dann Session prüfen.
  useEffect(() => {
    const urlToken = params.get("token");
    if (urlToken) {
      adminToken.set(urlToken);
      navigate("/admin", { replace: true });
    }
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

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard />;

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

function LoginCard() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await adminApi.login(email);
      setSent(true);
    } catch {
      setError(t("common.error"));
    }
  };

  return (
    <form className="card" onSubmit={submit}>
      <h2>{t("admin.login")}</h2>
      {error && <p className="error">{error}</p>}
      {sent ? (
        <p className="success">{t("admin.loginSent")}</p>
      ) : (
        <>
          <label>
            {t("register.email")}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <button className="primary" type="submit">
            {t("admin.login")}
          </button>
        </>
      )}
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
  const [events, setEvents] = useState<EventDto[]>([]);
  const [eventId, setEventId] = useState("");
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [regs, setRegs] = useState<AdminRegistration[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      if (e[0]) setEventId(e[0].id);
    });
  }, []);

  const reload = () => {
    if (!eventId) return;
    api.listCompetitions(eventId).then(setCompetitions);
    adminApi
      .listRegistrations(eventId)
      .then(setRegs)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  };
  useEffect(reload, [eventId]);

  const compLabel = (c: CompetitionDto) => c.title_i18n?.[lang] || t("register.laps", { n: c.lap_count });

  const act = async (fn: () => Promise<unknown>) => {
    setError("");
    try {
      await fn();
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <>
      <label>
        {t("register.event")}
        <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
          {events.map((ev) => (
            <option key={ev.id} value={ev.id}>
              {ev.name} ({ev.year})
            </option>
          ))}
        </select>
      </label>

      {error && <p className="error">{error}</p>}

      <h3>{t("admin.registrations")}</h3>
      <table className="results">
        <thead>
          <tr>
            <th>{t("admin.bib")}</th>
            <th>{t("admin.name")}</th>
            <th>{t("admin.competition")}</th>
            <th>{t("admin.payment")}</th>
            <th>{t("admin.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {regs.map((r) => (
            <tr key={r.id}>
              <td>
                {canManage ? (
                  <BibEditor
                    value={r.bib_number}
                    onSet={(n) => act(() => adminApi.assignBib(r.id, n))}
                  />
                ) : (
                  (r.bib_number ?? "–")
                )}
              </td>
              <td>
                {r.first_name} {r.last_name}
              </td>
              <td>
                {canManage ? (
                  <select
                    value={r.competition_id}
                    onChange={(e) => act(() => adminApi.reassign(r.id, e.target.value))}
                  >
                    {competitions.map((c) => (
                      <option key={c.id} value={c.id}>
                        {compLabel(c)}
                      </option>
                    ))}
                  </select>
                ) : (
                  t("register.laps", { n: r.lap_count })
                )}
              </td>
              <td>
                {r.payment_method ? t(`pay.method.${r.payment_method}`) : "–"} ·{" "}
                {r.payment_status ? t(`pay.status.${r.payment_status}`) : "–"}
              </td>
              <td>
                {canManage && r.payment_status !== "paid" && (
                  <button onClick={() => act(() => adminApi.markPaid(r.id))}>
                    {t("admin.markPaid")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {eventId && (
        <InternalResults eventId={eventId} competitions={competitions} lang={lang} />
      )}

      {canTiming && eventId && <DeviceTokens eventId={eventId} />}
    </>
  );
}

function InternalResults({
  eventId,
  competitions,
  lang,
}: {
  eventId: string;
  competitions: CompetitionDto[];
  lang: string;
}) {
  const { t } = useI18n();
  const [competitionId, setCompetitionId] = useState("");
  const [data, setData] = useState<ResultList | null>(null);

  useEffect(() => {
    setCompetitionId("");
    setData(null);
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
          <option key={c.id} value={c.id}>
            {compLabel(c)}
          </option>
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

function BibEditor({ value, onSet }: { value: number | null; onSet: (n: number) => void }) {
  const [edit, setEdit] = useState(false);
  const [n, setN] = useState(value ?? 0);
  if (!edit)
    return (
      <span onClick={() => setEdit(true)} className="bib-edit" title="bearbeiten">
        {value ?? "–"} ✎
      </span>
    );
  return (
    <span>
      <input
        type="number"
        style={{ width: 70 }}
        value={n}
        onChange={(e) => setN(Number(e.target.value))}
      />
      <button
        onClick={() => {
          onSet(n);
          setEdit(false);
        }}
      >
        OK
      </button>
    </span>
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
