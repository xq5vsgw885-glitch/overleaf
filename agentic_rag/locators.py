"""Locator v2.1.

Änderungen gegenüber v2:

1. Der Fallback-Anker heisst jetzt `nb-fallback-content:<hash>` und ist
   damit als Fallback erkennbar. Vorher hiess er `nb-hash:…` und sah einer
   nativen Zell-ID zu ähnlich — eine Auswertung hätte ihn für eine stabile
   Strukturidentität halten können.

2. `header()` erzeugt einen eigenständigen Locator-Header für die
   Serialisierung an Agent oder Audit. Er gehört NICHT in den
   Embedding-Text: `document_version_id`, `structure_anchor` und
   `content_sha256` sind in jedem Chunk nahezu identische Token-Folgen und
   würden die Vektoren aneinander angleichen, statt sie zu trennen.
"""

from dataclasses import dataclass, field
from typing import Optional

from identity import make_evidence_key, make_unit_id, sha256_text

LOCATOR_SCHEMA_VERSION = "2.1"


@dataclass
class Locator:
    source_id: str
    document_version_id: str
    label: str
    structure_anchor: str
    content_sha256: str
    kind: str
    warnings: list = field(default_factory=list)

    @property
    def unit_id(self) -> str:
        return make_unit_id(self.document_version_id, self.structure_anchor,
                            self.content_sha256)

    @property
    def evidence_key(self) -> str:
        return make_evidence_key(self.source_id, self.structure_anchor,
                                 self.content_sha256)

    @property
    def anchor_is_fallback(self) -> bool:
        return "fallback" in self.structure_anchor or "-pos:" in self.structure_anchor

    def as_uri(self) -> str:
        return (f"{self.source_id}?anchor={self.structure_anchor}"
                f"#content={self.content_sha256[:12]}")

    def header(self, char_start: int = None, char_end: int = None) -> str:
        """Eigenständiger Header — jeder Chunk muss ohne Vorgänger lesbar sein."""
        lines = [
            "<!-- LOCATOR",
            f"schema={LOCATOR_SCHEMA_VERSION}",
            f"source={self.source_id}",
            f"dv={self.document_version_id}",
            f"unit={self.unit_id}",
            f"evidence={self.evidence_key}",
            f"anchor={self.structure_anchor}",
            f"content={self.content_sha256}",
            f"label={self.label}",
        ]
        if char_start is not None:
            lines.append(f"range={char_start}:{char_end}")
        if self.anchor_is_fallback:
            lines.append("anchor_stability=fallback")
        lines.append("-->")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "schema_version": LOCATOR_SCHEMA_VERSION,
            "source_id": self.source_id,
            "document_version_id": self.document_version_id,
            "unit_id": self.unit_id,
            "evidence_key": self.evidence_key,
            "label": self.label,
            "structure_anchor": self.structure_anchor,
            "content_sha256": self.content_sha256,
            "anchor_is_fallback": self.anchor_is_fallback,
            "kind": self.kind,
            "warnings": self.warnings,
        }


def notebook_locator(source_id: str, document_version_id: str, index: int,
                     cell_type: str, content_text: str,
                     nb_cell_id: Optional[str] = None,
                     paired: bool = False) -> Locator:
    """content_text ist der fachliche Inhalt der Einheit — bei Code-Zellen
    Quelltext UND gerenderte Outputs, ohne Locator-Syntax."""
    warnings = []
    if nb_cell_id:
        anchor = f"nb-cell:{nb_cell_id}"
    else:
        anchor = f"nb-fallback-content:{sha256_text(content_text)[:16]}"
        warnings.append(
            "nbformat < 4.5: keine native Zell-ID. Kriterium 4b — eine "
            "stabile strukturelle Identität ist nicht ableitbar; der Anker "
            "ändert sich bei Inhaltsänderung mit."
        )
    suffix = "code+output" if paired else cell_type
    return Locator(
        source_id=source_id,
        document_version_id=document_version_id,
        label=f"Cell [{index:02d}] ({suffix})",
        structure_anchor=anchor,
        content_sha256=sha256_text(content_text),
        kind="cell",
        warnings=warnings,
    )


def slide_locator(source_id: str, document_version_id: str, number: int,
                  slide_id: Optional[int], content_text: str) -> Locator:
    warnings = []
    if slide_id is not None:
        anchor = f"pptx-slide:{slide_id}"
    else:
        anchor = f"pptx-fallback-pos:{number:02d}"
        warnings.append("keine slide_id auslesbar — Anker ist gegen "
                        "Umsortierung nicht stabil.")
    return Locator(
        source_id=source_id,
        document_version_id=document_version_id,
        label=f"Slide [{number:02d}]",
        structure_anchor=anchor,
        content_sha256=sha256_text(content_text),
        kind="slide",
        warnings=warnings,
    )
