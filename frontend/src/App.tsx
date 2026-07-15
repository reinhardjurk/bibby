import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AdminLayout, RunnerLayout } from "./components/Layouts";
import { AdminPage } from "./pages/AdminPage";
import { ManagePage } from "./pages/ManagePage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResultsPage } from "./pages/ResultsPage";
import { ResultsPrintPage } from "./pages/ResultsPrintPage";
import { SepaAdminPage } from "./pages/SepaAdminPage";
import { SpecialAdminPage } from "./pages/SpecialAdminPage";
import { SponsorsAdminPage } from "./pages/SponsorsAdminPage";
import { TimingPage } from "./pages/TimingPage";
import { VerySpecialAdminPage } from "./pages/VerySpecialAdminPage";

/** Alte QR-/Deep-Links auf die neue Zeiterfassungs-URL (inkl. Query). */
function TimingRedirect() {
  const loc = useLocation();
  return <Navigate to={`/team/zeiterfassung${loc.search}`} replace />;
}

export default function App() {
  return (
    <Routes>
      {/* Läufer-Bereich */}
      <Route element={<RunnerLayout />}>
        <Route path="/" element={<Navigate to="/teilnahme" replace />} />
        <Route path="/teilnahme" element={<RegisterPage />} />
        <Route path="/teilnahme/ergebnisse" element={<ResultsPage />} />
        <Route path="/manage" element={<ManagePage />} />
      </Route>

      {/* Staff-Bereich */}
      <Route path="/team" element={<AdminLayout />}>
        <Route index element={<AdminPage />} />
        <Route path="special" element={<SpecialAdminPage />} />
        <Route path="veryspecial" element={<VerySpecialAdminPage />} />
        <Route path="sepa" element={<SepaAdminPage />} />
        <Route path="ergebnisdruck" element={<ResultsPrintPage />} />
        <Route path="sponsoren" element={<SponsorsAdminPage />} />
        <Route path="zeiterfassung" element={<TimingPage />} />
      </Route>

      {/* Weiterleitungen von den alten Pfaden */}
      <Route path="/results" element={<Navigate to="/teilnahme/ergebnisse" replace />} />
      <Route path="/admin" element={<Navigate to="/team" replace />} />
      <Route path="/special-admin" element={<Navigate to="/team/special" replace />} />
      <Route path="/timing" element={<TimingRedirect />} />
    </Routes>
  );
}
