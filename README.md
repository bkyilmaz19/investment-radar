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
