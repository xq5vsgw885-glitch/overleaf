import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

from server import app

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
