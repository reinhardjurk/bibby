import { useI18n, type Lang } from "../i18n";

export function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  const langs: Lang[] = ["de", "en"];
  return (
    <div className="lang-switch">
      {langs.map((l) => (
        <button
          key={l}
          className={l === lang ? "active" : ""}
          onClick={() => setLang(l)}
          aria-pressed={l === lang}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
