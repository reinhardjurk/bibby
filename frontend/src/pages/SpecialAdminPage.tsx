import { useEffect, useState } from "react";
import {
  adminApi,
  formatTime,
  STAFF_ROLES,
  type AdminRegistration,
  type AdminUser,
  type MailSettings,
  type MailTexts,
  type TimingRow,
} from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  canManage as canManageRoles,
  canTiming as canTimingRoles,
  DeviceTokens,
  EventSelect,
  InternalResults,
  LoginCard,
  useAdminSession,
  useEventSelector,
} from "./adminShared";

export function SpecialAdminPage() {
  const { t, lang } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome title={t("special.title")} roles={roles} logout={logout} allow={["race_office", "timing"]}>
      <SpecialDashboard roles={roles} lang={lang} />
    </AdminChrome>
  );
}

function SpecialDashboard({ roles, lang }: { roles: string[]; lang: string }) {
  const { events, eventId, setEventId } = useEventSelector();
  const mng = canManageRoles(roles);
  const tim = canTimingRoles(roles);
  // Trigger, mit dem der Recompute-Button die Anmeldungsliste neu laden lässt.
  const [refresh, setRefresh] = useState(0);

  return (
    <>
      <EventSelect events={events} eventId={eventId} onChange={setEventId} />

      {eventId && <RegistrationsList eventId={eventId} refresh={refresh} />}
      {eventId && <CaptureLookup eventId={eventId} canTiming={tim} />}
      {mng && eventId && (
        <RecomputeTimes eventId={eventId} onDone={() => setRefresh((n) => n + 1)} />
      )}
      {eventId && <InternalResults eventId={eventId} lang={lang} />}
      {tim && eventId && <DeviceTokens eventId={eventId} />}
      <MailModeToggle roles={roles} />
      {mng && <MailTextsEditor />}
      {roles.includes("admin") && <UserAdmin />}
      <BuildInfo />
    </>
  );
}

/** Versions-/Build-Anzeige ganz unten: Frontend-Build, Backend-Build, DB-Schema. */
function BuildInfo() {
  const [backend, setBackend] = useState("?");
  const [dbSchema, setDbSchema] = useState("?");

  useEffect(() => {
    adminApi
      .version()
      .then((v) => {
        setBackend(v.backend);
        setDbSchema(v.db_schema ?? "?");
      })
      .catch(() => {
        setBackend("?");
        setDbSchema("?");
      });
  }, []);

  return (
    <p className="build-info">
      Frontend {__APP_BUILD__} · Backend {backend} · DB {dbSchema}
    </p>
  );
}

/** "Alle Laufzeiten berechnen" – eigener Block; stößt danach ein Reload der
 *  Anmeldungsliste an (über den refresh-Trigger im Dashboard). */
function RecomputeTimes({ eventId, onDone }: { eventId: string; onDone: () => void }) {
  const { t } = useI18n();
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  return (
    <section className="card">
      <button
        className="primary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setMsg("");
          setError("");
          try {
            const r = await adminApi.recomputeTimes(eventId);
            setMsg(t("admin.recomputed", { n: r.updated }));
            onDone();
          } catch (e) {
            setError(e instanceof Error ? e.message : t("common.error"));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? t("common.loading") : t("admin.recompute")}
      </button>{" "}
      {msg && <span className="hint">{msg}</span>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

/** Laufzeit-Schalter Test-/Live-Mailversand (Änderung nur für Admin). */
function MailModeToggle({ roles }: { roles: string[] }) {
  const { t } = useI18n();
  const isAdmin = roles.includes("admin");
  const [ms, setMs] = useState<MailSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    adminApi.getMailSettings().then(setMs).catch((e) => setErr(String(e)));
  }, []);

  async function toggle() {
    if (!ms) return;
    const next = !ms.test_mode;
    // Von Test -> Live: bewusst bestätigen (dann gehen Mails an echte Empfänger!).
    if (!next && !window.confirm(t("mail.confirmLive"))) return;
    setBusy(true);
    setErr(null);
    try {
      setMs(await adminApi.setMailMode(next));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h3>{t("mail.title")}</h3>
      {err && <p className="error">{err}</p>}
      {ms && (
        <>
          <p>
            {ms.test_mode ? (
              <>
                <span className="badge">{t("mail.stateTest")}</span>{" "}
                {t("mail.testHint", { recipient: ms.test_recipient })}
              </>
            ) : (
              <>
                <span className="badge badge-live">{t("mail.stateLive")}</span>{" "}
                {t("mail.liveHint")}
              </>
            )}
          </p>
          {isAdmin ? (
            <button onClick={toggle} disabled={busy}>
              {ms.test_mode ? t("mail.switchToLive") : t("mail.switchToTest")}
            </button>
          ) : (
            <p className="hint">{t("mail.adminOnly")}</p>
          )}
        </>
      )}
    </section>
  );
}

/** Betreff + Text der Anmeldebestätigung (DE/EN) zur Laufzeit bearbeiten. */
function MailTextsEditor() {
  const { t } = useI18n();
  const [texts, setTexts] = useState<MailTexts | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    adminApi.getMailTexts().then(setTexts).catch((e) => setErr(String(e)));
  }, []);

  const set = (patch: Partial<MailTexts>) => {
    setTexts((cur) => (cur ? { ...cur, ...patch } : cur));
    setMsg("");
  };

  const save = async () => {
    if (!texts) return;
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      setTexts(await adminApi.setMailTexts(texts));
      setMsg(t("mailText.saved"));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h3>{t("mailText.title")}</h3>
      <p className="hint">{t("mailText.hint")}</p>
      {err && <p className="error">{err}</p>}
      {texts && (
        <>
          <label>
            {t("mailText.subjectDe")}
            <input value={texts.subject_de} onChange={(e) => set({ subject_de: e.target.value })} />
          </label>
          <label>
            {t("mailText.bodyDe")}
            <textarea rows={5} value={texts.body_de} onChange={(e) => set({ body_de: e.target.value })} />
          </label>
          <label>
            {t("mailText.subjectEn")}
            <input value={texts.subject_en} onChange={(e) => set({ subject_en: e.target.value })} />
          </label>
          <label>
            {t("mailText.bodyEn")}
            <textarea rows={5} value={texts.body_en} onChange={(e) => set({ body_en: e.target.value })} />
          </label>
          <button className="primary" onClick={save} disabled={busy}>
            {t("manage.save")}
          </button>
          {msg && <span className="hint"> {msg}</span>}
        </>
      )}
    </section>
  );
}

const ALL_ROLES = STAFF_ROLES;

/** Benutzerverwaltung (nur admin): Nutzer anlegen, Rollen/aktiv setzen, Passwort
 *  zuruecksetzen. Der eigene Zugang laesst sich nicht deaktivieren/entadminen. */
function UserAdmin() {
  const { t } = useI18n();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [err, setErr] = useState("");

  const load = () =>
    adminApi.listUsers().then(setUsers).catch((e) => setErr(String(e)));
  useEffect(() => {
    load();
  }, []);

  return (
    <section className="card">
      <h3>{t("users.title")}</h3>
      <p className="hint">{t("users.hint")}</p>
      {err && <p className="error">{err}</p>}
      <div className="table-scroll">
        <table className="results">
          <thead>
            <tr>
              <th>{t("users.email")}</th>
              <th>{t("users.name")}</th>
              <th>{t("users.roles")}</th>
              <th>{t("users.active")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <UserRow key={u.id} user={u} onSaved={load} />
            ))}
          </tbody>
        </table>
      </div>
      <NewUser onCreated={load} />
    </section>
  );
}

function roleLabel(t: (k: string) => string, role: string) {
  return t(`role.${role}`);
}

function UserRow({ user, onSaved }: { user: AdminUser; onSaved: () => void }) {
  const { t } = useI18n();
  const [roles, setRoles] = useState<string[]>(user.roles);
  const [active, setActive] = useState(user.active);
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const toggleRole = (r: string) =>
    setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const save = async () => {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      await adminApi.updateUser(user.id, {
        active,
        roles,
        password: pw || undefined,
      });
      setPw("");
      setMsg("✓");
      onSaved();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <tr className={active ? "" : "dnf"}>
      <td>{user.email}</td>
      <td>{user.name}</td>
      <td>
        {ALL_ROLES.map((r) => (
          <label key={r} className="check" style={{ display: "inline-flex", marginRight: 10 }}>
            <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleRole(r)} />
            {roleLabel(t, r)}
          </label>
        ))}
      </td>
      <td style={{ textAlign: "center" }}>
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
      </td>
      <td>
        <input
          type="password"
          placeholder={t("users.newPassword")}
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          style={{ width: 130 }}
        />{" "}
        <button className="primary" onClick={save} disabled={busy}>
          {t("manage.save")}
        </button>{" "}
        {msg && <span className="hint">{msg}</span>}
        {err && <span className="error">{err}</span>}
      </td>
    </tr>
  );
}

function NewUser({ onCreated }: { onCreated: () => void }) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [pw, setPw] = useState("");
  const [roles, setRoles] = useState<string[]>(["race_office"]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const toggleRole = (r: string) =>
    setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const create = async () => {
    setBusy(true);
    setErr("");
    try {
      await adminApi.createUser({ email, name: name || email, password: pw, roles });
      setEmail("");
      setName("");
      setPw("");
      setRoles(["race_office"]);
      onCreated();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h4>{t("users.new")}</h4>
      {err && <p className="error">{err}</p>}
      <div className="row">
        <label>
          {t("users.email")}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          {t("users.name")}
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          {t("users.password")}
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
        </label>
      </div>
      <div>
        {ALL_ROLES.map((r) => (
          <label key={r} className="check" style={{ display: "inline-flex", marginRight: 10 }}>
            <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleRole(r)} />
            {roleLabel(t, r)}
          </label>
        ))}
      </div>
      <button
        className="primary"
        onClick={create}
        disabled={busy || !email || pw.length < 6}
      >
        {t("users.create")}
      </button>
    </>
  );
}

function RegistrationsList({ eventId, refresh }: { eventId: string; refresh: number }) {
  const { t, lang } = useI18n();
  const PAGE = 50;
  const [regs, setRegs] = useState<AdminRegistration[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  const reload = () => {
    adminApi
      .listRegistrations(eventId, q, PAGE, offset)
      .then((res) => {
        setRegs(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  };
  useEffect(() => {
    const h = setTimeout(reload, 250);
    return () => clearTimeout(h);
  }, [eventId, q, offset, refresh]);
  useEffect(() => {
    setOffset(0);
  }, [eventId]);

  return (
    <>
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
            <th>{t("admin.race")}</th>
            <th>{t("admin.time")}</th>
            <th>{t("admin.payment")}</th>
          </tr>
        </thead>
        <tbody>
          {regs.map((r) => (
            <tr key={r.id}>
              <td>{r.bib_number ?? "–"}</td>
              <td>{r.first_name} {r.last_name}</td>
              <td>{r.competition_title?.[lang] || "Lauf"}</td>
              <td>{r.finish_seconds == null ? "–" : formatTime(r.finish_seconds)}</td>
              <td>
                {r.payment_method ? t(`pay.method.${r.payment_method}`) : "–"} ·{" "}
                {r.payment_status ? t(`pay.status.${r.payment_status}`) : "–"}
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
    </>
  );
}

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/** Alle Erfassungen (timing_record) zu einer Startnummer anzeigen, korrigieren
 * oder löschen. */
function CaptureLookup({ eventId, canTiming }: { eventId: string; canTiming: boolean }) {
  const { t } = useI18n();
  const [bib, setBib] = useState("");
  const [rows, setRows] = useState<TimingRow[] | null>(null);
  const [error, setError] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [eTime, setETime] = useState("");
  const [eStatus, setEStatus] = useState("valid");
  const [eBib, setEBib] = useState("");
  const [addTime, setAddTime] = useState("");

  const search = async () => {
    if (!bib) return;
    setError("");
    setEditId(null);
    try {
      setRows(await adminApi.listTimings(eventId, Number(bib)));
      setAddTime(toLocalInput(new Date().toISOString())); // Vorbelegung: jetzt
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  const addCapture = async () => {
    if (!bib || !addTime) return;
    setError("");
    try {
      await adminApi.addTiming(eventId, Number(bib), new Date(addTime).toISOString());
      search();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  const startEdit = (r: TimingRow) => {
    setEditId(r.id);
    setETime(toLocalInput(r.absolute_time));
    setEStatus(["valid", "ignored", "manual"].includes(r.status) ? r.status : "valid");
    setEBib(bib);
  };

  const saveEdit = async () => {
    if (!editId) return;
    setError("");
    try {
      await adminApi.correctTiming(editId, {
        status: eStatus,
        bib_number: Number(eBib),
        absolute_time: new Date(eTime).toISOString(),
      });
      setEditId(null);
      search();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  const del = async (id: string) => {
    if (!window.confirm(t("special.confirmDelete"))) return;
    setError("");
    try {
      await adminApi.deleteTiming(id);
      search();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <>
      <h3>{t("special.captures")}</h3>
      <div className="row">
        <input
          inputMode="numeric"
          value={bib}
          onChange={(e) => setBib(e.target.value.replace(/\D/g, ""))}
          placeholder={t("admin.bib")}
        />
        <button className="primary" onClick={search} disabled={!bib}>
          {t("special.show")}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {rows && rows.length === 0 && <p>{t("special.noCaptures")}</p>}
      {rows !== null && canTiming && (
        <div className="row" style={{ marginTop: 8 }}>
          <input
            type="datetime-local"
            step={1}
            value={addTime}
            onChange={(e) => setAddTime(e.target.value)}
          />
          <button className="primary" onClick={addCapture} disabled={!addTime}>
            {t("special.addCapture")}
          </button>
        </div>
      )}
      {rows && rows.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>{t("special.time")}</th>
              <th>{t("special.status")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) =>
              editId === r.id ? (
                <tr key={r.id}>
                  <td>
                    <input
                      type="datetime-local"
                      step={1}
                      value={eTime}
                      onChange={(e) => setETime(e.target.value)}
                    />
                  </td>
                  <td>
                    <select value={eStatus} onChange={(e) => setEStatus(e.target.value)}>
                      <option value="valid">valid</option>
                      <option value="ignored">ignored</option>
                      <option value="manual">manual</option>
                    </select>
                  </td>
                  <td>
                    <label>
                      {t("admin.bib")}{" "}
                      <input
                        type="number"
                        style={{ width: 70 }}
                        value={eBib}
                        onChange={(e) => setEBib(e.target.value)}
                      />
                    </label>{" "}
                    <button onClick={saveEdit}>{t("manage.save")}</button>{" "}
                    <button type="button" onClick={() => setEditId(null)}>
                      {t("admin.cancel")}
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={r.id} className={r.status === "valid" || r.status === "manual" ? "" : "dnf"}>
                  <td>{new Date(r.absolute_time).toLocaleString()}</td>
                  <td>{r.status}</td>
                  <td>
                    {canTiming && (
                      <>
                        <button onClick={() => startEdit(r)}>{t("special.correct")}</button>{" "}
                        <button onClick={() => del(r.id)}>{t("special.delete")}</button>
                      </>
                    )}
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      )}
    </>
  );
}
