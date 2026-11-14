# Balkan Remote Career Meister 7.0

**Online-bereitstellbare Webanwendung, noch nicht veröffentlicht.**

## Start

Lokal: `python server.py` und `http://localhost:8765` öffnen. Für iPhone und Laptop dieselbe öffentlich gehostete URL verwenden.

Online: Repository auf GitHub hochladen, bei Render ein neues Web Service aus dem Repository erstellen und die mitgelieferte `render.yaml` nutzen. Der Anbieter erstellt die Internetadresse. Kostenloses Hosting kann schlafen oder Limits haben. Keine persönlichen CVs in das Repository hochladen.

## Quellen

Fünf allgemeine Jobfeeds: Remotive, Arbeitnow, Jobicy, Remote OK, Himalayas. Sieben firmenspezifische ATS-Feeds: Greenhouse (GitLab, Automattic, Remote), Lever (Canonical, Wikimedia), Ashby (Deel, Linear). Nicht alle Firmenboards müssen noch existieren oder Stellen liefern. Bei jedem Suchlauf werden Erfolg, Fehler und Anzahl pro Quelle angezeigt. Zusätzlich 31 externe Jobplattform-Links. Die Links werden **nicht** automatisch durchsucht.

## Grenzen und Sicherheit

Kein Zugang zu sämtlichen LinkedIn-, Indeed- oder StepStone-Stellen. Kein garantierter Live-Treffer. Firmenidentität und rechtliche Arbeit aus Ohrid bleiben ungeprüft. Lebenslauf wird nur im Browser ausgewählt und **nicht** hochgeladen. Bewerbung wird nur vorbereitet, nie automatisch versandt. Die Suchdaten werden im Server-RAM zwischengespeichert (15 Minuten); Neustart leert den Cache. Es gibt kein Nutzerkonto und keine geräteübergreifende CV-Synchronisierung. Kein persönliches Dokument in ein öffentliches GitHub-Repository hochladen. Für echte Accounts, CV-Cloudspeicherung und automatische Bewerbungen wären zusätzliche Sicherheitsmaßnahmen erforderlich.

## Tests

`python -m unittest -v test_server.py test_extra.py`
