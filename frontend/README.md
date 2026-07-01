# Bibby — Frontend (SPA)

Single-Page-App (React + Vite + TypeScript), mehrsprachig (de/en), gehostet als
statisches Bundle auf **Scaleway Object Storage + CDN**.

## Starten

```bash
cd frontend
cp .env.example .env        # VITE_API_BASE auf die API setzen
npm install
npm run dev                 # http://localhost:5173
npm run build               # erzeugt dist/ für Object-Storage-Upload
```

> Node ist auf dem aktuellen Rechner nicht installiert — `npm` zuerst einrichten
> (z. B. `brew install node`), dann obige Befehle.

## Routen

Zwei getrennte Bereiche mit je eigener Navigation (`src/components/Layouts.tsx`).

**Läufer-Bereich** (`RunnerLayout`):

| Route | Inhalt |
|---|---|
| `/teilnahme` | Anmeldeformular (inkl. Team, T-Shirt) |
| `/teilnahme/ergebnisse` | Ergebnislisten (Gesamt / Altersklasse / Geschlecht) |
| `/manage?token=…` | Selbstverwaltung + Startnummer-PDF |

**Staff-Bereich** (`AdminLayout`, Login/Rollen bzw. Geräte-Token):

| Route | Inhalt |
|---|---|
| `/team` | Admin: Suche (Name/Startnummer) + Voll-Bearbeitung |
| `/team/special` | Special-Admin: Liste, Erfassungen je Startnummer, Strecken/Startzeiten, interne Ergebnisse, Geräte-Tokens |
| `/team/zeiterfassung` | Zeiterfassung (Ziffernfeld, Geräte-Token) – Ziel des QR-Codes |

**Weiterleitungen (alt → neu):** `/` → `/teilnahme`, `/results` → `/teilnahme/ergebnisse`,
`/admin` → `/team`, `/special-admin` → `/team/special`, `/timing?…` → `/team/zeiterfassung?…`.

Die Backend-API-Endpunkte sind in [../backend/README.md](../backend/README.md#api-übersicht)
dokumentiert.

## i18n

Eigener leichter Provider in `src/i18n.tsx` (Wörterbuch de/en, `useI18n().t()`).
Sprache wird in `localStorage` gemerkt. Neue Sprache = weiterer Block im
`translations`-Objekt.

## Struktur

```
src/
  main.tsx          Bootstrap (Router + I18nProvider)
  App.tsx           Layout, Navigation, Routen
  api.ts            typisierter API-Client + formatTime()
  i18n.tsx          Übersetzungen + Hook
  components/       LanguageSwitcher · TeamInput · Layouts (Runner/Admin)
  pages/            RegisterPage · ManagePage · ResultsPage
                    AdminPage · SpecialAdminPage · TimingPage · adminShared
  styles.css        Basis-Styling (CSS-Variablen, hell)
```

## Hinweis zum SPA-Routing auf Object Storage

Alle Routen sind Client-Routen. Beim statischen Hosting muss 404 → `index.html`
umgeleitet werden (CDN-/Bucket-Konfiguration), damit Deep-Links wie
`/teilnahme/ergebnisse` oder `/team/special` funktionieren.
