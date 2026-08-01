"""Gemeinsame DB-Hilfsfunktionen für die Audit-Hooks. Nur Standardbibliothek.

Erweiterung fuer das Single-Writer-Modell (Spezifikation §2, §7, §10):

* `connect_write()` ist nur im Audit-Writer-Prozess erlaubt und wirft
  sonst. Damit ist die Invariante 'genau ein schreibender Prozess' nicht
  nur eine Absprache, sondern eine Zusicherung im Code (§12.5).
* `connect_read()` oeffnet eine echte SQLite-Read-only-Verbindung
  (`mode=ro`). Ein Schreibversuch scheitert an der Engine, nicht an einem
  Codepfad, den man vergessen kann.
* `source_key()` ersetzt `normalize_source()` als Vergleichsschluessel von
  Kanal A und Kanal B. `normalize_source()` bleibt erhalten (Altdaten in
  `assertions.source_id` sind damit gebildet), ist aber nicht mehr die
  Abgleichsgrundlage.
"""

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

import migrations

#: Beibehalten aus v1.0: Modulkonstante fuer Abwaertskompatibilitaet.
#: Neuer Code ruft `db_path()`, damit Tests die Umgebung nachtraeglich
#: setzen koennen, ohne das Modul neu importieren zu muessen.
DB_PATH = os.environ.get(
    "AUDIT_DB_PATH",
    os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", "."), ".audit", "audit_trail.db"),
)

#: v1.0 zeigte auf `../schema.sql` — das setzte voraus, dass dieses Modul
#: unter `.claude/hooks/` liegt. Im ausgelieferten flachen Projektstand
#: zeigte der Pfad aus dem Projekt heraus und eine frische Datenbank
#: scheiterte mit FileNotFoundError. Jetzt wird beides akzeptiert.
_HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = next(
    (p for p in (os.path.join(_HERE, "schema.sql"),
                 os.path.join(_HERE, "..", "schema.sql"))
     if os.path.exists(p)),
    os.path.join(_HERE, "schema.sql"),
)

#: Wird ausschliesslich im Writer-Kindprozess gesetzt (siehe audit_writer).
_WRITER_PROCESS = False


def db_path() -> str:
    return os.environ.get(
        "AUDIT_DB_PATH",
        os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", "."), ".audit",
                     "audit_trail.db"),
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Verbindungen
# ---------------------------------------------------------------------------

class WriteAccessDenied(RuntimeError):
    """Schreibversuch ausserhalb des Audit-Writer-Prozesses (§2)."""


def mark_writer_process() -> None:
    global _WRITER_PROCESS
    _WRITER_PROCESS = True


def is_writer_process() -> bool:
    return _WRITER_PROCESS


def initialize(path: str = None) -> dict:
    """Schema anlegen bzw. migrieren. Idempotent."""
    return migrations.migrate_audit(path or db_path())


#: Logisch append-only (§10). Der Schutz liegt doppelt: hier im
#: Anwendungscode ueber den SQLite-Authorizer und zusaetzlich in den
#: BEFORE-UPDATE/DELETE-Triggern des Schemas. Eine Schicht allein genuegt
#: nicht — der Authorizer schuetzt nur diese Verbindung, die Trigger
#: schuetzen die Datei auch gegen ein fremdes `sqlite3`-CLI.
APPEND_ONLY_TABLES = frozenset({
    "actions", "assertions", "audit_events", "hard_fails", "repairs",
    "phase_metrics",
})


class AppendOnlyViolation(RuntimeError):
    """Versuch, historische Audit-Daten zu aendern oder zu loeschen."""


def _append_only_authorizer(action, arg1, arg2, db_name, trigger):
    """SQLite-Authorizer: UPDATE/DELETE/DROP auf Audit-Historie verweigern.

    Greift auch dann, wenn der Writer selbst einen Fehler haette — er ist
    der einzige Prozess mit Schreibrecht, also muss die Sperre gegen ihn
    wirken, nicht nur gegen andere.
    """
    table = arg1 or ""
    if action == sqlite3.SQLITE_UPDATE and table in APPEND_ONLY_TABLES:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_DELETE and table in APPEND_ONLY_TABLES:
        # DELETE-Autorisierung erscheint auch beim Leeren temporaerer
        # Strukturen; die Tabellennamen sind hier eindeutig.
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_DROP_TABLE and table in APPEND_ONLY_TABLES:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def connect_write(path: str = None, append_only_guard: bool = True
                  ) -> sqlite3.Connection:
    """Die EINZIGE schreibende Verbindung. Nur im Writer-Prozess."""
    if not _WRITER_PROCESS:
        raise WriteAccessDenied(
            "Schreibende Verbindung zu audit_trail.db ist ausschliesslich dem "
            "Audit-Writer-Prozess erlaubt (Spezifikation §2). Producer senden "
            "Events ueber audit_client / AuditWriterHandle.send()."
        )
    target = path or db_path()
    parent = os.path.dirname(os.path.abspath(target))
    if parent:
        os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(target, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA synchronous = FULL")
    if append_only_guard:
        con.set_authorizer(_append_only_authorizer)
    return con


def connect_read(path: str = None) -> sqlite3.Connection:
    """Lesende Verbindung. `mode=ro` — von der Engine erzwungen."""
    target = path or db_path()
    if not os.path.exists(target):
        raise FileNotFoundError(
            f"{target} existiert nicht. Zuerst 'python3 audit_ctl.py init'.")
    uri = "file:" + target.replace("?", "%3f").replace("#", "%23") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def connect() -> sqlite3.Connection:
    """Kompatibilitaetspfad aus v1.0.

    In v1.0 gab dieselbe Funktion jedem Aufrufer eine Schreibverbindung.
    Genau daraus entstanden die konkurrierenden Schreibzugriffe. Der Name
    bleibt, damit vorhandene Skripte nicht brechen — die Semantik ist jetzt
    'schreibend nur im Writer, sonst lesend'.
    """
    if _WRITER_PROCESS:
        return connect_write()
    initialize()
    return connect_read()


# ---------------------------------------------------------------------------
# Hash-Kette
# ---------------------------------------------------------------------------

def head(con: sqlite3.Connection) -> str:
    row = con.execute("SELECT last_hash FROM chain_head WHERE id = 1").fetchone()
    return row["last_hash"] if row else "GENESIS"


def chain_link(prev: str, payload: dict) -> str:
    """Kettenglied bilden: sha256(prev_hash || kanonisches JSON).

    Reine Funktion — dadurch ist die Kette ohne Datenbank nachrechenbar
    und der Wiederanlauf pruefbar (§10).
    """
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"))
    return hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()


def advance(con: sqlite3.Connection, prev: str, payload: dict) -> str:
    """Kettenglied bilden und `chain_head` fortschreiben.

    RACE-BEFUND zu v1.0: `chain_head` ist eine globale Einzelzeile. Mit
    mehreren schreibenden Prozessen konnten zwei Kettenglieder denselben
    Vorgaengerhash lesen und sich gegenseitig ueberschreiben — die Kette
    blieb formal gueltig, verlor aber Glieder. Behoben durch das
    Single-Writer-Modell: `chain_head` wird nur noch von einem Prozess und
    innerhalb derselben Transaktion wie die Ereigniszeile fortgeschrieben.
    Zusaetzlich traegt jede Ereigniszeile ihren `prev_hash`, sodass die
    Kette auch nach einem Wiederanlauf lokal rekonstruierbar ist.
    """
    digest = chain_link(prev, payload)
    con.execute(
        "INSERT INTO chain_head (id, last_hash, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_hash = excluded.last_hash, "
        "updated_at = excluded.updated_at",
        (digest, now()),
    )
    return digest


def verify_chain(con: sqlite3.Connection) -> dict:
    """Kette aus `audit_events` nachrechnen (§10, forensische Pruefung)."""
    prev = "GENESIS"
    broken = []
    rows = con.execute(
        "SELECT seq, event_id, payload_json, prev_hash, row_hash "
        "FROM audit_events ORDER BY seq").fetchall()
    for row in rows:
        if row["prev_hash"] != prev:
            broken.append({"seq": row["seq"], "event_id": row["event_id"],
                           "problem": "prev_hash weicht ab",
                           "expected": prev, "found": row["prev_hash"]})
        expected = chain_link(row["prev_hash"], json.loads(row["payload_json"]))
        if expected != row["row_hash"]:
            broken.append({"seq": row["seq"], "event_id": row["event_id"],
                           "problem": "row_hash weicht ab",
                           "expected": expected, "found": row["row_hash"]})
        prev = row["row_hash"]
    stored = head(con)
    if rows and stored != prev:
        broken.append({"seq": None, "event_id": None,
                       "problem": "chain_head weicht vom letzten Glied ab",
                       "expected": prev, "found": stored})
    return {"events": len(rows), "head": stored, "ok": not broken,
            "violations": broken}


# ---------------------------------------------------------------------------
# Quellenidentitaet
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_SCHEME_RE = re.compile(r"^(local|zotero|doi|url):", re.IGNORECASE)


def normalize_source(ref: str) -> str:
    """LEGACY (Audit-Schema v1.0) — nicht mehr die Abgleichsgrundlage.

    BEFUND (§7): Diese Normalisierung ist kollisionsfaehig. Sie entfernt
    das Verzeichnis und die Dateiendung. Damit werden

        physik/messung.pdf   und   biologie/messung.pdf
        messung.pdf          und   messung.md

    auf denselben Schluessel abgebildet. An der einzigen Stelle, an der
    Kanal A und Kanal B verglichen werden, bedeutet das: ein Zitat auf
    Datei X gilt als belegt, weil irgendwo eine gleichnamige Datei Y
    geoeffnet wurde. Genau die Fabrikation, die das Verfahren ausschliessen
    soll.

    Die Funktion bleibt, weil `assertions.source_id` und `actions.source_id`
    aus Schema v1.0 mit ihr gebildet wurden; ein nachtraegliches
    Umschreiben dieser Werte waere eine Umdeutung historischer Daten (§10).
    Fuer jeden NEUEN Abgleich ist `source_key()` zu verwenden.
    """
    ref = ref.strip().lower()
    if ref.startswith("10.") and "/" in ref:
        return ref  # DOI: Slash ist Bestandteil des Bezeichners, nicht Pfadtrenner
    if "/" in ref or "\\" in ref:
        ref = os.path.basename(ref.replace("\\", "/"))
    for suffix in (".pdf", ".epub", ".docx", ".pptx", ".ipynb", ".md", ".txt"):
        if ref.endswith(suffix):
            ref = ref[: -len(suffix)]
            break
    return ref


def source_key(ref: str) -> str:
    """Kollisionsfreier Vergleichsschluessel fuer Kanal A gegen Kanal B.

    Regeln, bewusst konservativ — im Zweifel bleiben zwei Angaben
    verschieden, statt zusammenzufallen:

    1. DOIs werden als DOI erkannt und klein geschrieben; der Slash bleibt.
    2. Explizite Schemata (`local:`, `zotero:`, `doi:`, `url:`) aus
       `identity.make_source_id` bleiben erhalten.
    3. Dateipfade behalten Verzeichnis UND Endung. Normalisiert werden nur
       Backslashes, `./`-Praefixe, Mehrfach-Slashes und die Gross-/
       Kleinschreibung.
    4. Nichts wird abgeschnitten.

    Der Preis ist die Gegenrichtung: `./doc/x.pdf` und `/abs/doc/x.pdf`
    gelten als verschieden. Das ist der sichere Fehler — er meldet einen
    unbelegten Claim, wo Evidenz vorlaege, statt einen belegten, wo keine
    ist.
    """
    ref = (ref or "").strip()
    if not ref:
        return ""
    if _SCHEME_RE.match(ref):
        scheme, rest = ref.split(":", 1)
        return f"{scheme.lower()}:{rest.strip().lower()}"
    if _DOI_RE.match(ref):
        return "doi:" + ref.lower()
    if ref.lower().startswith(("http://", "https://")):
        return "url:" + ref.rstrip("/").lower()
    path = ref.replace("\\", "/")
    while "//" in path:
        path = path.replace("//", "/")
    while path.startswith("./"):
        path = path[2:]
    return "path:" + path.lower()
