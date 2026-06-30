import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type ManageView } from "../api";
import { useI18n } from "../i18n";

export function ManagePage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [data, setData] = useState<ManageView | null>(null);
  const [email, setEmail] = useState("");
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
      })
      .catch((e) => setError(e instanceof Error ? e.message : t("common.error")));
  }, [token]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaved(false);
    setError("");
    try {
      await api.updateManage(token, { email });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    }
  };

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!data) return <div className="card">{t("common.loading")}</div>;

  return (
    <form className="card" onSubmit={save}>
      <h2>{t("manage.heading")}</h2>
      <p>
        {data.first_name} {data.last_name} — {t("register.laps", { n: data.competition_lap_count })}
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

      <label>
        {t("register.email")}
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>

      {saved && <p className="success">{t("manage.saved")}</p>}
      <button className="primary" type="submit">{t("manage.save")}</button>

      {data.registration.bib_number != null && (
        <p>
          <a href={api.bibPdfUrl(token)} target="_blank" rel="noreferrer">{t("manage.bibPdf")}</a>
        </p>
      )}
    </form>
  );
}
