from engine.jobs import (
    create_job_run,
    complete_job,
    fail_job,
)


def test_create_job_run():
    job = create_job_run(
        job_id="job_001",
        pipeline_name="test_pipeline",
        task_name="extract"
    )

    assert job["job_id"] == "job_001"
    assert job["pipeline_name"] == "test_pipeline"
    assert job["task_name"] == "extract"
    assert job["status"] == "running"
    assert job["attempt"] == 1
    assert job["can_rerun"] is True


def test_complete_job():
    job = create_job_run(
        job_id="job_002",
        pipeline_name="test_pipeline",
        task_name="load"
    )

    completed = complete_job(job)

    assert completed["status"] == "success"
    assert completed["finished_at"] is not None
    assert completed["can_rerun"] is False


def test_fail_job_creates_failed_status():
    job = create_job_run(
        job_id="job_003",
        pipeline_name="test_pipeline",
        task_name="validate"
    )

    try:
        raise RuntimeError("Validation failed")
    except Exception as error:
        failed = fail_job(job, error)

    assert failed["status"] == "failed"
    assert failed["error_type"] == "RuntimeError"
    assert failed["error_message"] == "Validation failed"
    assert failed["can_rerun"] is True


def test_dead_job_when_max_attempts_reached():
    job = create_job_run(
        job_id="job_004",
        pipeline_name="test_pipeline",
        task_name="dead_task",
        max_attempts=1
    )

    try:
        raise RuntimeError("Final failure")
    except Exception as error:
        failed = fail_job(job, error)

    assert failed["status"] == "failed"
    assert failed["max_attempts"] == 1
