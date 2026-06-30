import { useEffect, useState, type FormEvent } from "react";
import { api, type CompetitionDto, type EventDto, type RegistrationOut } from "../api";
import { useI18n } from "../i18n";

export function RegisterPage() {
  const { t, lang } = useI18n();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [competitions, setCompetitions] = useState<CompetitionDto[]>([]);
  const [eventId, setEventId] = useState("");
  const [competitionId, setCompetitionId] = useState("");
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    birth_date: "",
    gender: "",
    email: "",
    consent_data: false,
    consent_publish: false,
    payment_method: "on_site",
    iban: "",
    account_holder: "",
    mandate_consent: false,
  });
  const [result, setResult] = useState<RegistrationOut | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listEvents().then((e) => {
      setEvents(e);
      if (e[0]) setEventId(e[0].id);
    }).catch(() => setError(t("common.error")));
  }, []);

  useEffect(() => {
    if (!eventId) return;
    api.listCompetitions(eventId).then(setCompetitions).catch(() => setError(t("common.error")));
  }, [eventId]);

  const sepa = form.payment_method === "sepa_debit";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const out = await api.register({ event_id: eventId, competition_id: competitionId, ...form });
      setResult(out);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    const link = `${window.location.origin}/manage?token=${result.manage_token}`;
    return (
      <div className="card">
        <p className="success">{t("register.success")}</p>
        <p>
          <strong>{t("register.manageLink")}</strong>
          <br />
          <a href={link}>{link}</a>
        </p>
        {result.bib_number != null && (
          <p>
            {t("manage.bib")}: <strong>{result.bib_number}</strong>
          </p>
        )}
        {result.mandate_reference && (
          <p>
            {t("register.mandateRef")}: <strong>{result.mandate_reference}</strong>
          </p>
        )}
        {result.manage_token && result.bib_number != null && (
          <p>
            <a href={api.bibPdfUrl(result.manage_token)} target="_blank" rel="noreferrer">
              {t("manage.bibPdf")}
            </a>
          </p>
        )}
      </div>
    );
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>{t("register.heading")}</h2>
      {error && <p className="error">{error}</p>}

      <label>
        {t("register.event")}
        <select value={eventId} onChange={(e) => setEventId(e.target.value)} required>
          {events.map((ev) => (
            <option key={ev.id} value={ev.id}>{ev.name} ({ev.year})</option>
          ))}
        </select>
      </label>

      <label>
        {t("register.competition")}
        <select value={competitionId} onChange={(e) => setCompetitionId(e.target.value)} required>
          <option value="">{t("common.choose")}</option>
          {competitions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title_i18n?.[lang] || t("register.laps", { n: c.lap_count })}
              {c.price_cents > 0 ? ` — ${(c.price_cents / 100).toFixed(2)} ${c.currency}` : ""}
            </option>
          ))}
        </select>
      </label>

      <div className="row">
        <label>
          {t("register.firstName")}
          <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
        </label>
        <label>
          {t("register.lastName")}
          <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
        </label>
      </div>

      <div className="row">
        <label>
          {t("register.birthDate")}
          <input type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} required />
        </label>
        <label>
          {t("register.gender")}
          <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} required>
            <option value="">{t("common.choose")}</option>
            <option value="f">{t("register.gender.f")}</option>
            <option value="m">{t("register.gender.m")}</option>
            <option value="x">{t("register.gender.x")}</option>
          </select>
        </label>
      </div>

      <label>
        {t("register.email")}
        <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
      </label>

      {/* Zahlungsweg */}
      <fieldset className="payment">
        <legend>{t("register.payment")}</legend>
        <label className="check">
          <input
            type="radio"
            name="method"
            checked={form.payment_method === "on_site"}
            onChange={() => setForm({ ...form, payment_method: "on_site" })}
          />
          {t("pay.method.on_site")}
        </label>
        <label className="check">
          <input
            type="radio"
            name="method"
            checked={sepa}
            onChange={() => setForm({ ...form, payment_method: "sepa_debit" })}
          />
          {t("pay.method.sepa_debit")}
        </label>

        {sepa && (
          <>
            <label>
              {t("register.accountHolder")}
              <input
                value={form.account_holder}
                onChange={(e) => setForm({ ...form, account_holder: e.target.value })}
                required={sepa}
              />
            </label>
            <label>
              {t("register.iban")}
              <input
                value={form.iban}
                onChange={(e) => setForm({ ...form, iban: e.target.value })}
                placeholder="DE.."
                required={sepa}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.mandate_consent}
                onChange={(e) => setForm({ ...form, mandate_consent: e.target.checked })}
                required={sepa}
              />
              {t("register.mandate")}
            </label>
          </>
        )}
      </fieldset>

      <label className="check">
        <input type="checkbox" checked={form.consent_data} onChange={(e) => setForm({ ...form, consent_data: e.target.checked })} required />
        {t("register.consentData")}
      </label>
      <label className="check">
        <input type="checkbox" checked={form.consent_publish} onChange={(e) => setForm({ ...form, consent_publish: e.target.checked })} />
        {t("register.consentPublish")}
      </label>

      <button className="primary" type="submit" disabled={busy || !competitionId}>
        {busy ? t("common.loading") : t("register.submit")}
      </button>
    </form>
  );
}
