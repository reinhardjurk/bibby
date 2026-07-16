import { useEffect, useState } from "react";
import {
  adminApi,
  api,
  uploadSponsor,
  type SponsorDto,
  type SponsorTierCfg,
  type SponsorsDto,
} from "../api";
import { useI18n } from "../i18n";
import { AdminChrome, LoginCard, useAdminSession } from "./adminShared";

const TIERS = [1, 2, 3, 4, 5];

export function SponsorsAdminPage() {
  const { t } = useI18n();
  const { authed, roles, onAuthed, logout } = useAdminSession();

  if (authed === null) return <div className="card">{t("common.loading")}</div>;
  if (!authed) return <LoginCard onAuthed={onAuthed} />;

  return (
    <AdminChrome title={t("sponsors.title")} roles={roles} logout={logout}>
      <SponsorsDashboard />
    </AdminChrome>
  );
}

function SponsorsDashboard() {
  const { t } = useI18n();
  const [data, setData] = useState<SponsorsDto | null>(null);
  const [error, setError] = useState("");

  const reload = () =>
    api
      .listSponsors()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));

  useEffect(() => {
    reload();
  }, []);

  if (!data) return <p>{t("common.loading")}</p>;

  return (
    <>
      {error && <p className="error">{error}</p>}
      <DisplayMode current={data.display} onSaved={reload} />
      <TierConfig tiers={data.tiers} onSaved={reload} />
      <UploadSponsor onUploaded={reload} />
      <SponsorList data={data} onChanged={reload} />
    </>
  );
}

function DisplayMode({ current, onSaved }: { current: string; onSaved: () => void }) {
  const { t } = useI18n();
  const [mode, setMode] = useState(current);
  const [error, setError] = useState("");

  const change = async (m: string) => {
    setMode(m);
    setError("");
    try {
      await adminApi.updateSponsorDisplay(m);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <>
      <h3>{t("sponsors.display")}</h3>
      <label>
        {t("sponsors.displayMode")}
        <select value={mode} onChange={(e) => change(e.target.value)}>
          <option value="rotate">{t("sponsors.displayRotate")}</option>
          <option value="marquee">{t("sponsors.displayMarquee")}</option>
        </select>
      </label>
      {error && <p className="error">{error}</p>}
    </>
  );
}

function TierConfig({
  tiers,
  onSaved,
}: {
  tiers: Record<string, SponsorTierCfg>;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(tiers);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const set = (tier: number, patch: Partial<SponsorTierCfg>) => {
    setDraft({ ...draft, [tier]: { ...draft[String(tier)], ...patch } });
    setSaved(false);
  };

  const save = async () => {
    setError("");
    try {
      await adminApi.updateSponsorTiers(draft);
      setSaved(true);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  const ratio = TIERS.map((n) => draft[String(n)]?.weight ?? 0).join(":");

  return (
    <>
      <h3>{t("sponsors.tiers")}</h3>
      <p className="hint">{t("sponsors.tiersHint", { ratio })}</p>
      {error && <p className="error">{error}</p>}
      <table className="results">
        <thead>
          <tr>
            <th>{t("sponsors.tier")}</th>
            <th>{t("sponsors.weight")}</th>
            <th>{t("sponsors.height")}</th>
          </tr>
        </thead>
        <tbody>
          {TIERS.map((n) => (
            <tr key={n}>
              <td>{n}</td>
              <td>
                <input
                  type="number"
                  min={0}
                  style={{ width: 80 }}
                  value={draft[String(n)]?.weight ?? 0}
                  onChange={(e) => set(n, { weight: Number(e.target.value) })}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={10}
                  max={400}
                  style={{ width: 80 }}
                  value={draft[String(n)]?.height ?? 60}
                  onChange={(e) => set(n, { height: Number(e.target.value) })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="primary" onClick={save}>
        {t("manage.save")}
      </button>
      {saved && <span className="hint"> ✓</span>}
    </>
  );
}

function UploadSponsor({ onUploaded }: { onUploaded: () => void }) {
  const { t } = useI18n();
  const [tier, setTier] = useState(1);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setMsg("");
    try {
      await uploadSponsor(tier, name, url, file);
      setName("");
      setUrl("");
      setMsg(t("sponsors.uploaded"));
      onUploaded();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h3>{t("sponsors.upload")}</h3>
      <p className="hint">{t("sponsors.uploadHint")}</p>
      <div className="row">
        <label>
          {t("sponsors.tier")}
          <select value={tier} onChange={(e) => setTier(Number(e.target.value))}>
            {TIERS.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          {t("sponsors.name")}
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          {t("sponsors.url")}
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
          />
        </label>
      </div>
      <input
        type="file"
        accept="image/png,image/jpeg,image/svg+xml,image/webp"
        disabled={busy}
        onChange={(e) => {
          upload(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {msg && <span className="hint"> {msg}</span>}
    </>
  );
}

function SponsorList({ data, onChanged }: { data: SponsorsDto; onChanged: () => void }) {
  const { t } = useI18n();
  const [error, setError] = useState("");

  const remove = async (id: string) => {
    if (!window.confirm(t("sponsors.confirmDelete"))) return;
    setError("");
    try {
      await adminApi.deleteSponsor(id);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <>
      <h3>{t("sponsors.list")}</h3>
      {error && <p className="error">{error}</p>}
      {data.items.length === 0 && <p>{t("sponsors.none")}</p>}
      {TIERS.map((n) => {
        const items = data.items.filter((s) => s.tier === n);
        if (!items.length) return null;
        return (
          <div key={n}>
            <p className="hint">
              {t("sponsors.tier")} {n} · {t("sponsors.weight")} {data.tiers[String(n)]?.weight ?? 0}
            </p>
            <div className="sponsor-admin-grid">
              {items.map((s) => (
                <SponsorItem key={s.id} sponsor={s} onDelete={() => remove(s.id)} />
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}

function SponsorItem({ sponsor, onDelete }: { sponsor: SponsorDto; onDelete: () => void }) {
  const { t } = useI18n();
  const [name, setName] = useState(sponsor.name ?? "");
  const [url, setUrl] = useState(sponsor.url ?? "");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    setError("");
    try {
      await adminApi.updateSponsor(sponsor.id, { name, url });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.error"));
    }
  };

  return (
    <div className="sponsor-admin-item">
      <img src={api.sponsorImageUrl(sponsor.id)} alt={sponsor.name ?? ""} loading="lazy" />
      <input
        placeholder={t("sponsors.name")}
        value={name}
        onChange={(e) => { setName(e.target.value); setSaved(false); }}
      />
      <input
        placeholder="https://…"
        value={url}
        onChange={(e) => { setUrl(e.target.value); setSaved(false); }}
      />
      {error && <span className="error">{error}</span>}
      <div className="row" style={{ gap: 6 }}>
        <button onClick={save}>{t("manage.save")}{saved ? " ✓" : ""}</button>
        <button onClick={onDelete}>{t("sponsors.delete")}</button>
      </div>
    </div>
  );
}
