"""Tests for the generation job lifecycle."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine.generation.budget import (
    HardwareSnapshot,
    InsufficientResourcesError,
    derive_budget,
)
from engine.generation.models import (
    CATEGORY_ARTIFACT,
    CATEGORY_JOB_STATE,
    FailureReason,
    GenerationProfile,
    JobState,
    artifact_record,
    build_idempotency_key,
    job_state_record,
    new_job,
)
from engine.generation.service import GenerationJobService, job_from_record
from engine.generation.store import InMemoryJobRecordStore


GIB = 1024 ** 3
TEST_CAPABILITY = "image_generation"
TEST_PROMPT = "test generation request"
TEST_MODEL_ID = "test-model"


def snapshot(
    *,
    total: int = 16 * GIB,
    available: int = 10 * GIB,
    cpus: int = 4,
    systemd: bool = True,
    cgroup: int = 2,
) -> HardwareSnapshot:
    return HardwareSnapshot(
        total_memory_bytes=total,
        available_memory_bytes=available,
        total_swap_bytes=4 * GIB,
        free_swap_bytes=3 * GIB,
        cpu_count=cpus,
        cgroup_version=cgroup,
        systemd_run_available=systemd,
    )


class BudgetTests(unittest.TestCase):
    def test_reserves_memory_for_the_session(self) -> None:
        budget = derive_budget(snapshot(), desktop_reserve_bytes=3 * GIB)
        self.assertEqual(budget.memory_max_bytes, 7 * GIB)

    def test_swap_is_always_disabled(self) -> None:
        self.assertEqual(derive_budget(snapshot()).swap_max_bytes, 0)

    def test_leaves_one_core_on_four_cpu_machine(self) -> None:
        budget = derive_budget(snapshot(cpus=4))
        self.assertEqual(budget.threads, 3)
        self.assertEqual(budget.cpu_quota_percent, 300)

    def test_reserves_fraction_on_twelve_cpu_machine(self) -> None:
        budget = derive_budget(snapshot(cpus=12))
        self.assertEqual(budget.threads, 9)
        self.assertEqual(budget.cpu_quota_percent, 900)

    def test_single_core_machine_still_gets_one_thread(self) -> None:
        self.assertEqual(derive_budget(snapshot(cpus=1)).threads, 1)

    def test_unenforceable_budget_is_labelled_as_such(self) -> None:
        budget = derive_budget(snapshot(systemd=False))
        self.assertFalse(budget.enforced)
        self.assertEqual(budget.profile, "unprotected")

    def test_cgroup_v1_cannot_be_enforced(self) -> None:
        self.assertFalse(derive_budget(snapshot(cgroup=1)).enforced)

    def test_refuses_to_run_without_headroom(self) -> None:
        with self.assertRaises(InsufficientResourcesError):
            derive_budget(
                snapshot(available=4 * GIB),
                desktop_reserve_bytes=3 * GIB,
            )


class ProfileTests(unittest.TestCase):
    def test_dimensions_must_be_multiples_of_eight(self) -> None:
        with self.assertRaises(ValueError):
            GenerationProfile(width=250)

    def test_rejects_too_few_effective_steps_for_img2img(self) -> None:
        with self.assertRaises(ValueError):
            GenerationProfile(steps=8, strength=0.2)

    def test_accepts_viable_img2img_combination(self) -> None:
        profile = GenerationProfile(steps=20, strength=0.6)
        self.assertEqual(profile.strength, 0.6)

    def test_rejects_out_of_range_guidance(self) -> None:
        with self.assertRaises(ValueError):
            GenerationProfile(guidance_scale=45.0)


class JobStateTests(unittest.TestCase):
    def build(self):
        return new_job(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            profile=GenerationProfile(),
            budget=derive_budget(snapshot()).as_dict(),
            hardware=snapshot().as_dict(),
            model_id=TEST_MODEL_ID,
        )

    def test_running_sets_started_at(self) -> None:
        job = self.build().transition(JobState.RUNNING)
        self.assertIsNotNone(job.started_at)
        self.assertIsNone(job.ended_at)

    def test_terminal_sets_ended_at(self) -> None:
        job = self.build().transition(JobState.RUNNING)
        job = job.transition(JobState.SUCCEEDED, artifact_id="artifact")
        self.assertIsNotNone(job.ended_at)
        self.assertEqual(job.artifact_id, "artifact")

    def test_terminal_state_cannot_be_left(self) -> None:
        job = self.build().transition(
            JobState.FAILED,
            reason=FailureReason.BUDGET_EXCEEDED,
        )
        with self.assertRaises(ValueError):
            job.transition(JobState.RUNNING)

    def test_failure_reason_is_stored_as_its_value(self) -> None:
        job = self.build().transition(
            JobState.FAILED,
            reason=FailureReason.HEARTBEAT_LOST,
        )
        self.assertEqual(job.reason, "heartbeat_lost")

    def test_identical_inputs_share_an_idempotency_key(self) -> None:
        first = build_idempotency_key(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            model_id=TEST_MODEL_ID,
            profile=GenerationProfile(),
        )
        second = build_idempotency_key(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            model_id=TEST_MODEL_ID,
            profile=GenerationProfile(),
        )
        self.assertEqual(first, second)

    def test_a_different_seed_is_a_different_job(self) -> None:
        first = build_idempotency_key(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            model_id=TEST_MODEL_ID,
            profile=GenerationProfile(seed=1),
        )
        second = build_idempotency_key(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            model_id=TEST_MODEL_ID,
            profile=GenerationProfile(seed=2),
        )
        self.assertNotEqual(first, second)


class RecordEnvelopeTests(unittest.TestCase):
    def build(self):
        return new_job(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            profile=GenerationProfile(),
            budget=derive_budget(snapshot()).as_dict(),
            hardware=snapshot().as_dict(),
            model_id=TEST_MODEL_ID,
        )

    def test_job_record_uses_the_canonical_envelope(self) -> None:
        record = job_state_record(self.build())

        for key in (
            "source",
            "category",
            "data_type",
            "sensor_type",
            "value",
            "unit",
        ):
            self.assertIn(key, record)

        self.assertEqual(record["category"], CATEGORY_JOB_STATE)
        self.assertEqual(record["unit"], "status")

    def test_artifact_record_carries_budget_and_resources(self) -> None:
        job = self.build()
        job.memory_peak_bytes = 4_187_593_216
        job.duration_ms = 20325

        record = artifact_record(
            job,
            artifact_id="artifact",
            relative_path="data/model_outputs/images/output.png",
            sha256="digest",
            mime_type="image/png",
            validation={"structural": True, "non_degenerate": True},
        )

        value = record["value"]
        self.assertEqual(record["category"], CATEGORY_ARTIFACT)
        self.assertEqual(value["resources"]["memory_peak_bytes"], 4_187_593_216)
        self.assertIn("budget", value)
        self.assertEqual(value["prompt_original"], TEST_PROMPT)

    def test_img2img_lineage_is_recorded_by_hash(self) -> None:
        record = artifact_record(
            self.build(),
            artifact_id="artifact",
            relative_path="output.png",
            sha256="digest",
            mime_type="image/png",
            validation={"structural": True, "non_degenerate": True},
            source_artifact_sha256="source-digest",
            source_dimensions=[4032, 3024],
            working_dimensions=[512, 384],
        )

        self.assertEqual(
            record["value"]["source_artifact_sha256"],
            "source-digest",
        )
        self.assertEqual(record["value"]["working_dimensions"], [512, 384])


class ArtifactLookupTests(unittest.TestCase):
    def test_artifact_can_be_recovered_by_identity(self) -> None:
        store = InMemoryJobRecordStore()

        job = new_job(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            profile=GenerationProfile(),
            budget=derive_budget(
                snapshot()
            ).as_dict(),
            hardware=snapshot().as_dict(),
            model_id=TEST_MODEL_ID,
        )

        record = artifact_record(
            job,
            artifact_id="artifact-lookup",
            relative_path=(
                "data/model_outputs/images/"
                "output.png"
            ),
            sha256="digest",
            mime_type="image/png",
            validation={
                "structural": True,
                "non_degenerate": True,
            },
        )

        store.append(
            record
        )

        recovered = store.artifact_record(
            "artifact-lookup"
        )

        self.assertIsNotNone(
            recovered
        )

        assert recovered is not None

        self.assertEqual(
            recovered["value"][
                "artifact_id"
            ],
            "artifact-lookup",
        )


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryJobRecordStore()
        self.service = GenerationJobService(
            store=self.store,
            project_root=Path("/tmp"),
            budget_provider=lambda: (snapshot(), derive_budget(snapshot())),
        )

    def submit(self, **overrides):
        arguments = {
            "capability": TEST_CAPABILITY,
            "prompt": TEST_PROMPT,
            "model_id": TEST_MODEL_ID,
            "detach": False,
        }
        arguments.update(overrides)
        return self.service.submit(**arguments)

    def test_submission_publishes_a_queued_record(self) -> None:
        job = self.submit()
        self.assertEqual(job.state, JobState.QUEUED)
        self.assertEqual(len(self.store.job_records(job.job_id)), 1)

    def test_resubmission_attaches_to_the_open_job(self) -> None:
        first = self.submit()
        second = self.submit()
        self.assertEqual(first.job_id, second.job_id)

    def test_a_completed_job_does_not_block_resubmission(self) -> None:
        first = self.submit()
        finished = first.transition(JobState.SUCCEEDED, artifact_id="artifact")
        self.store.append(job_state_record(finished))

        second = self.submit()
        self.assertNotEqual(first.job_id, second.job_id)

    def test_stale_running_job_is_reaped(self) -> None:
        job = self.submit()
        running = job.transition(JobState.RUNNING)
        running.heartbeat_at = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()
        self.store.append(job_state_record(running))

        reaped = self.service.reap_stale_jobs()

        self.assertEqual(len(reaped), 1)
        self.assertEqual(reaped[0].state, JobState.FAILED)
        self.assertEqual(reaped[0].reason, "heartbeat_lost")

    def test_recent_heartbeat_is_not_reaped(self) -> None:
        job = self.submit()
        running = job.transition(
            JobState.RUNNING,
            heartbeat_at=datetime.now(timezone.utc).isoformat(),
        )
        self.store.append(job_state_record(running))

        self.assertEqual(self.service.reap_stale_jobs(), [])

    def test_job_survives_a_round_trip_through_records(self) -> None:
        job = self.submit()
        rebuilt = job_from_record(self.store.job_records(job.job_id)[-1])

        self.assertEqual(rebuilt.job_id, job.job_id)
        self.assertEqual(rebuilt.profile.steps, job.profile.steps)
        self.assertEqual(rebuilt.state, JobState.QUEUED)

    def test_cancel_marks_open_job_terminal(self) -> None:
        job = self.submit()

        cancelled = self.service.cancel(
            job.job_id
        )

        self.assertIsNotNone(
            cancelled
        )

        assert cancelled is not None

        self.assertEqual(
            cancelled.state,
            JobState.CANCELLED,
        )

        self.assertEqual(
            cancelled.reason,
            FailureReason.USER.value,
        )

        recovered = self.service.get(
            job.job_id
        )

        self.assertIsNotNone(
            recovered
        )

        assert recovered is not None

        self.assertEqual(
            recovered.state,
            JobState.CANCELLED,
        )

    def test_cancel_is_idempotent_for_terminal_job(self) -> None:
        job = self.submit()

        first = self.service.cancel(
            job.job_id
        )

        second = self.service.cancel(
            job.job_id
        )

        self.assertIsNotNone(
            first
        )

        self.assertIsNotNone(
            second
        )

        assert first is not None
        assert second is not None

        self.assertEqual(
            first.state,
            JobState.CANCELLED,
        )

        self.assertEqual(
            second.state,
            JobState.CANCELLED,
        )

    def test_cancel_unknown_job_returns_none(self) -> None:
        self.assertIsNone(
            self.service.cancel(
                "missing-job"
            )
        )


class PressureTests(unittest.TestCase):
    def test_missing_psi_is_unknown_and_admits(self) -> None:
        from engine.generation.pressure import PressureSnapshot

        unknown = PressureSnapshot(None, None, None, available=False)

        self.assertFalse(unknown.available)
        self.assertFalse(unknown.exceeds(cpu=1.0, memory=1.0, io=1.0))

    def test_reading_above_threshold_is_detected(self) -> None:
        from engine.generation.pressure import PressureSnapshot

        busy = PressureSnapshot(45.0, 0.0, 0.0, available=True)

        self.assertTrue(busy.exceeds(cpu=20.0, memory=20.0, io=20.0))
        self.assertFalse(busy.exceeds(cpu=60.0, memory=60.0, io=60.0))

    def test_read_pressure_never_raises(self) -> None:
        from engine.generation.pressure import read_pressure

        pressure = read_pressure()

        self.assertIsInstance(pressure.available, bool)
        self.assertIn("cpu_some_avg10", pressure.as_dict())

    def test_admission_pressure_is_recorded_on_the_job(self) -> None:
        store = InMemoryJobRecordStore()
        service = GenerationJobService(
            store=store,
            project_root=Path("/tmp"),
            budget_provider=lambda: (snapshot(), derive_budget(snapshot())),
        )

        job = service.submit(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            model_id=TEST_MODEL_ID,
            detach=False,
        )

        self.assertIn("pressure", job.hardware)


class FailureDetailTests(unittest.TestCase):
    def test_failure_detail_round_trips_through_a_record(self) -> None:
        job = new_job(
            capability=TEST_CAPABILITY,
            prompt=TEST_PROMPT,
            profile=GenerationProfile(),
            budget=derive_budget(snapshot()).as_dict(),
            hardware=snapshot().as_dict(),
            model_id=TEST_MODEL_ID,
        )
        job = job.transition(
            JobState.FAILED,
            reason=FailureReason.BUDGET_EXCEEDED,
        )
        job.arguments["failure_detail"] = "terminated by signal"

        rebuilt = job_from_record(job_state_record(job))

        self.assertEqual(
            rebuilt.arguments["failure_detail"],
            "terminated by signal",
        )
        self.assertEqual(rebuilt.reason, "budget_exceeded")


if __name__ == "__main__":
    unittest.main()
