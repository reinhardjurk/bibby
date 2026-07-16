import { useState } from "react";
import { downloadSepaExport } from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  EventSelect,
  LoginCard,
  useAdminSession,
  useEventSelector,
} from "./adminShared";

export function SepaAdminPage() {
  const { t } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome title={t("sepa.title")} roles={roles} logout={logout} allow={["sepa"]}>
      <SepaDashboard />
    </AdminChrome>
  );
}

function SepaDashboard() {
  const { events, eventId, setEventId } = useEventSelector();

  return (
    <>
      <EventSelect events={events} eventId={eventId} onChange={setEventId} />
      {eventId && <SepaExport eventId={eventId} />}
    </>
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
