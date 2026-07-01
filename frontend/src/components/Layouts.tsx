import { NavLink, Outlet } from "react-router-dom";
import { useI18n } from "../i18n";
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

/** Staff-Bereich (/team). */
export function AdminLayout() {
  const { t } = useI18n();
  return (
    <div className="app">
      <header>
        <span className="brand">{t("app.title")}</span>
        <nav>
          <NavLink to="/team" end>{t("nav.admin")}</NavLink>
          <NavLink to="/team/special">{t("nav.special")}</NavLink>
          <NavLink to="/team/zeiterfassung">{t("nav.timing")}</NavLink>
        </nav>
        <LanguageSwitcher />
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
