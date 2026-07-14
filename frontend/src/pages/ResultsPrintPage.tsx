import { useEffect, useState } from "react";
import {
  adminApi,
  downloadCertificateBundle,
  downloadCertificateByBib,
  type CertificateGroup,
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
  const { events, eventId, setEventId } = useEventSelector();

  return (
    <>
      <EventSelect events={events} eventId={eventId} onChange={setEventId} />
      {eventId && <SingleCertificate eventId={eventId} />}
      {eventId && <BundleList eventId={eventId} />}
    </>
  );
}

function SingleCertificate({ eventId }: { eventId: string }) {
  const { t, lang } = useI18n();
  const [bib, setBib] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const print = async () => {
    if (!bib) return;
    setBusy(true);
    setError("");
    try {
      const { blob, filename } = await downloadCertificateByBib(eventId, Number(bib), lang);
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

function BundleList({ eventId }: { eventId: string }) {
  const { t, lang } = useI18n();
  const [groups, setGroups] = useState<CertificateGroup[] | null>(null);
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setGroups(null);
    setError("");
    adminApi
      .certificateGroups(eventId)
      .then(setGroups)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }, [eventId]);

  const download = async (g: CertificateGroup) => {
    const key = `${g.competition_id}-${g.age_class ?? ""}`;
    setBusyKey(key);
    setError("");
    try {
      const { blob, filename } = await downloadCertificateBundle(
        eventId,
        g.competition_id,
        g.age_class,
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
      <h3>{t("resultsprint.bundles")}</h3>
      <p className="hint">{t("resultsprint.bundlesHint")}</p>
      {error && <p className="error">{error}</p>}
      {groups && groups.length === 0 && <p>{t("resultsprint.none")}</p>}
      {groups && groups.length > 0 && (
        <table className="results">
          <thead>
            <tr>
              <th>{t("admin.race")}</th>
              <th>{t("resultsprint.ageClass")}</th>
              <th>{t("resultsprint.count")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const key = `${g.competition_id}-${g.age_class ?? ""}`;
              return (
                <tr key={key}>
                  <td>{g.competition_title?.[lang] || "Lauf"}</td>
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
