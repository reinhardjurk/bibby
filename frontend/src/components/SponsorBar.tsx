import { useEffect, useRef, useState } from "react";
import { api, type SponsorDto, type SponsorsDto } from "../api";
import { useI18n } from "../i18n";

/** Dauer eines Anzeige-Slots. Pro Slot wird eine Klasse nach ihrem Gewicht
 *  gelost -> über die Zeit entspricht der Anteil je Klasse exakt dem
 *  konfigurierten Verhältnis (z. B. 30:20:10:5:1). */
const SLOT_MS = 5000;

/** Klasse nach Gewicht losen (nur Klassen, die auch Logos haben). */
function pickTier(tiers: SponsorsDto["tiers"], byTier: Map<number, SponsorDto[]>): number {
  const available = [...byTier.keys()];
  const total = available.reduce((sum, t) => sum + (tiers[String(t)]?.weight ?? 0), 0);
  if (total <= 0) return available[0];
  let r = Math.random() * total;
  for (const t of available) {
    r -= tiers[String(t)]?.weight ?? 0;
    if (r <= 0) return t;
  }
  return available[available.length - 1];
}

/**
 * Sponsorenanzeige: lädt nur eine kleine JSON-Liste und zeigt immer genau EIN
 * Logo (rotierend) – dadurch minimaler Einfluss auf das Ladeverhalten. Die
 * Bilder kommen lazy und sind langlebig gecacht.
 */
export function SponsorBar() {
  const { t } = useI18n();
  const [data, setData] = useState<SponsorsDto | null>(null);
  const [current, setCurrent] = useState<SponsorDto | null>(null);
  // Round-Robin-Zeiger je Klasse: jedes Logo einer Klasse kommt gleich oft dran.
  const cursors = useRef<Map<number, number>>(new Map());

  useEffect(() => {
    let alive = true;
    api
      .listSponsors()
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null)); // Sponsoren sind optional -> still scheitern
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!data || data.items.length === 0) return;
    const byTier = new Map<number, SponsorDto[]>();
    for (const s of data.items) {
      const list = byTier.get(s.tier);
      if (list) list.push(s);
      else byTier.set(s.tier, [s]);
    }

    const next = () => {
      const tier = pickTier(data.tiers, byTier);
      const list = byTier.get(tier) ?? [];
      if (!list.length) return;
      const i = (cursors.current.get(tier) ?? 0) % list.length;
      cursors.current.set(tier, i + 1);
      setCurrent(list[i]);
    };

    next();
    const h = setInterval(next, SLOT_MS);
    return () => clearInterval(h);
  }, [data]);

  if (!data || data.items.length === 0 || !current) return null;

  const height = data.tiers[String(current.tier)]?.height ?? 60;

  return (
    <aside className="sponsors" aria-label={t("sponsors.label")}>
      <span className="sponsors-label">{t("sponsors.label")}</span>
      <img
        key={current.id}
        className="sponsor-logo"
        src={api.sponsorImageUrl(current.id)}
        alt={current.name ?? t("sponsors.label")}
        style={{ height }}
        loading="lazy"
        decoding="async"
      />
    </aside>
  );
}
