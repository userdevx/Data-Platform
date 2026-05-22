from engine.pipelines.definitions import (
    create_pipeline_definition,
    create_task,
)

from engine.pipelines.runner import run_pipeline


def test_pipeline_runner_success():
    def extract():
        return {"records": 1}

    def validate():
        return {"valid": True}

    def load():
        return {"stored": True}

    tasks = [
        create_task("extract", "extract"),
        create_task(
            "validate",
            "quality_check",
            depends_on=["extract"]
        ),
        create_task(
            "load",
            "load",
            depends_on=["validate"]
        ),
    ]

    pipeline = create_pipeline_definition(
        pipeline_name="test_pipeline_success",
        description="Successful pipeline test.",
        tasks=tasks,
        schedule="manual",
    )

    task_functions = {
        "extract": extract,
        "validate": validate,
        "load": load,
    }

    result = run_pipeline(pipeline, task_functions)

    assert result["status"] == "success"
    assert result["failed_tasks"] == []
    assert "extract" in result["completed_tasks"]
    assert "validate" in result["completed_tasks"]
    assert "load" in result["completed_tasks"]


def test_pipeline_runner_failure_stops_pipeline():
    def extract():
        return {"records": 1}

    def validate():
        raise RuntimeError("Validation failed")

    def load():
        return {"stored": True}

    tasks = [
        create_task("extract", "extract"),
        create_task(
            "validate",
            "quality_check",
            depends_on=["extract"]
        ),
        create_task(
            "load",
            "load",
            depends_on=["validate"]
        ),
    ]

    pipeline = create_pipeline_definition(
        pipeline_name="test_pipeline_failure",
        description="Failed pipeline test.",
        tasks=tasks,
        schedule="manual",
    )

    task_functions = {
        "extract": extract,
        "validate": validate,
        "load": load,
    }

    result = run_pipeline(pipeline, task_functions)

    assert result["status"] == "failed"
    assert "validate" in result["failed_tasks"]
    assert "load" not in result["completed_tasks"]
