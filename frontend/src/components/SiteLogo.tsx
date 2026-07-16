import { useState } from "react";
import { api } from "../api";

/** Globales Kopf-Logo, oben mittig. Ist keins hinterlegt (404), rendert nichts
 *  – keine zusätzliche Abfrage nötig, das <img> lädt lazy und cached. */
export function SiteLogo() {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;
  return (
    <img
      className="site-logo"
      src={api.siteLogoUrl()}
      alt=""
      onError={() => setVisible(false)}
      decoding="async"
    />
  );
}
