import { useEffect, useState } from "react";
import {
  adminApi,
  api,
  downloadCertificateBundle,
  downloadCertificateByBib,
  type CertificateGroup,
  type CompetitionDto,
} from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  EventSelect,
  LoginCard,
  useAdminSession,
  useEventSelector,
} from "./adminShared";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ResultsPrintPage() {
  const { t } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome title={t("resultsprint.title")} roles={roles} logout={logout}>
      <ResultsPrintDashboard />
    </AdminChrome>
  );
}

function ResultsPrintDashboard() {
  const { t, lang } = useI18n();
  const { events, eventId, setEventId } = useEventSelector();
  const [comps, setComps] = useState<CompetitionDto[]>([]);
  const [competitionId, setCompetitionId] = useState("");
  const [scheme, setScheme] = useState("five");
  const [gender, setGender] = useState(""); // "" = alle

  useEffect(() => {
    if (!eventId) {
      setComps([]);
      setCompetitionId("");
      return;
    }
    api.listCompetitions(eventId).then((c) => {
      setComps(c);
      setCompetitionId((prev) => (c.some((x) => x.id === prev) ? prev : c[0]?.id ?? ""));
    });
  }, [eventId]);

  const compLabel = (c: CompetitionDto) => c.title_i18n?.[lang] || t("admin.race");

  return (
    <>
      <EventSelect events={events} eventId={eventId} onChange={setEventId} />

      {eventId && <SingleCertificate eventId={eventId} scheme={scheme} />}

      {eventId && (
        <>
          <h3>{t("resultsprint.bundles")}</h3>
          <p className="hint">{t("resultsprint.bundlesHint")}</p>
          <div className="row">
            <label>
              {t("admin.race")}
              <select value={competitionId} onChange={(e) => setCompetitionId(e.target.value)}>
                {comps.map((c) => (
                  <option key={c.id} value={c.id}>{compLabel(c)}</option>
                ))}
              </select>
            </label>
            <label>
              {t("resultsprint.scheme")}
              <select value={scheme} onChange={(e) => setScheme(e.target.value)}>
                <option value="five">{t("resultsprint.scheme5")}</option>
                <option value="one">{t("resultsprint.scheme1")}</option>
              </select>
            </label>
            <label>
              {t("resultsprint.gender")}
              <select value={gender} onChange={(e) => setGender(e.target.value)}>
                <option value="">{t("resultsprint.genderAll")}</option>
                <option value="m">{t("register.gender.m")}</option>
                <option value="f">{t("register.gender.f")}</option>
                <option value="x">{t("register.gender.x")}</option>
              </select>
            </label>
          </div>
          {competitionId && (
            <BundleList
              eventId={eventId}
              competitionId={competitionId}
              scheme={scheme}
              gender={gender}
            />
          )}
        </>
      )}
    </>
  );
}

function SingleCertificate({ eventId, scheme }: { eventId: string; scheme: string }) {
  const { t, lang } = useI18n();
  const [bib, setBib] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const print = async () => {
    if (!bib) return;
    setBusy(true);
    setError("");
    try {
      const { blob, filename } = await downloadCertificateByBib(eventId, Number(bib), scheme, lang);
      triggerDownload(blob, filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h3>{t("resultsprint.single")}</h3>
      <div className="row">
        <input
          inputMode="numeric"
          value={bib}
          onChange={(e) => setBib(e.target.value.replace(/\D/g, ""))}
          placeholder={t("admin.bib")}
        />
        <button className="primary" onClick={print} disabled={!bib || busy}>
          {busy ? t("common.loading") : t("resultsprint.printSingle")}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </>
  );
}

function BundleList({
  eventId,
  competitionId,
  scheme,
  gender,
}: {
  eventId: string;
  competitionId: string;
  scheme: string;
  gender: string;
}) {
  const { t, lang } = useI18n();
  const [groups, setGroups] = useState<CertificateGroup[] | null>(null);
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setGroups(null);
    setError("");
    adminApi
      .certificateGroups(eventId, competitionId, scheme, gender)
      .then(setGroups)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }, [eventId, competitionId, scheme, gender]);

  const download = async (g: CertificateGroup) => {
    const key = g.age_class ?? "";
    setBusyKey(key);
    setError("");
    try {
      const { blob, filename } = await downloadCertificateBundle(
        eventId,
        competitionId,
        g.age_class,
        scheme,
        gender,
        lang
      );
      triggerDownload(blob, filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusyKey("");
    }
  };

  return (
    <>
      {error && <p className="error">{error}</p>}
      {groups && groups.length === 0 && <p>{t("resultsprint.none")}</p>}
      {groups && groups.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>{t("resultsprint.ageClass")}</th>
              <th>{t("resultsprint.count")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const key = g.age_class ?? "";
              return (
                <tr key={key}>
                  <td>{g.age_class ?? "–"}</td>
                  <td>{g.count}</td>
                  <td>
                    <button
                      className="primary"
                      disabled={busyKey === key}
                      onClick={() => download(g)}
                    >
                      {busyKey === key ? t("common.loading") : t("resultsprint.download")}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
