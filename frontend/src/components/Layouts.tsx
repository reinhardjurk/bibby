import { NavLink, Outlet, useLocation } from "react-router-dom";
import { canAccessTab } from "../api";
import { useI18n } from "../i18n";
import { useStaffRoles } from "../pages/adminShared";
import { LanguageSwitcher } from "./LanguageSwitcher";

/** Öffentlicher Läufer-Bereich (/teilnahme). */
export function RunnerLayout() {
  const { t } = useI18n();
  return (
    <div className="app">
      <header>
        <span className="brand">{t("app.title")}</span>
        <nav>
          <NavLink to="/teilnahme" end>{t("nav.register")}</NavLink>
          <NavLink to="/teilnahme/ergebnisse">{t("nav.results")}</NavLink>
        </nav>
        <LanguageSwitcher />
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}

/** Staff-Bereich (/team). Tabs werden rollenabhängig ein-/ausgeblendet;
 *  solange niemand eingeloggt ist, sind alle sichtbar (Login je Seite). */
export function AdminLayout() {
  const { t } = useI18n();
  const { authed, roles } = useStaffRoles();
  const loc = useLocation();

  const tabs: { to: string; label: string; end?: boolean }[] = [
    { to: "/team", label: t("nav.admin"), end: true },
    { to: "/team/ergebnisdruck", label: t("nav.resultsPrint") },
    { to: "/team/zeiterfassung", label: t("nav.timing") },
    { to: "/team/special", label: t("nav.special") },
    { to: "/team/sponsoren", label: t("nav.sponsors") },
    { to: "/team/veryspecial", label: t("nav.veryspecial") },
    { to: "/team/statistiken", label: t("nav.stats") },
    { to: "/team/sepa", label: t("nav.sepa") },
  ];

  // Reiner Geräte-/QR-Operator der Zeiterfassung (kein Staff-Login): keine
  // Navigation zu anderen Bereichen. Eingeloggte Staff-Nutzer sehen die nach
  // Rollen gefilterten Tabs; Ausgeloggte anderswo sehen alle (Login je Seite).
  const kioskOnly = loc.pathname.startsWith("/team/zeiterfassung") && !authed;
  const visible = kioskOnly
    ? []
    : authed
      ? tabs.filter((tab) => canAccessTab(roles, tab.to))
      : tabs;

  return (
    <div className="app">
      <header>
        <span className="brand">{t("app.title")}</span>
        <nav>
          {visible.map((tab) => (
            <NavLink key={tab.to} to={tab.to} end={tab.end}>
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <LanguageSwitcher />
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
