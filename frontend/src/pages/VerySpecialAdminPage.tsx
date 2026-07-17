import { useEffect, useState, type FormEvent } from "react";
import {
  adminApi,
  api,
  uploadBibBackground,
  uploadCertificateBackground,
  uploadSiteLogo,
  type EventCreatePayload,
} from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  canManage as canManageRoles,
  CompetitionSettings,
  EventSelect,
  LoginCard,
  useAdminSession,
  useEventSelector,
} from "./adminShared";

export function VerySpecialAdminPage() {
  const { t, lang } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome title={t("veryspecial.title")} roles={roles} logout={logout} allow={["race_office"]}>
      <EventMgmt roles={roles} lang={lang} />
    </AdminChrome>
  );
}

function EventMgmt({ roles, lang }: { roles: string[]; lang: string }) {
  const { t } = useI18n();
  const { events, eventId, setEventId, loadEvents } = useEventSelector();
  const mng = canManageRoles(roles);
  const isAdmin = roles.includes("admin");
  const [error, setError] = useState("");

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
      {mng && <SiteLogoAdmin />}
      {mng && <NewEvent onCreated={(id) => loadEvents(id)} />}
      {error && <p className="error">{error}</p>}

      <div className="row">
        <EventSelect events={events} eventId={eventId} onChange={setEventId} />
        {isAdmin && eventId && (
          <button type="button" onClick={delEvent} style={{ alignSelf: "flex-end" }}>
            {t("admin.deleteEvent")}
          </button>
        )}
      </div>

      {mng && eventId && <EventSettings eventId={eventId} />}
      {mng && eventId && <CompetitionSettings eventId={eventId} lang={lang} />}
    </>
  );
}

type CompRow = {
  title: string;
  price: string;
  priceJunior: string;
  startTime: string;
  scheme: string;
  genderScoring: boolean;
  relayScoring: boolean;
};
const emptyComp = (): CompRow => ({
  title: "",
  price: "",
  priceJunior: "",
  startTime: "",
  scheme: "five",
  genderScoring: true,
  relayScoring: false,
});

/** Globales Kopf-Logo hochladen/entfernen. Zeigt oben mittig auf Anmelde- und
 *  Detailseite an. Bild wird serverseitig normalisiert (max. Kante 400px). */
function SiteLogoAdmin() {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [v, setV] = useState(0); // Cache-Buster für die Vorschau

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setMsg("");
    try {
      await uploadSiteLogo(file);
      setV((x) => x + 1);
      setMsg(t("admin.siteLogoSaved"));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(t("admin.siteLogoDeleteConfirm"))) return;
    setBusy(true);
    setMsg("");
    try {
      await adminApi.deleteSiteLogo();
      setV((x) => x + 1);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>{t("admin.siteLogo")}</h2>
      <p className="hint">{t("admin.siteLogoHint")}</p>
      <img
        key={v}
        className="site-logo"
        style={{ margin: "0 auto" }}
        src={`${api.siteLogoUrl()}?v=${v}`}
        alt=""
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = "none";
        }}
      />
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp,image/svg+xml"
        disabled={busy}
        onChange={(e) => {
          upload(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <div className="row">
        <button type="button" onClick={remove} disabled={busy}>
          {t("admin.siteLogoDelete")}
        </button>
        {msg && <span className="hint" style={{ alignSelf: "center" }}>{msg}</span>}
      </div>
    </div>
  );
}

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
  const [comps, setComps] = useState<CompRow[]>([emptyComp()]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const setComp = (i: number, patch: Partial<CompRow>) =>
    setComps(comps.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));

  const addComp = () => setComps([...comps, emptyComp()]);

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
          title: c.title || null,
          price_cents: Math.round(Number(c.price || 0) * 100),
          price_junior_cents: c.priceJunior === "" ? null : Math.round(Number(c.priceJunior) * 100),
          start_time: c.startTime ? new Date(c.startTime).toISOString() : null,
          age_class_scheme: c.scheme,
          gender_scoring: c.genderScoring,
          relay_scoring: c.relayScoring,
        })),
      };
      const res = await adminApi.createEvent(body);
      onCreated(res.id);
      setOpen(false);
      setName(""); setYear(""); setDate(""); setDeadline(""); setDefaultStart("");
      setCutoff(""); setIncluded(false); setTshirtText("");
      setComps([emptyComp()]);
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
      <div className="table-scroll">
      <table className="results">
        <thead>
          <tr>
            <th>{t("admin.compTitle")}</th>
            <th>{t("admin.priceAdult")}</th>
            <th>{t("admin.priceJunior")}</th>
            <th>{t("admin.startTime")}</th>
            <th>{t("admin.ageClasses")}</th>
            <th>{t("admin.genderScoring")}</th>
            <th>{t("admin.relayScoring")}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {comps.map((c, i) => (
            <tr key={i}>
              <td><input value={c.title} onChange={(e) => setComp(i, { title: e.target.value })} required /></td>
              <td><input type="number" step="0.01" style={{ width: 80 }} value={c.price} onChange={(e) => setComp(i, { price: e.target.value })} /></td>
              <td><input type="number" step="0.01" style={{ width: 80 }} placeholder="–" value={c.priceJunior} onChange={(e) => setComp(i, { priceJunior: e.target.value })} /></td>
              <td><input type="datetime-local" value={c.startTime} onChange={(e) => setComp(i, { startTime: e.target.value })} /></td>
              <td>
                <select value={c.scheme} onChange={(e) => setComp(i, { scheme: e.target.value })}>
                  <option value="five">{t("admin.ak5")}</option>
                  <option value="one">{t("admin.ak1")}</option>
                  <option value="none">{t("admin.akNone")}</option>
                </select>
              </td>
              <td style={{ textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={c.genderScoring}
                  onChange={(e) => setComp(i, { genderScoring: e.target.checked })}
                />
              </td>
              <td style={{ textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={c.relayScoring}
                  onChange={(e) => setComp(i, { relayScoring: e.target.checked })}
                />
              </td>
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
      </div>
      <p>
        <button type="button" onClick={addComp}>
          {t("admin.addCompetition")}
        </button>
      </p>

      <button className="primary" type="submit" disabled={busy}>
        {busy ? t("common.loading") : t("admin.createEvent")}
      </button>
    </form>
  );
}

function EventSettings({ eventId }: { eventId: string }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [cutoff, setCutoff] = useState("");
  const [included, setIncluded] = useState(false);
  const [offset, setOffset] = useState("0");
  const [plz, setPlz] = useState("");
  const [saved, setSaved] = useState(false);
  const [hasBg, setHasBg] = useState(false);
  const [bgBusy, setBgBusy] = useState(false);
  const [bgMsg, setBgMsg] = useState("");
  const [hasBibBg, setHasBibBg] = useState(false);
  const [bibBgBusy, setBibBgBusy] = useState(false);
  const [bibBgMsg, setBibBgMsg] = useState("");

  useEffect(() => {
    api.listEvents().then((e) => {
      const ev = e.find((x) => x.id === eventId);
      setText((ev?.tshirt_options ?? []).join("\n"));
      setCutoff(ev?.junior_cutoff_date ?? "");
      setIncluded(ev?.tshirt_included ?? false);
      setOffset(String(ev?.certificate_offset ?? 0));
      setPlz(ev?.postal_code ?? "");
      setHasBg(ev?.has_certificate_background ?? false);
      setHasBibBg(ev?.has_bib_background ?? false);
      setBgMsg("");
      setBibBgMsg("");
      setSaved(false);
    });
  }, [eventId]);

  const uploadBg = async (file: File | undefined) => {
    if (!file) return;
    setBgBusy(true);
    setBgMsg("");
    try {
      await uploadCertificateBackground(eventId, file);
      setHasBg(true);
      setBgMsg(t("admin.certificateBgSaved"));
    } catch (err) {
      setBgMsg(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBgBusy(false);
    }
  };

  const uploadBibBg = async (file: File | undefined) => {
    if (!file) return;
    setBibBgBusy(true);
    setBibBgMsg("");
    try {
      await uploadBibBackground(eventId, file);
      setHasBibBg(true);
      setBibBgMsg(t("admin.bibBgSaved"));
    } catch (err) {
      setBibBgMsg(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBibBgBusy(false);
    }
  };

  const save = async () => {
    const opts = text.split("\n").map((s) => s.trim()).filter(Boolean);
    await adminApi.updateEvent(eventId, {
      tshirt_options: opts,
      junior_cutoff_date: cutoff || null,
      tshirt_included: included,
      certificate_offset: Number(offset) || 0,
      postal_code: plz.trim() || null,
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

      <label>
        {t("admin.eventPostalCode")}
        <input
          inputMode="numeric"
          style={{ width: 120 }}
          value={plz}
          onChange={(e) => { setPlz(e.target.value); setSaved(false); }}
        />
      </label>
      <p className="hint">{t("admin.eventPostalCodeHint")}</p>

      <label>
        {t("admin.certificateOffset")}
        <input
          type="number"
          step={1}
          style={{ width: 90 }}
          value={offset}
          onChange={(e) => { setOffset(e.target.value); setSaved(false); }}
        />
      </label>
      <p className="hint">{t("admin.certificateOffsetHint")}</p>

      <button className="primary" onClick={save}>
        {t("manage.save")}
      </button>
      {saved && <span className="hint"> ✓</span>}

      <h3>{t("admin.certificateBg")}</h3>
      <p className="hint">
        {t("admin.certificateBgHint")}{" "}
        {hasBg ? t("admin.certificateBgPresent") : t("admin.certificateBgNone")}
      </p>
      <input
        type="file"
        accept="image/png,image/jpeg"
        disabled={bgBusy}
        onChange={(e) => uploadBg(e.target.files?.[0])}
      />
      {bgMsg && <span className="hint"> {bgMsg}</span>}

      <h3>{t("admin.bibBg")}</h3>
      <p className="hint">
        {t("admin.bibBgHint")}{" "}
        {hasBibBg ? t("admin.certificateBgPresent") : t("admin.certificateBgNone")}
      </p>
      <input
        type="file"
        accept="image/png,image/jpeg"
        disabled={bibBgBusy}
        onChange={(e) => uploadBibBg(e.target.files?.[0])}
      />
      {bibBgMsg && <span className="hint"> {bibBgMsg}</span>}
    </>
  );
}
