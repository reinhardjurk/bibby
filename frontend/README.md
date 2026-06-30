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

| Route | Inhalt | Backend |
|---|---|---|
| `/` | Anmeldeformular (Feature 1) + Zahlungsstart | `GET /events`, `GET /events/{id}/competitions`, `POST /registrations`, `POST /registrations/{id}/payment` |
| `/manage?token=…` | Selbstverwaltung (Feature 2) + Startnummer-PDF | `GET/PATCH /manage`, `GET /manage/bib.pdf` |
| `/results` | Ergebnislisten (Feature 4) mit Splits & Teilnahmezähler | `GET /events/{id}/results` |

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
  components/       LanguageSwitcher
  pages/            RegisterPage · ManagePage · ResultsPage
  styles.css        Basis-Styling (CSS-Variablen, hell)
```

## Hinweis zum SPA-Routing auf Object Storage

`/manage` und `/results` sind Client-Routen. Beim statischen Hosting muss
404 → `index.html` umgeleitet werden (CDN-/Bucket-Konfiguration), damit
Deep-Links funktionieren.
