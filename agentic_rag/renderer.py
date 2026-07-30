"""Dualer Exportmodus (Spezifikation §11).

## Zwei Modi, strikt getrennt

`evaluation`  Alles bleibt sichtbar, Fehlerzustaende werden stabil
              markiert. Fuer die wissenschaftliche Auswertung: Eine
              stillschweigend entfernte Passage ist dort ein Datenverlust.

`production`  Ausschliesslich `VERIFIED`. `PARTIALLY_VERIFIED`,
              `UNVERIFIED` und `BLOCKED` werden vollstaendig und
              kommentarlos ausgeschlossen — kein Platzhalter, kein Hinweis,
              keine Fussnote.

## Maschinenlesbarkeit

Die Markierung darf nicht nur visuell sein. Jeder Renderlauf liefert daher
neben dem Markdown eine strukturierte Beilage (`sidecar`): Status,
Fehlerklasse, Evidenzlisten und Zeichenbereiche im gerenderten Text. Wer
den Export auswertet, liest die Beilage — nicht das Markdown.

## Keine Rueckwirkung

Der Export liest ausschliesslich. Er veraendert keine gespeicherten
Statuswerte und keine Audit-Daten (§11, letzter Satz).
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from policy import ExportMode, Status

#: Stabile Tags. Der Text hinter dem Callout-Marker ist Teil des Vertrags —
#: Auswertungen greifen darauf zu.
STATUS_TAGS = {
    Status.PARTIALLY_VERIFIED: "> [!WARNING] PARTIALLY_VERIFIED",
    Status.UNVERIFIED: "> [!DANGER] UNVERIFIED",
    Status.BLOCKED: "> [!ERROR] BLOCKED",
}


@dataclass
class RenderedSegment:
    claim_id: str
    status: Status
    char_start: int
    char_end: int
    error_class: Optional[str] = None
    rendered_text: bool = True
    reason: str = ""
    confirmed_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    repair_count: int = 0


@dataclass
class RenderResult:
    mode: ExportMode
    markdown: str
    segments: List[RenderedSegment]
    excluded_claim_ids: List[str]
    run_id: str = ""
    run_status: str = ""

    def sidecar(self) -> dict:
        """Strukturierte Beilage — die maschinenlesbare Wahrheit des Exports."""
        return {
            "export_mode": self.mode.value,
            "run_id": self.run_id,
            "run_status": self.run_status,
            "segments": [
                {"claim_id": s.claim_id, "status": s.status.value,
                 "char_start": s.char_start, "char_end": s.char_end,
                 "error_class": s.error_class,
                 "rendered_text": s.rendered_text, "reason": s.reason,
                 "confirmed_evidence": s.confirmed_evidence,
                 "missing_evidence": s.missing_evidence,
                 "repair_count": s.repair_count}
                for s in self.segments
            ],
            "excluded_claim_ids": list(self.excluded_claim_ids),
        }

    def sidecar_json(self) -> str:
        return json.dumps(self.sidecar(), ensure_ascii=False, sort_keys=True,
                          indent=2)


def render(verdicts: Sequence, mode=ExportMode.EVALUATION, run_id: str = "",
           run_status: str = "", texts: Dict[str, str] = None) -> RenderResult:
    """Verdicts rendern.

    `texts` erlaubt es, den fachlichen Text getrennt von der Verdict-Struktur
    zu uebergeben (z. B. den Chunk-Text statt des Claim-Satzes). Fehlt ein
    Eintrag, wird `verdict.claim_text` verwendet.
    """
    mode = ExportMode(mode)
    texts = texts or {}
    #: Ein laufweiter Hard Fail entwertet jede Aussage des Runs. Der
    #: gespeicherte Claim-Status bleibt davon unberuehrt (forensischer
    #: Wert), der Export sieht sie aber alle als BLOCKED.
    run_blocked = run_status == "blocked"

    parts: List[str] = []
    segments: List[RenderedSegment] = []
    excluded: List[str] = []
    cursor = 0

    for verdict in verdicts:
        status = Status.BLOCKED if run_blocked else verdict.status
        text = texts.get(verdict.claim_id, verdict.claim_text)

        if mode is ExportMode.PRODUCTION:
            if status is not Status.VERIFIED:
                excluded.append(verdict.claim_id)
                continue
            block = text
            rendered_text = True
        elif status is Status.VERIFIED:
            block = text
            rendered_text = True
        elif status is Status.BLOCKED:
            # §11: kein fachlicher Text. Nur Status, Fehlerklasse und
            # nicht-sensitive Referenzdaten.
            error_class = (verdict.error_class.value if verdict.error_class
                           else ("RUN_BLOCKED" if run_blocked else "UNSPECIFIED"))
            block = "\n".join([
                STATUS_TAGS[Status.BLOCKED],
                f"> claim_id: {verdict.claim_id}",
                f"> error_class: {error_class}",
                "> Fachlicher Text wird im BLOCKED-Zustand nicht ausgegeben.",
            ])
            rendered_text = False
        else:
            tag = STATUS_TAGS[status]
            error_class = (verdict.error_class.value if verdict.error_class
                           else "UNSPECIFIED")
            block = "\n".join([
                tag,
                f"> claim_id: {verdict.claim_id}",
                f"> error_class: {error_class}",
                f"> reason: {verdict.reason}",
                "",
                text,
            ])
            rendered_text = True

        start = cursor + (2 if parts else 0)
        parts.append(block)
        cursor = start + len(block)
        segments.append(RenderedSegment(
            claim_id=verdict.claim_id, status=status, char_start=start,
            char_end=cursor,
            error_class=(verdict.error_class.value
                         if verdict.error_class else
                         ("RUN_BLOCKED" if run_blocked and
                          status is Status.BLOCKED else None)),
            rendered_text=rendered_text, reason=verdict.reason,
            confirmed_evidence=list(verdict.confirmed_evidence),
            missing_evidence=list(verdict.missing_evidence),
            repair_count=verdict.repair_count))

    markdown = "\n\n".join(parts)
    return RenderResult(mode=mode, markdown=markdown, segments=segments,
                        excluded_claim_ids=excluded, run_id=run_id,
                        run_status=run_status)


def render_run(con, run_id: str, mode=ExportMode.EVALUATION,
               texts: Dict[str, str] = None) -> RenderResult:
    """Export aus den PERSISTIERTEN Statuswerten. Nur lesend."""
    import reconciler

    row = con.execute("SELECT status FROM runs WHERE run_id = ?",
                      (run_id,)).fetchone()
    run_status = row["status"] if row else "unknown"
    verdicts = reconciler.stored_verdicts(con, run_id)
    return render(verdicts, mode=mode, run_id=run_id, run_status=run_status,
                  texts=texts)
