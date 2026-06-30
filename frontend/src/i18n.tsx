/** Leichtes i18n ohne externe Abhängigkeit: Context + t()-Hook. */
import { createContext, useContext, useState, type ReactNode } from "react";

export type Lang = "de" | "en";

type Dict = Record<string, string>;

const translations: Record<Lang, Dict> = {
  de: {
    "app.title": "Bibby",
    "nav.register": "Anmeldung",
    "nav.results": "Ergebnisse",
    "nav.admin": "Admin",

    "admin.title": "Verwaltung",
    "admin.login": "Anmelden",
    "admin.loginSent": "Falls ein Konto existiert, wurde ein Login-Link verschickt (lokal: in den Server-Logs als [login-link]).",
    "admin.logout": "Abmelden",
    "admin.registrations": "Anmeldungen",
    "admin.bib": "Nr.",
    "admin.name": "Name",
    "admin.competition": "Strecke",
    "admin.payment": "Zahlung",
    "admin.actions": "Aktionen",
    "admin.markPaid": "Als bezahlt markieren",
    "admin.internalResults": "Interne Ergebnisliste (vollständig)",
    "admin.notPublic": "nicht öffentlich",
    "admin.deviceTokens": "Geräte-Tokens (Zeitnahme)",
    "admin.tokenLabel": "Bezeichnung",
    "admin.offset": "Offset (s)",
    "admin.create": "Erstellen",
    "admin.revoke": "Sperren",
    "admin.tokenCreated": "Token erstellt (nur jetzt sichtbar)",

    "register.heading": "Zur Laufveranstaltung anmelden",
    "register.event": "Veranstaltung",
    "register.competition": "Strecke",
    "register.laps": "{n} Runde(n)",
    "register.firstName": "Vorname",
    "register.lastName": "Nachname",
    "register.birthDate": "Geburtsdatum",
    "register.gender": "Geschlecht",
    "register.gender.f": "weiblich",
    "register.gender.m": "männlich",
    "register.gender.x": "divers",
    "register.email": "E-Mail",
    "register.consentData": "Ich willige in die Verarbeitung meiner Daten ein.",
    "register.consentPublish": "Veröffentlichung meines Ergebnisses erlaubt.",
    "register.payment": "Zahlung",
    "register.method": "Zahlungsweg",
    "register.iban": "IBAN",
    "register.accountHolder": "Kontoinhaber/in",
    "register.mandate": "Ich erteile ein SEPA-Lastschriftmandat und ermächtige den Veranstalter, das Startgeld von meinem Konto einzuziehen.",
    "register.mandateRef": "Mandatsreferenz",
    "register.submit": "Anmelden",
    "register.success": "Anmeldung erfasst! Wir haben dir eine E-Mail mit deinem Verwaltungslink geschickt.",
    "register.manageLink": "Verwaltungslink (auch per E-Mail):",
    "register.price": "Startgeld",
    "pay.method.sepa_debit": "SEPA-Lastschrift",
    "pay.method.on_site": "Barzahlung bei Abholung",
    "pay.status.pending": "offen",
    "pay.status.paid": "bezahlt",
    "pay.status.cancelled": "storniert",

    "manage.heading": "Anmeldung verwalten",
    "manage.status": "Status",
    "manage.bib": "Startnummer",
    "manage.payment": "Zahlung",
    "manage.method": "Zahlungsweg",
    "manage.iban": "IBAN",
    "manage.notAssigned": "noch nicht vergeben",
    "manage.save": "Änderungen speichern",
    "manage.saved": "Gespeichert.",
    "manage.bibPdf": "Startnummer als PDF",
    "manage.noToken": "Kein gültiger Verwaltungslink.",

    "results.heading": "Ergebnisse",
    "results.rank": "Platz",
    "results.bib": "Nr.",
    "results.name": "Name",
    "results.category": "Klasse",
    "results.time": "Zeit",
    "results.dnf": "DNF",
    "results.nth": "{n}. Teilnahme",
    "results.empty": "Noch keine Ergebnisse.",

    "common.loading": "Lädt …",
    "common.choose": "Bitte wählen",
    "common.error": "Etwas ist schiefgelaufen.",
  },
  en: {
    "app.title": "Bibby",
    "nav.register": "Sign up",
    "nav.results": "Results",
    "nav.admin": "Admin",

    "admin.title": "Administration",
    "admin.login": "Sign in",
    "admin.loginSent": "If an account exists, a login link was sent (locally: in the server logs as [login-link]).",
    "admin.logout": "Sign out",
    "admin.registrations": "Registrations",
    "admin.bib": "No.",
    "admin.name": "Name",
    "admin.competition": "Course",
    "admin.payment": "Payment",
    "admin.actions": "Actions",
    "admin.markPaid": "Mark as paid",
    "admin.internalResults": "Internal results (complete)",
    "admin.notPublic": "not public",
    "admin.deviceTokens": "Device tokens (timing)",
    "admin.tokenLabel": "Label",
    "admin.offset": "Offset (s)",
    "admin.create": "Create",
    "admin.revoke": "Revoke",
    "admin.tokenCreated": "Token created (visible only now)",

    "register.heading": "Register for the race",
    "register.event": "Event",
    "register.competition": "Course",
    "register.laps": "{n} lap(s)",
    "register.firstName": "First name",
    "register.lastName": "Last name",
    "register.birthDate": "Date of birth",
    "register.gender": "Gender",
    "register.gender.f": "female",
    "register.gender.m": "male",
    "register.gender.x": "diverse",
    "register.email": "Email",
    "register.consentData": "I consent to the processing of my data.",
    "register.consentPublish": "Allow publication of my result.",
    "register.payment": "Payment",
    "register.method": "Payment method",
    "register.iban": "IBAN",
    "register.accountHolder": "Account holder",
    "register.mandate": "I grant a SEPA direct debit mandate and authorise the organiser to collect the entry fee from my account.",
    "register.mandateRef": "Mandate reference",
    "register.submit": "Register",
    "register.success": "Registration received! We emailed you a management link.",
    "register.manageLink": "Management link (also emailed):",
    "register.price": "Entry fee",
    "pay.method.sepa_debit": "SEPA direct debit",
    "pay.method.on_site": "Pay on bib pickup",
    "pay.status.pending": "open",
    "pay.status.paid": "paid",
    "pay.status.cancelled": "cancelled",

    "manage.heading": "Manage registration",
    "manage.status": "Status",
    "manage.bib": "Bib number",
    "manage.payment": "Payment",
    "manage.method": "Payment method",
    "manage.iban": "IBAN",
    "manage.notAssigned": "not yet assigned",
    "manage.save": "Save changes",
    "manage.saved": "Saved.",
    "manage.bibPdf": "Bib as PDF",
    "manage.noToken": "No valid management link.",

    "results.heading": "Results",
    "results.rank": "Rank",
    "results.bib": "No.",
    "results.name": "Name",
    "results.category": "Class",
    "results.time": "Time",
    "results.dnf": "DNF",
    "results.nth": "participation #{n}",
    "results.empty": "No results yet.",

    "common.loading": "Loading …",
    "common.choose": "Please choose",
    "common.error": "Something went wrong.",
  },
};

type I18nCtx = { lang: Lang; setLang: (l: Lang) => void; t: (key: string, vars?: Record<string, string | number>) => string };

const Ctx = createContext<I18nCtx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(
    (localStorage.getItem("bibby.lang") as Lang) || "de"
  );
  const setLangPersist = (l: Lang) => {
    localStorage.setItem("bibby.lang", l);
    setLang(l);
  };
  const t = (key: string, vars?: Record<string, string | number>) => {
    let s = translations[lang][key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  };
  return <Ctx.Provider value={{ lang, setLang: setLangPersist, t }}>{children}</Ctx.Provider>;
}

export function useI18n() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
