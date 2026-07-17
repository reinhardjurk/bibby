/** Kleines "i" mit Zusatzinfo. Zeigt den Text bei Hover UND bei Fokus, damit er
 *  auch per Tastatur und auf Touch-Geräten (Antippen fokussiert) erreichbar ist. */
export function InfoTip({ text }: { text: string }) {
  return (
    <span className="infotip" tabIndex={0} role="note" aria-label={text}>
      <span className="infotip-icon" aria-hidden="true">
        i
      </span>
      <span className="infotip-bubble">{text}</span>
    </span>
  );
}
