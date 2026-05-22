from engine.recovery import run_recovery_check


def test_recovery_check_completes():
    report = run_recovery_check()

    assert report["status"] == "recovery_check_complete"
    assert report["data"]["file"] == "data/records.json"
    assert "jobs" in report
    assert "logs" in report
