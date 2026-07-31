# Agentic RAG — Ingestion, Provenienz und Audit

> **Audit-Architektur (Phase 1 und 2):** siehe `AUDIT_ARCHITEKTUR.md` —
> Single Audit Writer, laufzentriertes Schema v3 mit Evidenzregistry,
> Channel Reconciler, Repair Engine, Hard-Fail-Policy und dualer Export.
>
> **Retrieval-Phase:** Wer dem Agenten Chunks ausliefert, registriert sie
> mit `audit_client.record_retrieval(chunks)`. Nur registrierte Belege
> koennen `VERIFIED` werden; die Bestaetigung ueber blosse Quellenangaben
> ist ein markierter Uebergangspfad und ergibt hoechstens
> `PARTIALLY_VERIFIED`.
> Schnellstart: `python3 audit_ctl.py init`, dann
> `python3 audit_ctl.py selftest`. Tests: `python3 -m pytest`.
>
> **Wichtig:** `schema.sql` und `schema_provenance.sql` sind die BASELINE
> ihrer Version und duerfen nicht mehr direkt ausgefuehrt werden. Schema
> und Migration verantwortet ausschliesslich `migrations.py`.

## Ingestion-Parser: `.ipynb` und `.pptx`

Erzeugt locator-annotierte Ingestion-Einheiten für die RAG-Pipeline.
Das Feld `locator.anchor` ist als Wert für `assertions.locator` in
`audit_trail.db` vorgesehen.

```bash
python3 ingest.py notebook.ipynb          # Markdown nach stdout
python3 ingest.py deck.pptx --json        # Einheiten als JSON
                                          # Warnungen immer nach stderr
```

Abhängigkeiten: `python-pptx`, `lxml`. Der Notebook-Parser kommt ohne
Fremdbibliothek aus (`.ipynb` ist JSON).

---

## Drei Defekte Ihrer Spezifikation, korrigiert

### 1. `Cell [12]` ist als Zitatanker instabil

Die Notation ist mehrdeutig: `execution_count` (ändert sich bei jeder
Neuausführung, `null` bei Markdown) oder Array-Position (verschiebt sich
beim Einfügen oberhalb). Beides bricht den Audit-Trail **still** — ein
gestern protokollierter Beleg zeigt heute auf eine andere Stelle.

Korrektur: Trennung in `label` (positionsbasiert, für Menschen) und
`anchor` (stabil, für den Abgleich). Ab **nbformat 4.5** tragen Zellen
eine native `id`, die Umsortierung überlebt; sie wird bevorzugt, sonst
Rückfall auf Inhalts-Hash mit entsprechender Warnung.

### 2. „Erst Y, dann X" zerstört mehrspaltige Folien

Zwei Gründe: Exakte Y-Gleichheit gibt es nicht (Shapes derselben visuellen
Zeile unterscheiden sich um wenige EMU), und bei zwei Spalten ist
zeilenweises Lesen selbst bei perfekter Funktion falsch.

Korrektur: **rekursiver XY-Cut** (Nagy et al., Standardverfahren der
Layout-Analyse). Durchgehende Weissraum-Korridore werden gesucht; ein
vertikaler trennt Spalten, ein horizontaler Blöcke. Bei einspaltigem
Layout ist das Ergebnis mit Ihrer Vorgabe identisch — der Unterschied
zeigt sich erst ab zwei Spalten. Verifiziert an einer Testfolie mit zwei
je dreizeiligen Spalten, rechte Spalte um 0,1″ höher gesetzt:

| Naive Sortierung | XY-Cut |
|---|---|
| R1, L1, R2, L2, R3, L3 | L1, L2, L3, R1, R2, R3 |

Die linke Spalte ist eine Argumentationskette. Die naive Variante schiebt
zwischen jeden ihrer Schritte einen fremden Satz.

### 3. OCR auf Grafik-Outputs erzeugt Scheinevidenz

Ihre Vorgabe sieht „Konvertierung via OCR/ALT-Text" für Notebook-Grafiken
vor. OCR auf einem Matplotlib-Plot liefert Achsenbeschriftungsfragmente,
die im Index wie Messwerte aussehen — und stromabwärts nicht mehr von
solchen unterscheidbar sind.

Korrektur: Die Abbildung wird als **Fundstelle** protokolliert (MIME,
Grösse, `text/plain`-Alt), nicht als Inhalt, und erzeugt eine Warnung.
Eine ehrliche Lücke ist einer plausiblen Erfindung vorzuziehen. Wo Sie
Bildinhalte wirklich brauchen, gehört ein VLM in einen eigenen,
protokollierten Schritt — nicht in den Parser.

---

## Warum kein XSLT für OMML

Der kanonische Weg `OMML2MML.XSL → MathML → LaTeX` schleppt ein
proprietäres Microsoft-Stylesheet mit und verliert an jedem Übergang
Semantik. `omml.py` ist ein direkter rekursiver Parser für den in
Physik-Folien auftretenden Teilraum: Brüche, Sub-/Superskripte, Wurzeln,
n-äre Operatoren (Σ ∫ ∏ ∮), Klammern, Matrizen, Akzente, Überstriche,
Funktionen, Limites, plus eine Unicode-Symboltabelle (ℏ ∂ ∇ ψ …).

**Der wichtigere Teil ist das Fehlerverhalten:** Ein unbekanntes Element
rettet seinen Textinhalt und erzeugt eine Warnung, statt stillschweigend
zu verschwinden. Stille Auslassung ist hier der gefährlichste Fehlermodus —
die Formel sieht danach korrekt aus.

Getestet:

```
Eingabe : iℏ ∂ψ/∂t = Σ_{n=1}^{N} 1/n²,  ∛x,  Ĥ,  <m:zzUnbekannt>
Ausgabe : i\hbar \frac{\partial \psi }{\partial t}=\sum_{n=1}^{N} \frac{1}{{n}^{2}}\sqrt[3]{x}\hat{H}REST
Warnung : unbehandeltes OMML-Element <m:zzUnbekannt>
```

Ein während des Tests gefundener Defekt ist behoben: `\partial` direkt
gefolgt von `t` ergab das undefinierte Makro `\partialt`, das erst beim
Kompilieren auffällt — weit entfernt von der Ursache.

---

## Offene Punkte

- **Als Grafik gesetzte Formeln** lösen nur eine Warnung aus
  (`Bild ohne Alternativtext`). Eine automatische Erkennung „Bild *ist*
  Formel" ist ohne VLM nicht deterministisch möglich.
- **Folien-Anker** enthalten die Foliennummer. Werden Folien umsortiert,
  ändert sich der Anker. `.pptx` bietet mit `slide.slide_id` eine stabile
  Alternative — sinnvoll, sobald Ihre Decks versioniert werden.
- **Chunking** ist bewusst nicht enthalten. Eine Einheit kann grösser sein
  als das Embedding-Fenster; die Aufteilung muss die Locator-Kommentare in
  *jedem* Teilstück wiederholen, sonst geht die Fundstelle beim Splitten
  verloren. Das ist die nächste Fehlerquelle in der Kette.

## Quellen

- Nagy, Seth, Viswanathan: *A prototype document image analysis system for
  technical journals*, Computer 25(7), 1992 — Ursprung des XY-Cut.
  Bitte selbst verifizieren; ich habe keinen Literaturzugriff und kann
  Zitationen falsch wiedergeben.
- [python-pptx](https://python-pptx.readthedocs.io/) · nbformat-Zell-IDs ab
  Version 4.5
