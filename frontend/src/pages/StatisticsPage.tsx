import { useEffect, useState } from "react";
import { adminApi, type StatsDto } from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  EventSelect,
  LoginCard,
  useAdminSession,
  useEventSelector,
} from "./adminShared";

export function StatisticsPage() {
  const { t } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome
      title={t("stats.title")}
      roles={roles}
      logout={logout}
      allow={["race_office", "viewer"]}
    >
      <StatsDashboard />
    </AdminChrome>
  );
}

function StatsDashboard() {
  const { t } = useI18n();
  const { events, eventId, setEventId } = useEventSelector();
  const [data, setData] = useState<StatsDto | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!eventId) {
      setData(null);
      return;
    }
    setData(null);
    setError("");
    adminApi
      .stats(eventId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }, [eventId]);

  return (
    <>
      <EventSelect events={events} eventId={eventId} onChange={setEventId} />
      {error && <p className="error">{error}</p>}
      {eventId && !data && !error && <p>{t("common.loading")}</p>}
      {data && <Stats data={data} />}
    </>
  );
}

/** Eine Kennzahl als große Zahl mit Beschriftung. */
function Figure({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="figure">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function personText(p: { name: string; age: number } | null, t: (k: string, v?: any) => string) {
  return p ? t("stats.personAge", { name: p.name, age: p.age }) : "–";
}

function Stats({ data }: { data: StatsDto }) {
  const { t } = useI18n();
  const g = data.gender;

  return (
    <>
      {/* --- Überblick --- */}
      <h3>{t("stats.overview")}</h3>
      <div className="figures">
        <Figure value={data.total} label={t("stats.participants")} />
        <Figure value={data.finishers} label={t("stats.finishers")} />
        <Figure value={data.teams.count} label={t("stats.teams")} />
        <Figure value={data.relays.count} label={t("stats.relays")} />
        <Figure value={data.average_age ?? "–"} label={t("stats.avgAge")} />
      </div>
      <ul className="meta">
        <li>
          {t("register.gender.f")}: <strong>{g.f ?? 0}</strong>
        </li>
        <li>
          {t("register.gender.m")}: <strong>{g.m ?? 0}</strong>
        </li>
        <li>
          {t("register.gender.x")}: <strong>{g.x ?? 0}</strong>
        </li>
        <li>
          {t("stats.youngest")}: <strong>{personText(data.youngest, t)}</strong>
        </li>
        <li>
          {t("stats.oldest")}: <strong>{personText(data.oldest, t)}</strong>
        </li>
      </ul>

      {/* --- Je Lauf --- */}
      <h3>{t("stats.perRace")}</h3>
      <div className="table-scroll">
        <table className="results">
          <thead>
            <tr>
              <th>{t("admin.race")}</th>
              <th>{t("stats.participants")}</th>
              <th>{t("register.gender.f")}</th>
              <th>{t("register.gender.m")}</th>
              <th>{t("register.gender.x")}</th>
              <th>{t("stats.avgAge")}</th>
              <th>{t("stats.youngest")}</th>
              <th>{t("stats.oldest")}</th>
              <th>{t("stats.relays")}</th>
              <th>{t("stats.fastest")}</th>
            </tr>
          </thead>
          <tbody>
            {data.competitions.map((c) => (
              <tr key={c.id}>
                <td>{c.title}</td>
                <td>{c.total}</td>
                <td>{c.gender.f ?? 0}</td>
                <td>{c.gender.m ?? 0}</td>
                <td>{c.gender.x ?? 0}</td>
                <td>{c.average_age ?? "–"}</td>
                <td>{personText(c.youngest, t)}</td>
                <td>{personText(c.oldest, t)}</td>
                <td>{c.relay_scoring ? c.relays : "–"}</td>
                <td>{c.fastest ? `${c.fastest.name} (${c.fastest.time_text})` : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* --- Staffeln --- */}
      {data.relays.formed > 0 && (
        <>
          <h3>{t("stats.relayList")}</h3>
          <div className="table-scroll">
            <table className="results">
              <thead>
                <tr>
                  <th>{t("stats.rank")}</th>
                  <th>{t("register.team")}</th>
                  <th>{t("admin.race")}</th>
                  <th>{t("stats.relayTime")}</th>
                </tr>
              </thead>
              <tbody>
                {data.relays.list.map((r, i) => (
                  <tr key={i} className={r.scored ? "" : "dnf"}>
                    <td>{r.rank ?? "–"}</td>
                    <td>{r.team ?? "–"}</td>
                    <td>{r.competition}</td>
                    <td>{r.total_seconds != null ? formatSeconds(r.total_seconds) : t("stats.incomplete")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* --- Teams --- */}
      {data.teams.count > 0 && (
        <>
          <h3>{t("stats.teamList")}</h3>
          <p className="hint">
            {data.teams.list.map((tm) => `${tm.name} (${tm.members})`).join(" · ")}
          </p>
        </>
      )}

      {/* --- Anreise --- */}
      <h3>{t("stats.travel")}</h3>
      {!data.travel.reference_postal_code ? (
        <p className="hint">{t("stats.travelNoReference")}</p>
      ) : (
        <>
          <p className="hint">{t("stats.travelHint")}</p>
          <ul className="meta">
            <li>
              {t("stats.travelAvg")}: <strong>{data.travel.average_km ?? "–"} km</strong>
            </li>
            {data.travel.farthest && (
              <li>
                {t("stats.travelFarthest")}:{" "}
                <strong>
                  {data.travel.farthest.name} – ca. {data.travel.farthest.km} km
                  {data.travel.farthest.region ? ` (${data.travel.farthest.region})` : ""}
                </strong>
              </li>
            )}
            <li>
              {t("stats.travelUnknown")}: <strong>{data.travel.unknown}</strong>
            </li>
          </ul>
          <div className="table-scroll">
            <table className="results">
              <thead>
                <tr>
                  <th>{t("stats.distance")}</th>
                  <th>{t("stats.participants")}</th>
                </tr>
              </thead>
              <tbody>
                {data.travel.buckets.map((b) => (
                  <tr key={b.label}>
                    <td>{b.label}</td>
                    <td>{b.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.travel.top_regions.length > 0 && (
            <p className="hint">
              {t("stats.topRegions")}:{" "}
              {data.travel.top_regions
                .map((r) => `${r.name ?? r.region} (${r.count})`)
                .join(" · ")}
            </p>
          )}
        </>
      )}

      {/* --- Stammgäste --- */}
      {data.regulars.repeat_count > 0 && (
        <>
          <h3>{t("stats.regulars")}</h3>
          <p className="hint">{t("stats.regularsHint", { n: data.regulars.repeat_count })}</p>
          <ul className="meta">
            {data.regulars.list
              .filter((r) => r.participations > 1)
              .map((r) => (
                <li key={r.name}>
                  {r.name}: <strong>{t("stats.nth", { n: r.participations })}</strong>
                </li>
              ))}
          </ul>
        </>
      )}

      {/* --- Freiwillige Angaben --- */}
      {data.heard_about.length > 0 && (
        <>
          <h3>{t("stats.heardAbout")}</h3>
          <p className="hint">
            {data.heard_about.map((h) => `${t(`heard.${h.code}`)}: ${h.count}`).join(" · ")}
          </p>
        </>
      )}

      {/* --- T-Shirts (Logistik) --- */}
      {data.tshirts.length > 0 && (
        <>
          <h3>{t("stats.tshirts")}</h3>
          <p className="hint">
            {data.tshirts.map((s) => `${s.size}: ${s.count}`).join(" · ")}
          </p>
        </>
      )}
    </>
  );
}

function formatSeconds(total: number) {
  const s = Math.round(total);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    : `${m}:${String(sec).padStart(2, "0")}`;
}
