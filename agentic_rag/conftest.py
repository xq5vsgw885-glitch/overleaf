"""Gemeinsame Testfixtures.

Zwei Zusicherungen fuer die gesamte Suite:

1. Kein Test braucht Netz-, API- oder LLM-Zugang (§12). Provider sind
   deterministische Skript-Fixtures aus `output_adapter`.
2. Jeder Test bekommt eine eigene Datenbankdatei. Der Audit Writer haelt
   ein Lock je Datenbank; ohne Trennung wuerden parallele Tests
   aufeinander warten statt unabhaengig zu laufen.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_models import RunContext                           # noqa: E402


@pytest.fixture
def audit_db_path(tmp_path, monkeypatch):
    path = tmp_path / "audit" / "audit_trail.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(path))
    monkeypatch.setenv("PROVENANCE_DB_PATH",
                       str(tmp_path / "audit" / "provenance.db"))
    import migrations
    migrations.migrate_audit(str(path))
    return str(path)


@pytest.fixture
def context():
    return RunContext(experiment_id="exp-1", workflow_condition="A",
                      domain="physics", model_version="test-model",
                      output_enforcement="native", provider="test-provider",
                      task_id="task-1", replicate=1, seed=42,
                      batch_id="pilot")


@pytest.fixture
def env_context(monkeypatch):
    """Kontrollvariablen in der Umgebung — der Weg der Hooks."""
    values = {
        "AUDIT_EXPERIMENT_ID": "exp-1",
        "AUDIT_WORKFLOW_CONDITION": "B",
        "AUDIT_DOMAIN": "chemistry",
        "AUDIT_MODEL_VERSION": "test-model",
        "AUDIT_OUTPUT_ENFORCEMENT": "prompt",
        "AUDIT_PROVIDER": "test-provider",
        "AUDIT_TASK_ID": "task-7",
        "AUDIT_REPLICATE": "3",
        "AUDIT_SEED": "1234",
        "AUDIT_BATCH_ID": "pilot",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.fixture
def writer(audit_db_path):
    """Gestarteter Audit Writer, der am Testende geordnet endet."""
    from audit_writer import AuditWriterHandle
    handle = AuditWriterHandle(audit_db_path).start()
    try:
        yield handle
    finally:
        if handle.report is None:
            handle.shutdown(reason="fixture_teardown")


@pytest.fixture
def read_con(audit_db_path):
    import audit_db
    connections = []

    def _open():
        con = audit_db.connect_read(audit_db_path)
        connections.append(con)
        return con

    yield _open
    for con in connections:
        con.close()
