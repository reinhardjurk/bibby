# Bibby — Benutzerhandbuch für das Team

Dieses Handbuch beschreibt die Bedienung des Team-Bereichs von Bibby für den
Lauftag und die Vorbereitung. Es ist nach **Zielgruppen** gegliedert — such dir
das Kapitel, das zu deiner Aufgabe passt.

- [Grundlagen für alle](#grundlagen-für-alle)
- [Kapitel 1 — Empfang, Startnummernausgabe & Kassieren](#kapitel-1--empfang-startnummernausgabe--kassieren) · Tab **Admin**
- [Kapitel 2 — Lauf-Administration](#kapitel-2--lauf-administration) · Tabs **Special-Admin**, **Events**, **Ergebnisdruck**
- [Kapitel 3 — Sponsorenverwaltung](#kapitel-3--sponsorenverwaltung) · Tab **Sponsoren**
- [Kapitel 4 — SEPA-Verwaltung](#kapitel-4--sepa-verwaltung) · Tab **SEPA**
- [Häufige Probleme](#häufige-probleme)

---

## Grundlagen für alle

### Anmelden

Der Team-Bereich liegt unter **https://anmeldung.run-bibby.de/team**. Oben
findest du die Navigationsreiter (Tabs):

**Admin · Special-Admin · Events · SEPA · Ergebnisdruck · Sponsoren · Zeiterfassung**

Beim ersten Öffnen eines Tabs erscheint eine **Login-Maske** (E-Mail +
Passwort). Nach dem Login bleibst du **72 Stunden** angemeldet; danach ist ein
erneuter Login nötig. Oben rechts kannst du zwischen **Deutsch/Englisch**
umschalten.

Team-Zugänge legt ein **Administrator** im Tab **Special-Admin** unter
**„Benutzer & Rollen"** an (siehe [Kapitel 2.4](#24-benutzer--rollen-nur-admin)).

### Rollen (wer darf was)

| Rolle | Darf |
|---|---|
| **admin** | alles (inkl. Event löschen, Mailversand auf „Live" schalten) |
| **race_office** | Anmeldungen, Startnummern, Zahlungen, Events/Strecken, SEPA, Sponsoren, Urkunden |
| **timing** | Zeiten erfassen/korrigieren, Zeitnahme-Geräte |
| **viewer** | nur ansehen/exportieren |

Wenn ein Button oder ein Tab bei dir fehlt, hat dein Zugang die nötige Rolle
nicht.

### Ganz unten auf jeder Seite

Eine kleine Zeile `Frontend … · Backend … · DB …` zeigt die aktuelle
Programmversion — praktisch, wenn du dem technischen Team ein Problem meldest.

---

## Kapitel 1 — Empfang, Startnummernausgabe & Kassieren

> **Tab: Admin** · benötigt Rolle **race_office** (oder admin) zum Bearbeiten.
> Diese Ansicht ist für den Empfangstisch am Veranstaltungstag gedacht.

### Überblick

Jeder Teilnehmer bekommt seine **Startnummer bereits bei der Online-Anmeldung
automatisch zugeteilt**. Am Empfang geht es also darum, den Teilnehmer zu
**finden**, ihm die passende Startnummer **auszuhändigen** und — falls er bar
zahlt — die Zahlung als **bezahlt** zu markieren.

### Schritt für Schritt

1. **Event wählen** (oben im Dropdown), falls mehrere existieren.
2. Im **Suchfeld** den Namen **oder** die Startnummer eingeben. Die Liste
   aktualisiert sich automatisch beim Tippen und zeigt **Startnummer, Name und
   Strecke**.
3. Beim richtigen Teilnehmer auf **Bearbeiten** klicken. Es öffnet sich das
   Detailformular.
4. **Startnummer aushändigen:** Die zugeteilte Nummer steht im Feld
   *Startnummer*. Händige die entsprechende physische Startnummer aus. Muss eine
   andere Nummer vergeben werden (z. B. Nummer beschädigt), kannst du sie hier
   ändern und **Speichern**.
5. **Kassieren (Barzahlung):** Steht *Zahlungsart* auf „Barzahlung bei Abholung"
   und der Teilnehmer zahlt jetzt, setze **Zahlstatus** auf **„bezahlt"** und
   **Speichern**. Damit ist im System dokumentiert, dass das Startgeld erhalten
   wurde.

### Was du im Detailformular sonst ändern kannst

- **Person:** Vor-/Nachname, Geburtsdatum, Geschlecht
- **Kontakt/Sprache:** E-Mail, Sprache der Bestätigungen
- **Zuordnung:** Team, T-Shirt-Größe, **Strecke**
- **Startnummer** (frei änderbar)
- **Status der Anmeldung:** „bestätigt" oder „storniert"
- **Zahlungsart** (Barzahlung / SEPA-Lastschrift) und **Zahlstatus** (offen /
  bezahlt / storniert)
- Bei SEPA wird die hinterlegte **IBAN maskiert** angezeigt (z. B. `DE89 **** 3000`).

### Nützlich zu wissen

- Der **Betrag** wird bei der Anmeldung berechnet und als Momentaufnahme
  gespeichert; die T-Shirt-Wahl ändert ihn nicht.
- Der Teilnehmer kann seine Startnummer und (nach dem Lauf) seine Urkunde auch
  selbst über den **Verwaltungslink** aus seiner Bestätigungs-E-Mail abrufen.
- **Stornierung:** Setzt du den Status auf „storniert", bleibt der Datensatz
  erhalten (er wird nicht gelöscht).

---

## Kapitel 2 — Lauf-Administration

> **Tabs: Special-Admin, Events, Ergebnisdruck** · benötigt in der Regel
> **race_office** (einzelne Aktionen nur **admin**).

Diese drei Tabs bilden zusammen die Organisation des Laufes ab: Stammdaten
(Events/Strecken), operativer Ablauf am Renntag (Zeiten, Ergebnisse) und der
Urkundendruck.

### 2.1 Tab „Events" — Stammdaten anlegen und pflegen

Hier legst du **vor** der Veranstaltung alles Grundlegende an.

- **Kopf-Logo:** Ganz oben kannst du ein globales Logo hochladen, das auf der
  Anmeldeseite und der Teilnehmer-Detailseite oben mittig erscheint. Über
  „Logo entfernen" wieder löschen.
- **Neues Event anlegen** („Neues Event"): Name, Jahr, Datum,
  Anmeldeschluss, Standard-Startzeit, Jugend-Stichtag, T-Shirt-Option. Dazu
  **eine oder mehrere Strecken**, je Strecke:
  - **Titel** (z. B. „3,3 km Running") — unterscheidet die Strecken
  - **Preis** und optional **ermäßigter Preis** (Jugend)
  - **Startzeit** der Strecke (überschreibt die Standard-Startzeit)
  - **Altersklassen-Schema:** 5-Jahres-Klassen / 1-Jahres-Klassen / keine
  - **Geschlechtswertung:** ja/nein
- **Event-Einstellungen** (nach Auswahl eines Events):
  - T-Shirt-Optionen, Jugend-Stichtag, „T-Shirt inklusive"
  - **Urkunden-Druckversatz** (verschiebt den Aufdruck vertikal, in „Zeilen";
    negativ = nach oben, positiv = nach unten)
  - **Urkunden-Hintergrund** hochladen (A4-Vorlage; Name/Zeit werden mittig
    daraufgelegt)
  - **Startnummer-Hintergrund** hochladen (A5-quer-Vorlage)
- **Strecken bearbeiten:** Für ein bestehendes Event kannst du Startzeit,
  Preise, Altersklassen-Schema und Geschlechtswertung je Strecke ändern.
- **Event löschen:** nur mit Rolle **admin** (löscht das Event samt Anmeldungen
  — mit Bedacht verwenden).

> **Wichtig:** Die **Startzeit** (der Strecke bzw. das Standard-Startdatum des
> Events) muss gesetzt sein, sonst kann keine Laufzeit berechnet werden und alle
> Teilnehmer erscheinen als **DNF**.

### 2.2 Tab „Special-Admin" — Renntag-Betrieb

Nach Auswahl des Events findest du hier die operativen Werkzeuge:

- **Anmeldungsliste:** Alle Anmeldungen des Events (durchblätterbar).
- **Erfassungen zu einer Startnummer:** Startnummer eingeben, um die einzelnen
  Ziel-Erfassungen zu sehen. Du kannst eine Fehl­erfassung auf **„ignoriert"**
  setzen oder **löschen**, oder — wenn für eine Nummer **keine** Erfassung
  vorliegt — **manuell eine Zielzeit hinzufügen** (Rolle timing).
  *Die Zielzeit einer Nummer ist der Mittelwert aller nicht ignorierten
  Erfassungen.*
- **Alle Laufzeiten berechnen:** Rechnet die Nettozeiten neu und speichert sie.
  Die Rückmeldung nennt die **Anzahl** ermittelter Zeiten — **0** ist ein klares
  Signal für eine fehlende Startzeit oder fehlende Erfassungen.
- **Interne Ergebnisliste:** Vollständige Wertung (auch Teilnehmer ohne
  Veröffentlichungs-Einwilligung), nur für den internen Gebrauch.
- **Zeitnahme-Geräte:** Erzeugt Zugangs-Codes (mit QR-Code) für die
  Zeiterfassungs-Geräte. Code/QR bleiben **dauerhaft sichtbar**, damit ein Gerät
  jederzeit neu eingerichtet werden kann.
- **Mailversand Test/Live:** Schalter zwischen **Test** (alle Mails gehen an
  eine feste Testadresse) und **Live** (echte Empfänger). Das Umschalten auf
  Live ist bewusst **nur für admin** und muss bestätigt werden.
- **Mailvorlage:** Betreff und Text der Anmeldebestätigung (Deutsch/Englisch)
  direkt bearbeiten. Der Platzhalter **`{link}`** im Text wird durch den
  persönlichen Verwaltungslink des Teilnehmers ersetzt — er muss erhalten
  bleiben. Änderungen wirken sofort, ohne dass etwas neu ausgerollt werden muss.

### 2.4 Benutzer & Rollen (nur admin)

Ebenfalls im Tab **Special-Admin**, ganz unten (nur mit Rolle **admin**
sichtbar), verwaltest du die Team-Zugänge:

- **Neuen Benutzer anlegen:** E-Mail, Name, Passwort (mind. 6 Zeichen) und die
  gewünschten **Rollen** per Häkchen. Für den Empfang/Kassieren, Sponsoren und
  SEPA genügt **Wettkampfbüro** (`race_office`); für die Zeitnahme
  **Zeitnahme** (`timing`); reine Zuschauer bekommen **Nur lesen** (`viewer`).
  Mehrere Rollen sind möglich.
- **Rollen ändern / deaktivieren:** In der Liste kannst du je Nutzer die
  Rollen-Häkchen anpassen, den Zugang **aktiv/inaktiv** schalten und ein
  **neues Passwort** setzen — dann **Speichern**.
- **Schutz vor Selbst-Aussperren:** Den **eigenen** Zugang kannst du weder
  deaktivieren noch dir selbst die Admin-Rolle entziehen.

**Rollenübersicht:** Admin (alles) · Wettkampfbüro (Anmeldungen, Startnummern,
Zahlungen, Events, SEPA, Sponsoren, Urkunden) · Zeitnahme (Zeiten & Geräte) ·
Nur lesen (ansehen/exportieren).

### 2.3 Tab „Ergebnisdruck" — Urkunden

Nachdem Zeiten erfasst und berechnet wurden, druckst du hier die Urkunden. Alle
Downloads sind PDFs.

1. **Event wählen.**
2. **„Hintergrund mitdrucken"** an-/abwählen: mit Häkchen wird die hochgeladene
   Urkunden-Vorlage mitgedruckt; ohne Häkchen nur Text (praktisch für
   vorgedrucktes Urkundenpapier).
3. **Einzelne Urkunde:** Startnummer eingeben → **Drucken**.
4. **Sammeldruck je Lauf:** Strecke wählen. Dann:
   - **„Alle Urkunden des Laufs"**: ein PDF mit allen Urkunden der Strecke,
     sortiert nach Altersklasse (aufsteigend), Geschlecht und innerhalb der
     Gruppe **schlechteste Platzierung zuerst** — passend für die
     Siegerehrung von hinten nach vorne.
   - **Wertungsgruppen-Liste:** je Gruppe (Altersklasse × Geschlecht) mit
     Teilnehmerzahl und eigenem **Download**-Button.

> Eine Urkunde ist nur verfügbar, wenn für den Teilnehmer eine **Zielzeit**
> vorliegt.

---

## Kapitel 3 — Sponsorenverwaltung

> **Tab: Sponsoren** · benötigt Rolle **race_office** (oder admin).

Die Sponsorenleiste erscheint automatisch **oben und unten** auf der
Anmeldeseite und der Teilnehmer-Detailseite. Es gibt **5 Klassen** (1 = größte
Präsenz … 5 = kleinste).

### Anzeigemodus

- **Rotation:** Es wird immer genau ein Logo gezeigt; die Klassen werden nach
  ihrem **Gewicht** eingeblendet (das Gewichtsverhältnis bestimmt die
  Anzeigezeit, z. B. 30:20:10:5:1).
- **Laufband:** Alle Logos scrollen endlos durch. Die **Geschwindigkeit**
  (Sekunden pro Durchlauf) ist einstellbar.

### Klassen konfigurieren

Je Klasse legst du fest:
- **Gewicht** — Zeitanteil in der Rotation
- **Höhe** — maximale Anzeigehöhe in Pixel (kleinere Klassen = kleiner
  dargestellt)

Die **Bandhöhe bleibt konstant** (größte Klassenhöhe) — die Leiste springt beim
Logowechsel nie in der Größe.

### Logo hochladen

Beim Upload gibst du an:
- **Klasse** (1–5)
- **Name** (optional)
- **Ziel-URL** (optional) — ist eine URL hinterlegt, wird das Logo anklickbar
  (öffnet in neuem Tab)
- **Bilddatei** (PNG/JPG/WebP oder SVG)

Raster-Logos werden **automatisch serverseitig** auf eine einheitliche Höhe
verkleinert (kleinere Dateien, gleichmäßige Qualität); SVG bleibt unverändert.

### Verwalten

In der Liste kannst du je Sponsor **Name und URL bearbeiten** oder den Eintrag
**löschen**. Eine Vorschau des Logos wird angezeigt.

---

## Kapitel 4 — SEPA-Verwaltung

> **Tab: SEPA** · benötigt Rolle **race_office** (oder admin).

Teilnehmer, die bei der Anmeldung **SEPA-Lastschrift** gewählt haben, haben eine
verschlüsselt gespeicherte IBAN und ein Mandat hinterlegt. Über diesen Tab
erzeugst du die **Einzugsliste** als CSV-Datei für die Weiterverarbeitung in
deiner Bank-/Tabellensoftware.

### Export erstellen

1. **Event wählen.**
2. Optional **„auch bereits exportierte einschließen"** anhaken. Standardmäßig
   enthält der Export nur die **offenen, noch nicht exportierten** Lastschriften.
3. Auf den **Export-Button** klicken. Es lädt eine **CSV-Datei** herunter
   (Semikolon-getrennt, UTF-8 mit BOM — Excel erkennt Umlaute korrekt).

Die Datei enthält je Zeile: **Startnummer, Teilnehmer, Kontoinhaber, IBAN,
Betrag, Währung, Mandatsreferenz, Mandatsdatum, Verwendungszweck**.

### Wichtige Hinweise

- Mit dem Export werden die enthaltenen Lastschriften als **„exportiert"
  markiert**, damit du sie nicht versehentlich doppelt einziehst. Ein erneuter
  Export ohne das Häkchen enthält sie deshalb nicht mehr; mit dem Häkchen
  „bereits exportierte einschließen" holst du sie wieder mit dazu.
- Nach dem tatsächlichen Bankeinzug solltest du die betreffenden Anmeldungen im
  Tab **Admin** auf **Zahlstatus „bezahlt"** setzen.
- Steht in der IBAN-Spalte **`IBAN_NICHT_ENTSCHLUESSELBAR`**, konnte diese eine
  IBAN technisch nicht entschlüsselt werden (i. d. R. Alt-/Testdaten nach einem
  Schlüsselwechsel). Der restliche Export ist davon nicht betroffen; melde
  solche Fälle dem technischen Team.
- Eine fertige **pain.008-XML** (SEPA-Bankdatei) erzeugt Bibby derzeit noch
  nicht — nur die CSV.

---

## Häufige Probleme

| Symptom | Ursache / Lösung |
|---|---|
| **Alle Teilnehmer sind „DNF"** | Startzeit der Strecke/​des Events fehlt. Im Tab **Events** die Startzeit setzen, dann im **Special-Admin** „Alle Laufzeiten berechnen". |
| **„Alle Laufzeiten berechnen" meldet 0** | Keine Startzeit oder keine Ziel-Erfassungen vorhanden. |
| **Urkunde/Ergebnis fehlt für einen Teilnehmer** | Es liegt keine Zielzeit vor. Im **Special-Admin** unter „Erfassungen zu einer Startnummer" prüfen oder manuell eine Zeit hinzufügen. |
| **Ein Tab/Button fehlt bei mir** | Dein Zugang hat die nötige Rolle nicht — beim technischen Team melden. |
| **Login klappt nicht** | E-Mail/Passwort prüfen; Zugänge legt der technische Administrator an. Nach 72 h ist ein erneuter Login nötig. |
| **Teilnehmer bekommt keine E-Mail** | Ggf. steht der Mailversand auf **Test** (Special-Admin → Mailversand Test/Live). Für echte Mails auf **Live** schalten (nur admin). |
| **Die erste Seite lädt lange** | Kaltstart des Servers (einige Sekunden), wenn länger niemand zugegriffen hat — danach schnell. |
