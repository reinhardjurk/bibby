import { useEffect, useState, type FormEvent } from "react";
import {
  adminApi,
  api,
  downloadSepaExport,
  formatTime,
  type AdminRegistration,
  type EventCreatePayload,
  type EventDto,
  type TimingRow,
} from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  canManage as canManageRoles,
  canTiming as canTimingRoles,
  CompetitionSettings,
  DeviceTokens,
  InternalResults,
  LoginCard,
  useAdminSession,
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
  const { t } = useI18n();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [eventId, setEventId] = useState("");
  const mng = canManageRoles(roles);
  const tim = canTimingRoles(roles);
  const isAdmin = roles.includes("admin");
  const [error, setError] = useState("");

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

  const delEvent = async () => {
    const ev = events.find((e) => e.id === eventId);
    if (!ev) return;
    if (!window.confirm(t("admin.deleteEventConfirm", { name: `${ev.name} (${ev.year})` }))) return;
    setError("");
    try {
      await adminApi.deleteEvent(eventId);
      await loadEvents();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <>
      {mng && <NewEvent onCreated={(id) => loadEvents(id)} />}
      {error && <p className="error">{error}</p>}

      <div className="row">
        <label>
          {t("register.event")}
          <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
            {events.map((ev) => (
              <option key={ev.id} value={ev.id}>{ev.name} ({ev.year})</option>
            ))}
          </select>
        </label>
        {isAdmin && eventId && (
          <button type="button" onClick={delEvent} style={{ alignSelf: "flex-end" }}>
            {t("admin.deleteEvent")}
          </button>
        )}
      </div>

      {eventId && <RegistrationsList eventId={eventId} canManage={mng} />}
      {eventId && <CaptureLookup eventId={eventId} canTiming={tim} />}
      {mng && eventId && <SepaExport eventId={eventId} />}
      {mng && eventId && <EventSettings eventId={eventId} />}
      {mng && eventId && <CompetitionSettings eventId={eventId} lang={lang} />}
      {eventId && <InternalResults eventId={eventId} lang={lang} />}
      {tim && eventId && <DeviceTokens eventId={eventId} />}
    </>
  );
}

function RegistrationsList({ eventId, canManage }: { eventId: string; canManage: boolean }) {
  const { t } = useI18n();
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
            <th>{t("admin.competition")}</th>
            <th>{t("admin.time")}</th>
            <th>{t("admin.payment")}</th>
          </tr>
        </thead>
        <tbody>
          {regs.map((r) => (
            <tr key={r.id}>
              <td>{r.bib_number ?? "–"}</td>
              <td>{r.first_name} {r.last_name}</td>
              <td>{t("register.laps", { n: r.lap_count })}</td>
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

type CompRow = { lap_count: string; title: string; price: string; priceJunior: string; startTime: string };
const emptyComp = (): CompRow => ({ lap_count: "", title: "", price: "", priceJunior: "", startTime: "" });

function NewEvent({ onCreated }: { onCreated: (id: string) => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [year, setYear] = useState("");
  const [date, setDate] = useState("");
  const [deadline, setDeadline] = useState("");
  const [defaultStart, setDefaultStart] = useState("");
  const [cutoff, setCutoff] = useState("");
  const [included, setIncluded] = useState(false);
  const [tshirtText, setTshirtText] = useState("");
  const [comps, setComps] = useState<CompRow[]>([{ ...emptyComp(), lap_count: "1" }]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const setComp = (i: number, patch: Partial<CompRow>) =>
    setComps(comps.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body: EventCreatePayload = {
        name,
        year: Number(year),
        event_date: date,
        registration_deadline: deadline ? new Date(deadline).toISOString() : null,
        default_start_time: defaultStart ? new Date(defaultStart).toISOString() : null,
        junior_cutoff_date: cutoff || null,
        tshirt_included: included,
        tshirt_options: tshirtText.trim()
          ? tshirtText.split("\n").map((s) => s.trim()).filter(Boolean)
          : null,
        competitions: comps.map((c) => ({
          lap_count: Number(c.lap_count),
          title: c.title || null,
          price_cents: Math.round(Number(c.price || 0) * 100),
          price_junior_cents: c.priceJunior === "" ? null : Math.round(Number(c.priceJunior) * 100),
          start_time: c.startTime ? new Date(c.startTime).toISOString() : null,
        })),
      };
      const res = await adminApi.createEvent(body);
      onCreated(res.id);
      setOpen(false);
      setName(""); setYear(""); setDate(""); setDeadline(""); setDefaultStart("");
      setCutoff(""); setIncluded(false); setTshirtText("");
      setComps([{ ...emptyComp(), lap_count: "1" }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <p>
        <button className="primary" onClick={() => setOpen(true)}>{t("admin.newEvent")}</button>
      </p>
    );
  }

  return (
    <form className="card edit-panel" onSubmit={submit}>
      <div className="admin-head">
        <h3>{t("admin.newEvent")}</h3>
        <button type="button" onClick={() => setOpen(false)}>{t("admin.cancel")}</button>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="row">
        <label>{t("admin.eventName")}<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label>{t("admin.eventYear")}<input type="number" value={year} onChange={(e) => setYear(e.target.value)} required /></label>
      </div>
      <div className="row">
        <label>{t("admin.eventDate")}<input type="date" value={date} onChange={(e) => setDate(e.target.value)} required /></label>
        <label>{t("admin.deadline")}<input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
      </div>
      <div className="row">
        <label>{t("admin.defaultStart")}<input type="datetime-local" value={defaultStart} onChange={(e) => setDefaultStart(e.target.value)} /></label>
        <label>{t("admin.juniorCutoff")}<input type="date" value={cutoff} onChange={(e) => setCutoff(e.target.value)} /></label>
      </div>
      <label className="check">
        <input type="checkbox" checked={included} onChange={(e) => setIncluded(e.target.checked)} />
        {t("admin.tshirtIncluded")}
      </label>
      <label>
        {t("admin.tshirtOptions")}
        <textarea rows={4} value={tshirtText} onChange={(e) => setTshirtText(e.target.value)} />
      </label>
      <p className="hint">{t("admin.tshirtOptionsHint")}</p>

      <h4>{t("admin.competitions")}</h4>
      <table className="results">
        <thead>
          <tr>
            <th>{t("admin.laps")}</th>
            <th>{t("admin.compTitle")}</th>
            <th>{t("admin.priceAdult")}</th>
            <th>{t("admin.priceJunior")}</th>
            <th>{t("admin.startTime")}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {comps.map((c, i) => (
            <tr key={i}>
              <td><input type="number" style={{ width: 60 }} value={c.lap_count} onChange={(e) => setComp(i, { lap_count: e.target.value })} required /></td>
              <td><input value={c.title} onChange={(e) => setComp(i, { title: e.target.value })} /></td>
              <td><input type="number" step="0.01" style={{ width: 80 }} value={c.price} onChange={(e) => setComp(i, { price: e.target.value })} /></td>
              <td><input type="number" step="0.01" style={{ width: 80 }} placeholder="–" value={c.priceJunior} onChange={(e) => setComp(i, { priceJunior: e.target.value })} /></td>
              <td><input type="datetime-local" value={c.startTime} onChange={(e) => setComp(i, { startTime: e.target.value })} /></td>
              <td>
                {comps.length > 1 && (
                  <button type="button" onClick={() => setComps(comps.filter((_, idx) => idx !== i))}>
                    {t("admin.remove")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <button type="button" onClick={() => setComps([...comps, emptyComp()])}>
          {t("admin.addCompetition")}
        </button>
      </p>

      <button className="primary" type="submit" disabled={busy}>
        {busy ? t("common.loading") : t("admin.createEvent")}
      </button>
    </form>
  );
}

function SepaExport({ eventId }: { eventId: string }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [includeExported, setIncludeExported] = useState(false);

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      const { blob, filename } = await downloadSepaExport(eventId, includeExported);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h3>{t("admin.sepaExport")}</h3>
      <p className="hint">{t("admin.sepaExportHint")}</p>
      <label className="check">
        <input
          type="checkbox"
          checked={includeExported}
          onChange={(e) => setIncludeExported(e.target.checked)}
        />
        {t("admin.sepaAll")}
      </label>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={run} disabled={busy}>
        {busy ? t("common.loading") : t("admin.sepaExportBtn")}
      </button>
    </>
  );
}

function EventSettings({ eventId }: { eventId: string }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [cutoff, setCutoff] = useState("");
  const [included, setIncluded] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.listEvents().then((e) => {
      const ev = e.find((x) => x.id === eventId);
      setText((ev?.tshirt_options ?? []).join("\n"));
      setCutoff(ev?.junior_cutoff_date ?? "");
      setIncluded(ev?.tshirt_included ?? false);
      setSaved(false);
    });
  }, [eventId]);

  const save = async () => {
    const opts = text.split("\n").map((s) => s.trim()).filter(Boolean);
    await adminApi.updateEvent(eventId, {
      tshirt_options: opts,
      junior_cutoff_date: cutoff || null,
      tshirt_included: included,
    });
    setSaved(true);
  };

  return (
    <>
      <h3>{t("admin.eventSettings")}</h3>
      <label>
        {t("admin.tshirtOptions")}
        <textarea rows={6} value={text} onChange={(e) => { setText(e.target.value); setSaved(false); }} />
      </label>
      <p className="hint">{t("admin.tshirtOptionsHint")}</p>

      <div className="row">
        <label>
          {t("admin.juniorCutoff")}
          <input
            type="date"
            value={cutoff}
            onChange={(e) => { setCutoff(e.target.value); setSaved(false); }}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={included}
            onChange={(e) => { setIncluded(e.target.checked); setSaved(false); }}
          />
          {t("admin.tshirtIncluded")}
        </label>
      </div>
      <p className="hint">{t("admin.juniorCutoffHint")}</p>

      <button className="primary" onClick={save}>
        {t("manage.save")}
      </button>
      {saved && <span className="hint"> ✓</span>}
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
