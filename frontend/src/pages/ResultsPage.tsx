import { useEffect, useState } from "react";
import { api, formatTime, type CompetitionDto, type EventDto, type ResultList, type ResultRow } from "../api";
import { useI18n } from "../i18n";

type View = "overall" | "ageclass" | "ageclass_gender";

type Entry = { row: ResultRow; rank: number | null };

export function ResultsPage() {
  const { t, lang } = useI18n();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [eventId, setEventId] = useState("");
  const [competitionId, setCompetitionId] = useState("");
  const [view, setView] = useState<View>("overall");
  const [data, setData] = useState<ResultList | null>(null);

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      if (e[0]) setEventId(e[0].id);
    });
  }, []);

  useEffect(() => {
    if (!eventId) return;
    setCompetitionId("");
    setData(null);
    api.listCompetitions(eventId).then(setCompetitions);
  }, [eventId]);

  useEffect(() => {
    if (eventId && competitionId) api.getResults(eventId, competitionId).then(setData);
  }, [eventId, competitionId]);

  return (
    <div className="card">
      <h2>{t("results.heading")}</h2>
      <div className="row">
        <label>
          {t("register.event")}
          <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
            {events.map((ev) => (
              <option key={ev.id} value={ev.id}>{ev.name} ({ev.year})</option>
            ))}
          </select>
        </label>
        <label>
          {t("register.competition")}
          <select value={competitionId} onChange={(e) => setCompetitionId(e.target.value)}>
            <option value="">{t("common.choose")}</option>
            {competitions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title_i18n?.[lang] || t("register.laps", { n: c.lap_count })}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("results.view")}
          <select value={view} onChange={(e) => setView(e.target.value as View)}>
            <option value="overall">{t("results.viewOverall")}</option>
            <option value="ageclass">{t("results.viewAgeClass")}</option>
            <option value="ageclass_gender">{t("results.viewAgeClassGender")}</option>
          </select>
        </label>
      </div>

      {data && data.rows.length === 0 && <p>{t("results.empty")}</p>}
      {data && data.rows.length > 0 && view === "overall" && (
        <ResultTable entries={data.rows.map((r) => ({ row: r, rank: r.rank }))} />
      )}
      {data && data.rows.length > 0 && view !== "overall" && (
        <Grouped rows={data.rows} withGender={view === "ageclass_gender"} />
      )}
    </div>
  );
}

/** Gruppiert die (bereits nach Zeit sortierten) Zeilen und vergibt je Gruppe
 * eine eigene Platzierung (nur für Finisher). */
function Grouped({ rows, withGender }: { rows: ResultRow[]; withGender: boolean }) {
  const { t } = useI18n();
  const noCat = t("results.noCategory");

  const groups = new Map<string, { heading: string; entries: Entry[] }>();
  const counters = new Map<string, number>();
  for (const row of rows) {
    const cat = row.category_code || noCat;
    const key = withGender ? `${cat}|${row.gender}` : cat;
    const heading = withGender ? `${cat} · ${t(`register.gender.${row.gender}`)}` : cat;
    if (!groups.has(key)) groups.set(key, { heading, entries: [] });
    let rank: number | null = null;
    if (row.finish_seconds != null) {
      const c = (counters.get(key) ?? 0) + 1;
      counters.set(key, c);
      rank = c;
    }
    groups.get(key)!.entries.push({ row, rank });
  }

  return (
    <>
      {[...groups.values()].map((g) => (
        <div key={g.heading}>
          <h3>{g.heading}</h3>
          <ResultTable entries={g.entries} />
        </div>
      ))}
    </>
  );
}

function ResultTable({ entries }: { entries: Entry[] }) {
  const { t } = useI18n();
  return (
    <table className="results">
      <thead>
        <tr>
          <th>{t("results.rank")}</th>
          <th>{t("results.bib")}</th>
          <th>{t("results.name")}</th>
          <th>{t("results.category")}</th>
          <th>{t("results.time")}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {entries.map(({ row, rank }) => (
          <tr key={row.bib_number} className={row.finish_seconds == null ? "dnf" : ""}>
            <td>{rank ?? t("results.dnf")}</td>
            <td>{row.bib_number}</td>
            <td>{row.first_name} {row.last_name}</td>
            <td>{row.category_code ?? "–"}</td>
            <td>{row.finish_seconds == null ? t("results.dnf") : formatTime(row.finish_seconds)}</td>
            <td>
              {row.participation_count > 1 && (
                <span className="badge">{t("results.nth", { n: row.participation_count })}</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
