import { useEffect, useState } from "react";
import { api, formatTime, type CompetitionDto, type EventDto, type ResultList } from "../api";
import { useI18n } from "../i18n";

export function ResultsPage() {
  const { t, lang } = useI18n();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [eventId, setEventId] = useState("");
  const [competitionId, setCompetitionId] = useState("");
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
      </div>

      {data && data.rows.length === 0 && <p>{t("results.empty")}</p>}
      {data && data.rows.length > 0 && (
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
            {data.rows.map((r) => (
              <tr key={r.bib_number} className={r.finish_seconds == null ? "dnf" : ""}>
                <td>{r.rank ?? t("results.dnf")}</td>
                <td>{r.bib_number}</td>
                <td>{r.first_name} {r.last_name}</td>
                <td>{r.category_code ?? "–"}</td>
                <td>{r.finish_seconds == null ? t("results.dnf") : formatTime(r.finish_seconds)}</td>
                <td>
                  {r.participation_count > 1 && (
                    <span className="badge">{t("results.nth", { n: r.participation_count })}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
