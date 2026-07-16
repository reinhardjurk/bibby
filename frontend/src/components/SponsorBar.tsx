import { useEffect, useRef, useState } from "react";
import { api, type SponsorDto, type SponsorsDto } from "../api";
import { useI18n } from "../i18n";

/** Dauer eines Anzeige-Slots im Rotationsmodus. Pro Slot wird eine Klasse nach
 *  ihrem Gewicht gelost -> über die Zeit exakt das konfigurierte Verhältnis. */
const SLOT_MS = 5000;

/** Die Liste wird pro Seitenaufruf nur EINMAL geholt, auch bei mehreren Leisten. */
let sponsorsCache: Promise<SponsorsDto> | null = null;
function loadSponsors(): Promise<SponsorsDto> {
  if (!sponsorsCache) sponsorsCache = api.listSponsors();
  return sponsorsCache;
}

/** Bandhöhe = größte konfigurierte Klassenhöhe -> das Band ändert seine Größe
 *  NIE beim Logowechsel (jedes Logo wird innerhalb dieser festen Höhe skaliert). */
function bandHeight(data: SponsorsDto): number {
  return Math.max(40, ...Object.values(data.tiers).map((t) => t.height));
}
const tierHeight = (data: SponsorsDto, tier: number) => data.tiers[String(tier)]?.height ?? 60;

export function SponsorBar() {
  const [data, setData] = useState<SponsorsDto | null>(null);

  useEffect(() => {
    let alive = true;
    loadSponsors()
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null)); // Sponsoren sind optional -> still scheitern
    return () => {
      alive = false;
    };
  }, []);

  if (!data || data.items.length === 0) return null;
  return data.display === "marquee" ? <Marquee data={data} /> : <Rotator data={data} />;
}

/** Ein Logo, rotierend (klassengewichtet). Immer genau EIN Bild im DOM. */
function Rotator({ data }: { data: SponsorsDto }) {
  const { t } = useI18n();
  const [current, setCurrent] = useState<SponsorDto | null>(null);
  const cursors = useRef<Map<number, number>>(new Map()); // Round-Robin je Klasse

  useEffect(() => {
    const byTier = new Map<number, SponsorDto[]>();
    for (const s of data.items) (byTier.get(s.tier) ?? byTier.set(s.tier, []).get(s.tier)!).push(s);

    const pickTier = () => {
      const tiers = [...byTier.keys()];
      const total = tiers.reduce((sum, ti) => sum + (data.tiers[String(ti)]?.weight ?? 0), 0);
      if (total <= 0) return tiers[0];
      let r = Math.random() * total;
      for (const ti of tiers) {
        r -= data.tiers[String(ti)]?.weight ?? 0;
        if (r <= 0) return ti;
      }
      return tiers[tiers.length - 1];
    };

    const next = () => {
      const tier = pickTier();
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

  if (!current) return null;
  return (
    <aside className="sponsors" style={{ height: bandHeight(data) }} aria-label={t("sponsors.label")}>
      <img
        key={current.id}
        className="sponsor-logo"
        src={api.sponsorImageUrl(current.id)}
        alt={current.name ?? t("sponsors.label")}
        style={{ maxHeight: tierHeight(data, current.tier) }}
        loading="lazy"
        decoding="async"
      />
    </aside>
  );
}

/** Laufband: alle Logos scrollen endlos horizontal (Größe je Klasse). */
function Marquee({ data }: { data: SponsorsDto }) {
  const { t } = useI18n();
  // Track verdoppeln -> nahtlose Schleife bei translateX(-50%).
  const track = [...data.items, ...data.items];
  const duration = Math.max(20, data.items.length * 6); // s
  return (
    <aside
      className="sponsors marquee"
      style={{ height: bandHeight(data) }}
      aria-label={t("sponsors.label")}
    >
      <div className="marquee-track" style={{ animationDuration: `${duration}s` }}>
        {track.map((s, i) => (
          <img
            key={`${s.id}-${i}`}
            className="marquee-logo"
            src={api.sponsorImageUrl(s.id)}
            alt={s.name ?? t("sponsors.label")}
            style={{ maxHeight: tierHeight(data, s.tier) }}
            loading="lazy"
            decoding="async"
          />
        ))}
      </div>
    </aside>
  );
}
