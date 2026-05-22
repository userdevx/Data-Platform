from datetime import datetime, timezone

from engine.jobs import create_job_run, complete_job, fail_job


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def validate_pipeline_definition(pipeline):
    if "pipeline_name" not in pipeline:
        raise ValueError("Pipeline missing pipeline_name")

    if "tasks" not in pipeline:
        raise ValueError("Pipeline missing tasks")

    task_names = set()

    for task in pipeline["tasks"]:
        task_name = task.get("task_name")

        if not task_name:
            raise ValueError("Task missing task_name")

        if task_name in task_names:
            raise ValueError(f"Duplicate task name: {task_name}")

        task_names.add(task_name)

    for task in pipeline["tasks"]:
        for dependency in task.get("depends_on", []):
            if dependency not in task_names:
                raise ValueError(
                    f"Task '{task['task_name']}' depends on missing task '{dependency}'"
                )


def can_run_task(task, completed_tasks):
    dependencies = task.get("depends_on", [])

    for dependency in dependencies:
        if dependency not in completed_tasks:
            return False

    return True


def run_pipeline(pipeline, task_functions, ran_by="system"):
    validate_pipeline_definition(pipeline)

    pipeline_name = pipeline["pipeline_name"]
    completed_tasks = set()
    failed_tasks = []
    run_results = []

    started_at = current_timestamp()

    for task in pipeline["tasks"]:
        task_name = task["task_name"]

        if not can_run_task(task, completed_tasks):
            failed_tasks.append(task_name)

            run_results.append({
                "task_name": task_name,
                "status": "blocked",
                "reason": "dependency_not_completed",
            })

            break

        if task_name not in task_functions:
            failed_tasks.append(task_name)

            run_results.append({
                "task_name": task_name,
                "status": "failed",
                "reason": "missing_task_function",
            })

            break

        job = create_job_run(
            job_id=f"{pipeline_name}.{task_name}",
            pipeline_name=pipeline_name,
            task_name=task_name,
            ran_by=ran_by,
            max_attempts=task.get("retries", 3),
        )

        try:
            result = task_functions[task_name]()

            completed_job = complete_job(job)
            completed_tasks.add(task_name)

            run_results.append({
                "task_name": task_name,
                "status": "success",
                "job": completed_job,
                "result": result,
            })

        except Exception as error:
            failed_job = fail_job(job, error)
            failed_tasks.append(task_name)

            run_results.append({
                "task_name": task_name,
                "status": "failed",
                "job": failed_job,
                "error": str(error),
            })

            break

    finished_at = current_timestamp()

    pipeline_status = "success" if not failed_tasks else "failed"

    return {
        "pipeline_name": pipeline_name,
        "status": pipeline_status,
        "started_at": started_at,
        "finished_at": finished_at,
        "completed_tasks": list(completed_tasks),
        "failed_tasks": failed_tasks,
        "results": run_results,
    }
