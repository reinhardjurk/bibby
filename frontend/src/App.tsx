import { NavLink, Route, Routes } from "react-router-dom";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { useI18n } from "./i18n";
import { AdminPage } from "./pages/AdminPage";
import { ManagePage } from "./pages/ManagePage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResultsPage } from "./pages/ResultsPage";

export default function App() {
  const { t } = useI18n();
  return (
    <div className="app">
      <header>
        <span className="brand">{t("app.title")}</span>
        <nav>
          <NavLink to="/" end>{t("nav.register")}</NavLink>
          <NavLink to="/results">{t("nav.results")}</NavLink>
          <NavLink to="/admin">{t("nav.admin")}</NavLink>
        </nav>
        <LanguageSwitcher />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<RegisterPage />} />
          <Route path="/manage" element={<ManagePage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  );
}
