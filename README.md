# Balkan Remote Career Meister 8.0

Lokal mit `python server.py` starten und `http://127.0.0.1:8765` öffnen. Der Server verwendet Python 3.12 und Standardbibliotheken. Der Docker-Start für Render ist im Repository enthalten.

## Treffer und Filter

Die Startliste verlangt eine passende Tätigkeit, einen Sprachhinweis und eine Ortsangabe für Nordmazedonien. Explizite Anforderungen an Deutsch, Mazedonisch, Serbisch, Kroatisch und Bosnisch sowie mazedonischsprachige lokale Anzeigen werden mit ihrem jeweiligen Nachweis ausgewiesen. Höhere Englischpflicht, weitere Pflichtsprachen, unpassende Tätigkeiten und ausgeschlossene Arbeitsorte fallen aus der Startliste.

Die Rangfolge berücksichtigt Sprachbeleg, Tätigkeit, Ortsangabe, Arbeitsmodell und Datum. Die Karte zeigt die Teilpunkte und den Standortbeleg. Weltweite, regionale und unklare Remote-Angebote sind bei ansonsten passendem Profil unter „Passend, Arbeitsort offen“ zu finden. Innerhalb einer Filtergruppe werden Auswahlen mit ODER verbunden, zwischen Gruppen mit UND.

## Quellen

Die quellenweise Statusanzeige unterscheidet erreichbare, teilweise erreichbare, ausgefallene und vorübergehend zwischengespeicherte Quellen. Neben allgemeinen Jobfeeds und Firmenboards werden Vrabotuvanje MK, KARIERA.mk, der Workable-Feed von SupportYourApp und eine Jobicy-Sprachsuche ausgewertet. Lokale Anzeigen werden anhand ihrer Detailseiten und Bewerbungsfristen geprüft. Die Quellen starten beim Serverstart und werden alle 30 Minuten aktualisiert. Bei Ausfällen kann ein zuvor erfolgreicher Abruf bis zu zwei Stunden im RAM erhalten bleiben. Abgelaufene Anzeigen werden auch zwischen Abrufen ausgefiltert.

Die Auswertung basiert auf veröffentlichten Angaben. Sie kann zusätzliche Anforderungen, Bildanzeigen oder mehrdeutige Ortsangaben übersehen. Eine weltweite Ausschreibung ersetzt keine Aussage des Arbeitgebers zum Vertrag in Nordmazedonien. Die Datenquellen und Suchseiten haben begrenzte Abdeckung. Externe Jobplattformen unter „Weitere Jobplattformen“ sind Direktlinks. Lebensläufe bleiben lokal im Browser und Bewerbungen werden als Entwurf vorbereitet.

## Tests

`python -m unittest -v`
