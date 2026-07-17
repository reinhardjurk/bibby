import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type CompetitionDto, type ManageView } from "../api";
import { SiteLogo } from "../components/SiteLogo";
import { SponsorBar } from "../components/SponsorBar";
import { TeamInput } from "../components/TeamInput";
import { useI18n } from "../i18n";

export function ManagePage() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [data, setData] = useState<ManageView | null>(null);
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [email, setEmail] = useState("");
  const [competitionId, setCompetitionId] = useState("");
  const [team, setTeam] = useState("");
  const [tshirt, setTshirt] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!token) {
      setError(t("manage.noToken"));
      return;
    }
    api.getManage(token)
      .then((d) => {
        setData(d);
        setEmail(d.email);
        setCompetitionId(d.registration.competition_id);
        // Team vorbelegen: aktuelles Team oder Vorschlag aus früherer Anmeldung.
        setTeam(d.team ?? d.suggested_team ?? "");
        setTshirt(d.tshirt ?? "");
        return api.listCompetitions(d.event_id);
      })
      .then((c) => c && setCompetitions(c))
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }, [token]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaved(false);
    setError("");
    try {
      await api.updateManage(token, { email, competition_id: competitionId, team, tshirt });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  };

  if (error && !data) return <div className="card"><p className="error">{error}</p></div>;
  if (!data) return <div className="card">{t("common.loading")}</div>;

  const compLabel = (c: CompetitionDto) =>
    c.title_i18n?.[lang] || t("register.laps", { n: c.lap_count });
  const showSuggestion = !data.team && !!data.suggested_team;

  return (
    <>
    <SiteLogo />
    <SponsorBar position="top" />
    <form className="card" onSubmit={save}>
      <h2>{t("manage.heading")}</h2>
      <p>
        {data.first_name} {data.last_name}
      </p>
      <ul className="meta">
        <li>{t("manage.status")}: <strong>{data.registration.status}</strong></li>
        <li>{t("manage.bib")}: <strong>{data.registration.bib_number ?? t("manage.notAssigned")}</strong></li>
        <li>
          {t("manage.method")}:{" "}
          <strong>{data.payment_method ? t(`pay.method.${data.payment_method}`) : "–"}</strong>
        </li>
        <li>
          {t("manage.payment")}:{" "}
          <strong>{data.payment_status ? t(`pay.status.${data.payment_status}`) : "–"}</strong>
        </li>
        {data.payment_iban_masked && (
          <li>{t("manage.iban")}: <strong>{data.payment_iban_masked}</strong></li>
        )}
        {data.mandate_reference && (
          <li>{t("register.mandateRef")}: <strong>{data.mandate_reference}</strong></li>
        )}
      </ul>

      {error && <p className="error">{error}</p>}

      <label>
        {t("register.email")}
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>

      <label>
        {t("register.competition")}
        <select value={competitionId} onChange={(e) => setCompetitionId(e.target.value)}>
          {competitions.map((c) => (
            <option key={c.id} value={c.id}>{compLabel(c)}</option>
          ))}
        </select>
      </label>

      <label>
        {t("register.team")}
        <TeamInput value={team} onChange={setTeam} placeholder={t("register.teamPlaceholder")} />
        {showSuggestion && (
          <span className="hint">{t("manage.teamSuggestion", { team: data.suggested_team || "" })}</span>
        )}
      </label>

      <label>
        {t("register.tshirt")}
        <select value={tshirt} onChange={(e) => setTshirt(e.target.value)}>
          <option value="">{t("common.choose")}</option>
          {data.tshirt_options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      </label>

      {saved && <p className="success">{t("manage.saved")}</p>}
      <button className="primary" type="submit">{t("manage.save")}</button>

      {data.registration.bib_number != null && (
        <p>
          <a href={api.bibPdfUrl(token)} target="_blank" rel="noreferrer">{t("manage.bibPdf")}</a>
        </p>
      )}

      {data.finish_seconds != null && (
        <p>
          <a href={api.certificatePdfUrl(token)} target="_blank" rel="noreferrer">
            {t("manage.certificate")}
          </a>
        </p>
      )}
    </form>
    <SponsorBar position="bottom" />
    </>
  );
}
