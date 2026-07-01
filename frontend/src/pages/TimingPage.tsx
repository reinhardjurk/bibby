import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, sendTimings, type EventDto, type TimingPing } from "../api";
import { useI18n } from "../i18n";

const TKEY = "bibby.timing.token";
const EKEY = "bibby.timing.event";
const QKEY = "bibby.timing.queue";

function uuid() {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// Warteschlange noch nicht gesendeter Erfassungen (überlebt Reload/Absturz).
function loadQueue(): TimingPing[] {
  try {
    return JSON.parse(localStorage.getItem(QKEY) || "[]");
  } catch {
    return [];
  }
}
function saveQueue(q: TimingPing[]) {
  localStorage.setItem(QKEY, JSON.stringify(q));
}

export function TimingPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [token, setToken] = useState(localStorage.getItem(TKEY) || "");
  const [eventId, setEventId] = useState(localStorage.getItem(EKEY) || "");
  const [configured, setConfigured] = useState(
    !!(localStorage.getItem(TKEY) && localStorage.getItem(EKEY))
  );

  const [bib, setBib] = useState("");
  const pendingRef = useRef<TimingPing[]>(loadQueue());
  const flushingRef = useRef(false);
  const [pending, setPending] = useState(pendingRef.current.length);
  const [recent, setRecent] = useState<{ bib: number; time: string }[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api.listEvents().then(setEvents).catch(() => {});
  }, []);

  // Vorkonfiguration per gescanntem QR-Code: ?token=…&event=…
  useEffect(() => {
    const urlToken = params.get("token");
    const urlEvent = params.get("event");
    if (urlToken && urlEvent) {
      localStorage.setItem(TKEY, urlToken);
      localStorage.setItem(EKEY, urlEvent);
      setToken(urlToken);
      setEventId(urlEvent);
      setConfigured(true);
      navigate("/timing", { replace: true }); // Token aus URL/History entfernen
    }
  }, []);

  const flush = async () => {
    if (flushingRef.current || pendingRef.current.length === 0) return;
    flushingRef.current = true;
    const batch = pendingRef.current.slice();
    try {
      await sendTimings(eventId, token, batch);
      // Nur die gesendeten (vorne liegenden) entfernen; neue kamen hinten dazu.
      pendingRef.current = pendingRef.current.slice(batch.length);
      saveQueue(pendingRef.current);
      setPending(pendingRef.current.length);
      setMsg({ ok: true, text: t("timing.sent") });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : t("timing.error") });
    } finally {
      flushingRef.current = false;
    }
  };

  // Sofort beim Laden (persistierte Warteschlange) und dann alle 4 s erneut
  // versuchen, noch nicht gesendete Erfassungen abzusenden.
  useEffect(() => {
    if (pendingRef.current.length) flush();
    const h = setInterval(() => {
      if (pendingRef.current.length) flush();
    }, 4000);
    return () => clearInterval(h);
  }, [eventId, token]);

  const saveConfig = (e: FormEvent) => {
    e.preventDefault();
    localStorage.setItem(TKEY, token);
    localStorage.setItem(EKEY, eventId);
    setConfigured(true);
  };

  const press = (d: string) => setBib((b) => (b.length >= 6 ? b : b + d));

  const capture = () => {
    const n = parseInt(bib, 10);
    if (!n) return;
    // Zeit JETZT festhalten (Gerätezeit), unabhängig vom Netz.
    const ping: TimingPing = {
      bib_number: n,
      absolute_time: new Date().toISOString(),
      dedup_key: uuid(),
    };
    pendingRef.current.push(ping);
    saveQueue(pendingRef.current);
    setPending(pendingRef.current.length);
    setRecent((r) => [{ bib: n, time: ping.absolute_time }, ...r].slice(0, 8));
    setBib("");
    flush();
  };

  if (!configured) {
    return (
      <form className="card" onSubmit={saveConfig}>
        <h2>{t("timing.title")}</h2>
        <p className="hint">{t("timing.setupHint")}</p>
        <label>
          {t("register.event")}
          <select value={eventId} onChange={(e) => setEventId(e.target.value)} required>
            <option value="">{t("common.choose")}</option>
            {events.map((ev) => (
              <option key={ev.id} value={ev.id}>{ev.name} ({ev.year})</option>
            ))}
          </select>
        </label>
        <label>
          {t("timing.token")}
          <input value={token} onChange={(e) => setToken(e.target.value)} required />
        </label>
        <button className="primary" type="submit" disabled={!eventId || !token}>
          {t("timing.save")}
        </button>
      </form>
    );
  }

  return (
    <div className="card timing">
      <div className="timing-display">{bib || " "}</div>

      <div className="numpad">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} type="button" className="num-key" onClick={() => press(d)}>
            {d}
          </button>
        ))}
        <button type="button" className="num-key num-alt" onClick={() => setBib("")}>
          C
        </button>
        <button type="button" className="num-key" onClick={() => press("0")}>
          0
        </button>
        <button type="button" className="num-key num-alt" onClick={() => setBib((b) => b.slice(0, -1))}>
          ⌫
        </button>
      </div>

      <button className="capture-btn" type="button" onClick={capture} disabled={!bib}>
        {t("timing.capture")}
      </button>

      {msg && <p className={msg.ok ? "success" : "error"}>{msg.text}</p>}
      {pending > 0 && <p className="hint">{t("timing.pending", { n: pending })}</p>}

      <h3>{t("timing.recent")}</h3>
      <table className="results">
        <tbody>
          {recent.map((r, i) => (
            <tr key={i}>
              <td><strong>{r.bib}</strong></td>
              <td>{new Date(r.time).toLocaleTimeString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p>
        <button onClick={() => setConfigured(false)}>{t("timing.settings")}</button>
      </p>
    </div>
  );
}
