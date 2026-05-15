import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

from server import app
import server

client = TestClient(app)


def test_analyze_processes_all_rows_stats_and_regression():
    csv = "time,angle\n0,0\n1,2\n2,4\n3,6\n"
    r = client.post("/api/analyze", json={"csv": csv, "filename": "synthetic.csv"})
    assert r.status_code == 200
    d = r.json()
    assert d["used_all_rows"] is True
    assert d["row_count"] == 4
    assert {"tables", "figures", "results", "calculations"}.issubset(d.keys())

    stats_table = next(i for i in d["tables"] if i["id"] == "raw_statistics")
    angle_stats = next(row for row in stats_table["data"] if row["column"] == "angle")
    assert math.isclose(angle_stats["sample_std_ddof1"], 2.58198889747, rel_tol=1e-9)

    regression = next(i for i in d["calculations"] if i["id"] == "angular_regression")
    assert math.isclose(regression["data"]["slope"], 2.0, rel_tol=1e-12)

    summary = repr(d["summary_for_generation"])
    forbidden = ["SHA256", "internal provenance", "serverseitig", "Claude", "Anthropic"]
    assert not any(term in summary for term in forbidden)


def test_not_computable_latitude_has_no_correction_factor():
    csv = "time,angle\n0,0\n1,2\n2,4\n3,6\n"
    r = client.post("/api/analyze", json={
        "csv": csv,
        "metadata": {"omega_mess_rad_s": 999.0},
    })
    assert r.status_code == 200
    d = r.json()
    latitude = next(i for i in d["results"] if i["id"] == "latitude_result")
    assert latitude["data"]["not_computable"] is True
    assert latitude["data"]["correction_factor_used"] is False


def test_xy_tracking_without_angle_transformation_does_not_invent_angle():
    csv = "time,x,y\n0,1,0\n1,0,1\n2,-1,0\n"
    r = client.post("/api/analyze", json={"csv": csv, "filename": "tracking.csv"})
    assert r.status_code == 200
    d = r.json()

    calculation_ids = {item["id"] for item in d["calculations"]}
    result_ids = {item["id"] for item in d["results"]}
    warning_ids = {item["id"] for item in d["warnings"]}

    assert "angular_regression" not in calculation_ids
    assert "latitude_result" not in result_ids
    assert "xy_tracking_no_angle" in warning_ids

    warning = next(item for item in d["warnings"] if item["id"] == "xy_tracking_no_angle")
    assert warning["data"]["not_computable"] is True
    assert warning["data"]["requires_todo"] is True


def test_malformed_or_empty_csv_returns_clear_error():
    empty = client.post("/api/analyze", json={"csv": "", "filename": "empty.csv"})
    assert empty.status_code in {400, 422}

    malformed = client.post("/api/analyze", json={"csv": 'time,angle\n0,"unterminated', "filename": "bad.csv"})
    assert malformed.status_code == 400
    detail = malformed.json().get("detail", "")
    assert "konnte nicht" in detail or "CSV" in detail


def test_semicolon_delimiter_with_decimal_commas():
    """Test robust delimiter detection: semicolon-separated with decimal commas."""
    csv = "time;angle\n0;0,0\n1;2,0\n2;4,0\n"
    r = client.post("/api/analyze", json={"csv": csv, "filename": "semicolon.csv"})
    assert r.status_code == 200
    d = r.json()
    
    # Verify basic structure
    assert d["used_all_rows"] is True
    assert d["row_count"] == 3
    
    # Verify numeric columns detected
    assert "time" in d["detected_numeric_columns"]
    assert "angle" in d["detected_numeric_columns"]
    
    # Verify stats are computed correctly
    stats_table = next(i for i in d["tables"] if i["id"] == "raw_statistics")
    angle_stats = next(row for row in stats_table["data"] if row["column"] == "angle")
    assert angle_stats["n"] == 3
    assert math.isclose(angle_stats["mean"], 2.0, rel_tol=1e-9)
    
    # Verify regression is computed
    regression = next(i for i in d["calculations"] if i["id"] == "angular_regression")
    assert math.isclose(regression["data"]["slope"], 2.0, rel_tol=1e-12)


def test_generic_csv_profile():
    csv = "a,b,label\n1,2,low\n2,4,mid\n3,6,high\n"
    r = client.post("/api/analyze", json={"csv": csv, "filename": "generic.csv"})
    assert r.status_code == 200
    d = r.json()

    assert d["used_all_rows"] is True
    assert d["row_count"] == 3
    assert {"a", "b"}.issubset(set(d["detected_numeric_columns"]))

    table_ids = {item["id"] for item in d["tables"]}
    result_ids = {item["id"] for item in d["results"]}
    assert "raw_statistics" in table_ids
    assert "column_profile" in table_ids
    assert "missing_values_summary" in result_ids
    assert "dataset_overview" in result_ids
    assert "rubensrohr_sound_speed_result" not in result_ids


def test_rubensrohr_sound_speed_analysis():
    csv = """frequency_Hz,peak_spacing_m
300,0.572
350,0.490
400,0.429
450,0.381
500,0.343
550,0.312
600,0.286
"""
    r = client.post("/api/analyze", json={"csv": csv, "filename": "rubensrohr.csv"})
    assert r.status_code == 200
    d = r.json()

    assert d["used_all_rows"] is True
    assert d["row_count"] == 7
    assert {"frequency_Hz", "peak_spacing_m"}.issubset(set(d["detected_numeric_columns"]))

    table_ids = {item["id"] for item in d["tables"]}
    result_ids = {item["id"] for item in d["results"]}
    calculation_ids = {item["id"] for item in d["calculations"]}
    figure_ids = {item["id"] for item in d["figures"]}
    assert "rubensrohr_sound_speed_table" in table_ids
    assert "rubensrohr_sound_speed_result" in result_ids
    assert "rubensrohr_inverse_frequency_regression" in calculation_ids
    assert "rubensrohr_inverse_frequency_plot" in figure_ids

    result = next(item for item in d["results"] if item["id"] == "rubensrohr_sound_speed_result")
    regression = next(item for item in d["calculations"] if item["id"] == "rubensrohr_inverse_frequency_regression")
    assert math.isclose(result["data"]["mean_sound_speed_m_s"], 343.0, abs_tol=1.0)
    assert result["data"]["sem_m_s"] is not None
    assert result["data"]["sem_m_s"] > 0
    assert math.isclose(regression["data"]["c_regression_m_s"], 343.0, abs_tol=2.0)

    summary = repr(d["summary_for_generation"])
    forbidden = ["SHA256", "internal provenance", "serverseitig", "Claude", "Anthropic"]
    assert not any(term in summary for term in forbidden)


def test_unknown_csv_does_not_invent_physics():
    csv = "height,width\n1,4\n2,5\n3,6\n"
    r = client.post("/api/analyze", json={"csv": csv, "filename": "unknown.csv"})
    assert r.status_code == 200
    d = r.json()

    assert "column_profile" in {item["id"] for item in d["tables"]}
    assert "rubensrohr_sound_speed_result" not in {item["id"] for item in d["results"]}
    assert "angular_regression" not in {item["id"] for item in d["calculations"]}
    assert "ambiguous_physical_interpretation" in {item["id"] for item in d["warnings"]}


def test_analyze_returns_preview_blocks_with_required_fields():
    csv = "time,angle\n0,0\n1,2\n2,4\n3,6\n"
    r = client.post("/api/analyze", json={"csv": csv, "filename": "preview.csv"})
    assert r.status_code == 200
    d = r.json()

    assert "preview_blocks" in d
    assert isinstance(d["preview_blocks"], list)
    assert d["preview_blocks"]
    for block in d["preview_blocks"]:
        assert {"id", "type", "section", "title", "content", "source"}.issubset(block)


def test_generate_accepts_preferred_payload_without_raw_csv(monkeypatch):
    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Msg:
                content = [{"type": "text", "text": "\\documentclass{article}\\begin{document}OK\\printbibliography\\end{document}"}]

            return Msg()

    class FakeAnthropic:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(server, "Anthropic", FakeAnthropic)

    r = client.post("/api/generate", json={
        "experiment_title": "Rubensrohr",
        "experiment_type": "rubensrohr",
        "lab_notes": "Raumtemperatur notiert.",
        "summary_for_generation": {"row_count": 2},
        "selected_analysis_blocks": [{"id": "result", "type": "result", "content": {"value": 343}}],
        "generation_rules": {"missing_values": "write %TODO"},
    })

    assert r.status_code == 200
    assert r.json()["validation_warnings"] == []
    assert captured["messages"]
    prompt = captured["messages"][0]["content"][0]["text"]
    assert "Rubensrohr" in prompt
    assert "selected_analysis_blocks" in prompt
    assert "raw_csv" not in prompt


def test_generate_strips_raw_data_fields_from_llm_prompt(monkeypatch):
    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Msg:
                content = [{"type": "text", "text": "OK"}]

            return Msg()

    class FakeAnthropic:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(server, "Anthropic", FakeAnthropic)

    r = client.post("/api/generate", json={
        "experiment_title": "Test",
        "summary_for_generation": {"row_count": 2},
        "selected_analysis_blocks": [{"id": "x", "content": {"csv": "a,b\n1,2"}}],
        "generation_rules": {},
        "raw_csv": "a,b\n1,2",
        "csv": "a,b\n3,4",
        "file_content": "secret raw content",
    })

    assert r.status_code == 200
    warnings = r.json()["validation_warnings"]
    assert any("raw_csv" in warning for warning in warnings)
    assert any("csv" in warning for warning in warnings)
    assert any("file_content" in warning for warning in warnings)
    prompt = captured["messages"][0]["content"][0]["text"]
    assert "a,b" not in prompt
    assert "secret raw content" not in prompt
    assert "raw_csv" not in prompt
    assert "file_content" not in prompt
