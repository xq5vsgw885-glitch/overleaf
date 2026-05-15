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
