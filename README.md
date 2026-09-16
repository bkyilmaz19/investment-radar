# Short-Term Investment Radar

Externes, automatisch aktualisiertes Dashboard für **kurzfristige Aktien-Setups (wenige Stunden bis maximal etwa 2 Handelstage)**.

## Was die neue Version berücksichtigt

- 1-Tages- und 5-Tages-Momentum
- relatives Handelsvolumen
- aktuelle Nachrichten / Event-Katalysatoren
- ATR / kurzfristige Volatilität
- Premarket-Gap und Premarket-Momentum, sobald die Daten verfügbar sind
- Entry-Trigger statt blindem Sofortkauf
- Stop-/Invalidation-Orientierung
- erstes Gewinnziel als Orientierung
- klaren Exit spätestens nach sehr kurzem Zeithorizont

Die Scores sind **keine Garantie**. Das Dashboard soll Setups priorisieren, nicht sichere Gewinner behaupten.

## Automatische Updates

Der GitHub-Workflow läuft an Handelstagen zweimal:

- **08:07 Europe/Berlin**: früher Morning-Scan mit News, Daily-Momentum, Volumen und ATR.
- **10:17 Europe/Berlin**: zweiter Scan, damit US-Premarket-Daten/Gaps einfließen können, sofern der Datenfeed sie liefert.

Die Minuten liegen absichtlich nicht genau auf der vollen Stunde, weil GitHub geplante Jobs zu stark frequentierten Zeiten verzögern kann.

## Einmalige Einrichtung

1. Erstelle auf GitHub ein neues Repository, z. B. `investment-radar`.
2. Lade **den Inhalt dieses Ordners** hoch und committe auf `main`.
3. Gehe zu **Settings → Pages**.
4. Wähle bei **Build and deployment → Source**: **GitHub Actions**.
5. Öffne **Actions → Update Investment Radar → Run workflow** und starte den Workflow einmal manuell.
6. Danach findest du die Seite typischerweise unter:
   `https://DEIN-GITHUB-NAME.github.io/investment-radar/`

Danach ist kein täglicher manueller Import nötig.

## Datenquellen

- Kursdaten: Yahoo Finance über `yfinance`
- News: Google News RSS
- Hosting/Automatisierung: GitHub Actions + GitHub Pages

Für ernsthaftes aktives Trading sind kostenlose Datenfeeds nicht garantiert echtzeitfähig oder vollständig. Später kann ein professioneller Kurs-/News-Feed eingebaut werden.

## Risiko

Kurzfristige und Overnight-Trades sind spekulativ. Ein Setup kann trotz positivem Score sofort drehen oder mit einem Gap gegen dich eröffnen. Stop-/Target-Angaben sind Modellorientierungen, keine personalisierte Anlageberatung.


## Großes Aktienuniversum

Diese Version scannt aktuell **204 liquide Aktien/ADRs** aus mehreren Sektoren. 
Der Prozess ist dreistufig, um Laufzeit und Datenlast vernünftig zu halten:

1. Alle 204 Titel: Kursmomentum, 5-Tages-Momentum, relatives Volumen und ATR.
2. Nur die besten 24 quantitativen Setups: aktuelle News/Sentiment.
3. Nur die besten 10: Premarket-/Gap-Prüfung.
4. Im Dashboard erscheinen maximal die besten 5 Titel mit Mindestscore 65/100.

Damit werden nicht nur wenige feste Favoriten verglichen, sondern ein deutlich breiteres Universum.


## KAUF-HEUTE-Signal

Für jeden Kandidaten wird jetzt ein eindeutiger regelbasierter Status angezeigt:

- **KAUF HEUTE**: alle definierten Kriterien sind erfüllt **und in der heutigen regulären US-Session (ab 09:30 New York) live bestätigt**.
- **WARTEN**: das Grundsetup ist interessant oder im Premarket bestätigt, aber die reguläre US-Session hat den Entry noch nicht bestätigt.
- **NICHT KAUFEN**: Mindestregeln sind nicht erfüllt.

Die Kriterien sind:
- Score >= 75
- positives 1-Tages-Momentum und kein stark negatives 5-Tages-Momentum
- relatives Volumen >= 1,10x
- ATR zwischen 1 % und 6 %
- News-Sentiment nicht negativ
- Premarket-Gap zwischen -1,5 % und +6 %
- Premarket-Verlauf nicht schlechter als -0,5 %

Das Signal ist eine Heuristik und keine Garantie für Gewinne.


## Push-Benachrichtigungen aufs Handy

Diese Version enthält `monitor.py` und `.github/workflows/monitor.yml`.

### Einmalig auf dem Handy
1. Installiere die App **ntfy** (iOS oder Android).
2. Erfinde einen langen privaten Topic-Namen, z. B. `radar-4f92-mein-geheimer-code`.
3. Abonniere in der ntfy-App genau dieses Topic auf dem Standardserver `https://ntfy.sh`.

### Einmalig bei GitHub
1. Repository → **Settings → Secrets and variables → Actions**.
2. **New repository secret**.
3. Name: `NTFY_TOPIC`
4. Value: genau dein privater Topic-Name.
5. Speichern.
6. Unter **Actions → Monitor Trade Signals → Run workflow** einmal testen.

Den Topic-Namen nicht direkt in eine öffentliche Datei schreiben. Er bleibt als GitHub Secret privat.

### Was wird überwacht?
- Während der regulären US-Handelszeit prüft der Workflow ungefähr alle 15 Minuten.
- Bei einem neuen `KAUF HEUTE`-Signal wird einmalig ein Entry-Push geschickt.
- Danach wird das Setup virtuell weiterverfolgt.
- Ein Exit-Push wird gesendet, wenn:
  - Stop/Invalidation erreicht wird,
  - das erste Gewinnziel erreicht wird,
  - oder am Folgetag gegen 15:45 New-York-Zeit der Zeit-Exit ansteht.

### Stückzahl im Push
In `config.json` kannst du einmalig `portfolio_eur` setzen, z. B. `10000`.
`risk_per_trade_pct` ist standardmäßig `0.5`, also 0,5 % Depotrisiko pro Trade.
Die Stückzahl wird aus Depotrisiko und Stop-Abstand berechnet.

### Wichtige Grenzen
GitHub Actions ist kein professioneller Echtzeit-Trading-Server. Geplante Jobs können verzögert starten, Yahoo-Daten können verzögert/fehlerhaft sein, und 15-Minuten-Prüfungen können schnelle Bewegungen verpassen. Die Pushes sind Research-/Risikohinweise, keine garantierten Kauf- oder Verkaufsanweisungen.


## Echte Position aus dem Dashboard überwachen

Im Bereich **Meine echte Position** kannst du nach dem Kauf in Trade Republic eintragen:
- Ticker
- echten Kaufkurs
- Stückzahl
- Kaufzeit
- Stop in %
- Gewinnziel in %
- privaten ntfy-Topic

Der Monitor übernimmt diese Daten beim nächsten Lauf und überwacht deinen tatsächlichen Einstieg.
Exit-Pushs enthalten dann auch den ungefähren unrealisierten Gewinn/Verlust auf Basis deiner Stückzahl.

Wichtig: Die Überwachung ist nicht tickgenau. GitHub Actions läuft ungefähr alle 15 Minuten und Marktdaten können verzögert sein. Ein Exit-Push kann daher nicht garantieren, dass exakt zum angezeigten Preis verkauft werden kann.


## Automatische Kauf- und Verkaufsmenge

Im Dashboard gibt es jetzt **Positionsgröße** mit:
- Depotwert
- Risiko pro Trade in %
- maximaler Positionsgröße als % des Depots

Beim nächsten echten Entry-Push berechnet der Monitor die Stückzahl anhand des aktuellen Kurses und des Stop-Abstands.

Beispiel:
- Depot: 10.000 €
- Risiko: 0,5 % = maximal 50 € Verlust
- Stop: 2 %
- Aktie: 50 €

Rein nach Risiko wären 50 Stück möglich, aber bei einem Positionslimit von 10 % des Depots sind maximal 20 Stück erlaubt. Das System schlägt deshalb 20 Stück vor.

Wenn du anschließend im Dashboard deine echte Position mit Stückzahl einträgst, enthält ein Exit-Push konkret:
**„Aktion: X Stück verkaufen / Position vollständig schließen.“**

Das ist eine regelbasierte Risikosteuerung, keine Garantie für Gewinn oder optimalen Ein-/Ausstieg.


## ntfy-Topic im Dashboard verborgen

In dieser Version gibt es kein sichtbares ntfy-Topic-Feld mehr.
Das Dashboard verwendet den bereits im Browser gespeicherten Wert `radar_ntfy_topic`.

Solange du denselben Browser verwendest und die Website-/Browserdaten nicht löschst,
musst du den Topic nicht erneut eingeben. Dein GitHub-Secret `NTFY_TOPIC` bleibt weiterhin
separat in GitHub gespeichert.

Wenn der Browser-Speicher gelöscht wird oder du ein neues Gerät verwendest, muss die
Push-Verbindung einmalig erneut initialisiert werden.


## Backend-Version
Der ntfy-Topic liegt nur noch als Cloudflare-Worker-Secret vor. Siehe `CLOUDFLARE_SETUP.md`.


## ntfy-Kontingent sparen

Die Positionsgrößen-Einstellungen werden ab dieser Version **nicht mehr über ntfy versendet**.
Sie werden im Dashboard lokal gespeichert. Dadurch verbraucht das Ändern oder Speichern von
Depotwert, Risiko und Positionslimit keine ntfy-Nachrichten mehr.

Der GitHub-Monitor ist derzeit fest auf folgende Werte eingestellt:

- Depotwert: 2.000 €
- Risiko pro Trade: 0,5 %
- Maximale Einzelposition: 10 % des Depots

ntfy wird weiterhin verwendet für:
- tatsächlich im Dashboard eingetragene Positionen, damit der Monitor sie übernehmen kann,
- Entry-Signale,
- Exit-Signale.

Wenn das ntfy-Tageslimit bereits erreicht ist, funktionieren neue ntfy-Nachrichten erst wieder,
wenn das Kontingent zurückgesetzt wurde oder ein Tarif mit höherem Limit verwendet wird.


## Test-Benachrichtigung

Das Dashboard enthält jetzt unter **PUSH-ÜBERWACHUNG** den Button
**„Test-Benachrichtigung senden“**.

Der Button ruft den Cloudflare-Worker-Endpunkt `/test` auf und sendet genau eine
ntfy-Nachricht. Damit lässt sich die Strecke

Dashboard → Cloudflare Worker → ntfy

testen, ohne eine Testposition anzulegen.

Hinweis: Der Test verbraucht genau eine ntfy-Nachricht und funktioniert nicht,
wenn das ntfy-Tageslimit bereits erreicht ist.


## Tageszähler für Push-Nachrichten

Das Dashboard zeigt jetzt unter **PUSH-ÜBERWACHUNG**:

**Heute über das Radar gesendet: X Push-Nachrichten**

Damit der Zähler dauerhaft funktioniert, muss im Cloudflare Worker einmalig ein KV-Namespace
gebunden werden:

1. Cloudflare → Workers & Pages → dein Worker
2. Settings → Bindings
3. Add binding → KV Namespace
4. Neuen KV-Namespace anlegen, z. B. `investment-radar-counter`
5. Variable name / Binding name exakt: `PUSH_COUNTER`
6. Speichern und Worker neu deployen

Ohne diese KV-Bindung funktioniert das Dashboard weiterhin normal, aber beim Zähler steht
„Zähler noch nicht eingerichtet“.

Der Zähler zählt nur erfolgreich über den Cloudflare-Worker gesendete ntfy-Nachrichten.
Er zählt nicht andere Nachrichten, die unabhängig davon an dein ntfy-Konto/Topic gesendet werden.


## Intraday-Live-Scan

Der Monitor-Workflow wurde erweitert:

1. Alle 15 Minuten während des breiten US-Handelsfensters wird zuerst `radar.py` neu ausgeführt.
2. Danach liest `monitor.py` sofort die frisch erzeugte `data/radar.json`.
3. Ein Kandidat kann dadurch intraday von **WARTEN** auf **KAUF HEUTE** wechseln.
4. Wenn das passiert und für den Ticker an diesem Tag noch kein Entry-Push gesendet wurde,
   wird der Entry-Push automatisch verschickt.
5. Danach werden `data/radar.json` und `state/push_state.json` gespeichert und GitHub Pages neu deployed.

Nach US-Börsenöffnung verwendet der Scanner zusätzlich:
- aktuellen Live-Gap gegenüber dem Vortagesschluss,
- Kursbewegung seit regulärem US-Open,
- Gap-Recovery als mögliche Bestätigung.

Das reduziert das Problem, dass ein morgens negativer Premarket-Gap den Titel für den ganzen Tag
auf `WARTEN` festhält, obwohl er sich nach Börsenöffnung klar erholt.

Hinweis: Die Daten stammen weiterhin aus Yahoo Finance / yfinance und sind nicht tickgenau.
GitHub Actions kann außerdem einige Minuten verspätet starten.


## ntfy authentication for GitHub monitor

If the ntfy topic is protected, add GitHub repository secret `NTFY_TOKEN` with the ntfy access token.
The monitor now uses `Authorization: Bearer <token>` for both publishing alerts and reading manual-position events.


## Session-Schutz (Fix)

- Intraday-Daten werden ausschließlich dem **tatsächlichen aktuellen Datum in America/New_York** zugeordnet.
- Vor 04:00 New-York-Zeit können gestrige Bars nicht mehr als heutiger Premarket/Live-Handel erscheinen.
- Vor 09:30 New-York-Zeit ist **KAUF HEUTE gesperrt**; ein gutes Premarket-Setup bleibt **WARTEN**.
- `Gap` ist der aktuelle Premarket-Kurs relativ zum letzten abgeschlossenen offiziellen Schlusskurs.
- Sobald Yahoo während des heutigen Handels bereits einen unvollständigen Daily-Bar liefert, werden Momentum, Volumen und ATR weiterhin nur aus abgeschlossenen Sessions berechnet.
