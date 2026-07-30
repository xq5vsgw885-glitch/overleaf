"""§12.25 — die bestehenden Suiten bleiben erfolgreich.

`test_chunker.py` und `test_acceptance.py` sind eigenstaendige
Pruefskripte mit `main()` und einer eigenen Ergebnistabelle; sie
definieren keine `test_`-Funktionen und wuerden von pytest sonst
kommentarlos mit null Tests eingesammelt. Diese Wrapper fuehren sie als
Unterprozess aus und lassen den Testlauf scheitern, sobald eine ihrer
Invarianten faellt.

Unterprozess und nicht Import: Beide Skripte fuehren globale Zustaende
(`RESULTS`) und schreiben in temporaere Verzeichnisse. Ein Import in den
pytest-Prozess wuerde diese Zustaende zwischen den Suiten teilen — und
damit genau die Invarianz aufweichen, die hier bewiesen werden soll.
"""

import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, script], cwd=HERE, capture_output=True, text=True,
        timeout=600,
        env={**os.environ, "PYTHONPATH": HERE,
             "PROVENANCE_DB_PATH": os.path.join(HERE, ".pytest-provenance.db")})


@pytest.mark.parametrize("script,marker", [
    ("test_chunker.py", "Prüfungen"),
    ("test_acceptance.py", "Kriterien"),
])
def test_legacy_suite_still_passes(script, marker):
    completed = _run(script)
    report = completed.stdout + completed.stderr
    assert completed.returncode == 0, report[-4000:]
    assert "FEHLER" not in report.replace("0 Fehler", ""), report[-4000:]
    assert marker in report
