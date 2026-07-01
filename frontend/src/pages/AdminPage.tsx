import { useEffect, useState } from "react";
import { adminApi, api, type AdminRegistration, type EventDto } from "../api";
import { useI18n } from "../i18n";
import {
  AdminChrome,
  canManage as canManageRoles,
  EditRegistration,
  LoginCard,
  useAdminSession,
} from "./adminShared";

export function AdminPage() {
  const { t, lang } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome title={t("admin.title")} roles={roles} logout={logout}>
      <AdminSearch canManage={canManageRoles(roles)} lang={lang} />
    </AdminChrome>
  );
}

function AdminSearch({ canManage, lang }: { canManage: boolean; lang: string }) {
  const { t } = useI18n();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [eventId, setEventId] = useState("");
  const [q, setQ] = useState("");
  const [regs, setRegs] = useState<AdminRegistration[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      if (e[0]) setEventId(e[0].id);
    });
  }, []);

  const runSearch = () => {
    if (!eventId || !q.trim()) {
      setRegs([]);
      return;
    }
    adminApi
      .listRegistrations(eventId, q, 50, 0)
      .then((res) => setRegs(res.items))
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  };
  // Suche mit kleiner Entprellung; nur bei nicht-leerer Eingabe.
  useEffect(() => {
    const h = setTimeout(runSearch, 250);
    return () => clearTimeout(h);
  }, [eventId, q]);

  return (
    <>
      <label>
        {t("register.event")}
        <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
          {events.map((ev) => (
            <option key={ev.id} value={ev.id}>{ev.name} ({ev.year})</option>
          ))}
        </select>
      </label>

      <input
        placeholder={t("admin.search")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoFocus
      />
      {error && <p className="error">{error}</p>}

      {!q.trim() && <p className="hint">{t("admin.searchPrompt")}</p>}

      {q.trim() && (
        <table className="results">
          <thead>
            <tr>
              <th>{t("admin.bib")}</th>
              <th>{t("admin.name")}</th>
              <th>{t("admin.competition")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {regs.map((r) => (
              <tr key={r.id}>
                <td>{r.bib_number ?? "–"}</td>
                <td>{r.first_name} {r.last_name}</td>
                <td>{t("register.laps", { n: r.lap_count })}</td>
                <td>
                  {canManage && (
                    <button onClick={() => setEditingId(r.id)}>{t("admin.edit")}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editingId && (
        <EditRegistration
          id={editingId}
          lang={lang}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            runSearch();
          }}
        />
      )}
    </>
  );
}
