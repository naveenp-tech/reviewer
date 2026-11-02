from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EVAL_DIFF = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 import os
+result = eval(user_input)
 print(result)
"""

CLEAN_DIFF = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 import os
-print("a")
+print("b")
"""

NOT_A_DIFF = "hello, this is not a diff"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "provider": "mock"}


def test_review_flags_eval_as_critical_security():
    response = client.post("/review", json={"diff": EVAL_DIFF})
    assert response.status_code == 200

    body = response.json()
    assert body["provider"] == "mock"
    assert body["files_reviewed"] == 1
    assert any(
        f["category"] == "security" and f["severity"] == "critical"
        for f in body["findings"]
    )
    assert body["findings"][0]["line"] == 2


def test_clean_diff_has_no_findings():
    response = client.post("/review", json={"diff": CLEAN_DIFF})
    assert response.status_code == 200
    assert response.json()["findings"] == []


def test_empty_diff_is_rejected_by_validation():
    response = client.post("/review", json={"diff": ""})
    assert response.status_code == 422


def test_text_that_is_not_a_diff_returns_422():
    response = client.post("/review", json={"diff": NOT_A_DIFF})
    assert response.status_code == 422
    assert "No added lines" in response.json()["detail"]
