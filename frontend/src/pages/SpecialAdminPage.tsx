import { useEffect, useState } from "react";
import {
  adminApi,
  formatTime,
  type AdminRegistration,
  type MailSettings,
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
    <AdminChrome title={t("special.title")} roles={roles} logout={logout}>
      <SpecialDashboard roles={roles} lang={lang} />
    </AdminChrome>
  );
}

function SpecialDashboard({ roles, lang }: { roles: string[]; lang: string }) {
  const { events, eventId, setEventId } = useEventSelector();
  const mng = canManageRoles(roles);
  const tim = canTimingRoles(roles);

  return (
    <>
      <MailModeToggle roles={roles} />
      <EventSelect events={events} eventId={eventId} onChange={setEventId} />

      {eventId && <RegistrationsList eventId={eventId} canManage={mng} />}
      {eventId && <CaptureLookup eventId={eventId} canTiming={tim} />}
      {eventId && <InternalResults eventId={eventId} lang={lang} />}
      {tim && eventId && <DeviceTokens eventId={eventId} />}
    </>
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

function RegistrationsList({ eventId, canManage }: { eventId: string; canManage: boolean }) {
  const { t, lang } = useI18n();
  const PAGE = 50;
  const [regs, setRegs] = useState<AdminRegistration[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [recMsg, setRecMsg] = useState("");
  const [recBusy, setRecBusy] = useState(false);

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
  }, [eventId, q, offset]);
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
      {canManage && (
        <p>
          <button
            className="primary"
            disabled={recBusy}
            onClick={async () => {
              setRecBusy(true);
              setRecMsg("");
              try {
                const r = await adminApi.recomputeTimes(eventId);
                setRecMsg(t("admin.recomputed", { n: r.updated }));
                reload();
              } catch (e) {
                setError(e instanceof Error ? e.message : t("common.error"));
              } finally {
                setRecBusy(false);
              }
            }}
          >
            {recBusy ? t("common.loading") : t("admin.recompute")}
          </button>{" "}
          {recMsg && <span className="hint">{recMsg}</span>}
        </p>
      )}
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
              <td>{r.competition_title?.[lang] || t("register.laps", { n: r.lap_count })}</td>
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

  const search = async () => {
    if (!bib) return;
    setError("");
    setEditId(null);
    try {
      setRows(await adminApi.listTimings(eventId, Number(bib)));
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
      {rows && rows.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>{t("special.time")}</th>
              <th>{t("special.lap")}</th>
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
                  <td>{r.lap_index ?? "–"}</td>
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
                  <td>{r.lap_index ?? "–"}</td>
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
