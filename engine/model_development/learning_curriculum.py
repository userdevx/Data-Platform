from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class LearningAreaId(
    str,
    Enum,
):
    SYSTEM_UNDERSTANDING = (
        "system_understanding"
    )

    INSPECT_BEFORE_CHANGE = (
        "inspect_before_change"
    )

    REQUEST_TO_REQUIREMENT = (
        "request_to_requirement"
    )

    ENGINEERING_PLAN = (
        "engineering_plan"
    )

    SAFE_CHANGE_LIFECYCLE = (
        "safe_change_lifecycle"
    )

    CODE_GENERATION = (
        "code_generation"
    )

    DATA_ENGINE_USAGE = (
        "data_engine_usage"
    )

    END_TO_END_FEATURES = (
        "end_to_end_features"
    )

    DEBUGGING = (
        "debugging"
    )

    TESTING_VERIFICATION = (
        "testing_verification"
    )

    APPLICATION_GENERATION = (
        "application_generation"
    )

    APPLICATION_MAINTENANCE = (
        "application_maintenance"
    )

    INTELLIGENCE_INTEGRATION = (
        "intelligence_integration"
    )

    UI_UX_GENERATION = (
        "ui_ux_generation"
    )

    SECURITY_PERMISSIONS = (
        "security_permissions"
    )

    LEARN_FROM_OUTCOMES = (
        "learn_from_outcomes"
    )


@dataclass(
    frozen=True,
    kw_only=True,
)
class LearningArea:
    id: LearningAreaId

    title: str

    purpose: str

    behaviors: tuple[
        str,
        ...
    ]

    required_inputs: tuple[
        str,
        ...
    ]

    expected_outputs: tuple[
        str,
        ...
    ]

    evaluation_requirements: tuple[
        str,
        ...
    ]

    requires_repository_context: bool = False

    requires_data_engine_context: bool = False

    requires_execution_feedback: bool = False


LEARNING_CURRICULUM: Final[
    tuple[
        LearningArea,
        ...
    ]
] = (
    LearningArea(
        id=(
            LearningAreaId
            .SYSTEM_UNDERSTANDING
        ),
        title=(
            "Understand the Data Platform"
        ),
        purpose=(
            "Understand the responsibilities "
            "and boundaries of the major "
            "Data Platform systems."
        ),
        behaviors=(
            (
                "Distinguish the Data Engine, "
                "Intelligence Runtime, "
                "Application Engineering, "
                "Model Development, and "
                "application interface."
            ),
            (
                "Keep models separate from "
                "storage, validation, routing, "
                "permissions, and application "
                "state ownership."
            ),
            (
                "Identify which subsystem "
                "owns a requested operation."
            ),
        ),
        required_inputs=(
            "system architecture",
            "component definitions",
        ),
        expected_outputs=(
            "correct component ownership",
            "architecture explanation",
        ),
        evaluation_requirements=(
            (
                "No ownership responsibility "
                "is assigned to the wrong "
                "subsystem."
            ),
        ),
    ),

    LearningArea(
        id=(
            LearningAreaId
            .INSPECT_BEFORE_CHANGE
        ),
        title=(
            "Inspect Before Changing"
        ),
        purpose=(
            "Require repository inspection "
            "before proposing or generating "
            "software changes."
        ),
        behaviors=(
            "Inspect the actual repository.",
            "Locate relevant files.",
            "Read existing implementations.",
            "Identify dependencies.",
            (
                "Determine whether the "
                "requested capability already "
                "exists."
            ),
            "Avoid duplicate components.",
        ),
        required_inputs=(
            "user request",
            "repository context",
        ),
        expected_outputs=(
            "inspection findings",
            "affected files",
            "existing implementation summary",
        ),
        evaluation_requirements=(
            (
                "No software change is "
                "proposed before inspection."
            ),
            (
                "Referenced files must exist "
                "in retrieved repository "
                "context."
            ),
        ),
        requires_repository_context=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .REQUEST_TO_REQUIREMENT
        ),
        title=(
            "Convert Requests to Requirements"
        ),
        purpose=(
            "Translate user intent into "
            "clear engineering requirements."
        ),
        behaviors=(
            "Identify the requested outcome.",
            "Identify constraints.",
            "Identify affected systems.",
            "Define acceptance criteria.",
            (
                "Separate requested behavior "
                "from implementation guesses."
            ),
        ),
        required_inputs=(
            "user request",
            "repository findings",
        ),
        expected_outputs=(
            "requirement",
            "constraints",
            "acceptance criteria",
        ),
        evaluation_requirements=(
            (
                "Requirement preserves the "
                "user's requested outcome."
            ),
            (
                "Acceptance criteria are "
                "testable."
            ),
        ),
        requires_repository_context=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .ENGINEERING_PLAN
        ),
        title=(
            "Create Engineering Plans"
        ),
        purpose=(
            "Create a validated implementation "
            "plan before modification."
        ),
        behaviors=(
            "Identify files to change.",
            "Explain why each change is needed.",
            "Describe implementation steps.",
            "Identify risks.",
            "Define tests.",
            "Define completion evidence.",
        ),
        required_inputs=(
            "validated requirement",
            "repository inspection",
        ),
        expected_outputs=(
            "Engineering Plan",
        ),
        evaluation_requirements=(
            "Plan references real files.",
            "Plan contains verification steps.",
            (
                "Plan does not authorize "
                "changes by itself."
            ),
        ),
        requires_repository_context=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .SAFE_CHANGE_LIFECYCLE
        ),
        title=(
            "Follow the Safe Change Lifecycle"
        ),
        purpose=(
            "Require controlled engineering "
            "steps before release."
        ),
        behaviors=(
            "Inspect.",
            "Create requirement.",
            "Create Engineering Plan.",
            "Validate the plan.",
            "Create recoverable Git checkpoint.",
            "Use a candidate workspace.",
            "Modify candidate files.",
            "Compile.",
            "Test.",
            "Verify.",
            "Release only after success.",
        ),
        required_inputs=(
            "Engineering Plan",
            "repository state",
        ),
        expected_outputs=(
            "controlled engineering sequence",
            "verification evidence",
        ),
        evaluation_requirements=(
            (
                "No file modification occurs "
                "before a validated plan and "
                "checkpoint."
            ),
            (
                "Failed validation prevents "
                "release."
            ),
        ),
        requires_repository_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .CODE_GENERATION
        ),
        title=(
            "Generate Code Within the Existing System"
        ),
        purpose=(
            "Generate implementation candidates "
            "that extend the existing "
            "architecture."
        ),
        behaviors=(
            "Reuse existing interfaces.",
            "Reuse existing modules.",
            "Follow existing schemas.",
            "Follow existing naming conventions.",
            "Avoid unnecessary dependencies.",
            "Avoid duplicate implementations.",
            "Generate complete code.",
            "Generate executable query candidates.",
            (
                "Use execution results to "
                "correct code or query "
                "candidates."
            ),
        ),
        required_inputs=(
            "Engineering Plan",
            "relevant repository files",
            "available interfaces",
        ),
        expected_outputs=(
            "code candidate",
            "query candidate when required",
        ),
        evaluation_requirements=(
            "Generated code compiles.",
            "Relevant tests pass.",
            (
                "Query candidates pass "
                "Data Platform validation "
                "before execution."
            ),
            (
                "Generated implementation "
                "does not duplicate existing "
                "functionality."
            ),
        ),
        requires_repository_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .DATA_ENGINE_USAGE
        ),
        title=(
            "Use the Data Engine Correctly"
        ),
        purpose=(
            "Use the Data Engine as the "
            "authoritative information system."
        ),
        behaviors=(
            "Read existing records.",
            "Use QueryService.",
            "Use controlled record writers.",
            "Preserve provenance.",
            "Preserve Evidence lineage.",
            "Validate before persistence.",
            "Avoid replacing data with model memory.",
        ),
        required_inputs=(
            "Data Engine schema",
            "retrieved records",
            "query requirements",
        ),
        expected_outputs=(
            "validated query operation",
            "validated record operation",
        ),
        evaluation_requirements=(
            (
                "No fabricated Data Engine "
                "information."
            ),
            (
                "Storage operations use "
                "approved Data Engine "
                "interfaces."
            ),
        ),
        requires_data_engine_context=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .END_TO_END_FEATURES
        ),
        title=(
            "Build Features End to End"
        ),
        purpose=(
            "Implement application features "
            "across all required layers."
        ),
        behaviors=(
            (
                "Determine which application "
                "layers are affected."
            ),
            (
                "Connect Python application "
                "logic when required."
            ),
            "Connect Rust/Tauri when required.",
            (
                "Connect TypeScript bridges "
                "when required."
            ),
            "Connect React UI when required.",
            "Validate the complete path.",
        ),
        required_inputs=(
            "feature requirement",
            "repository architecture",
        ),
        expected_outputs=(
            "complete feature implementation",
        ),
        evaluation_requirements=(
            (
                "Feature works through the "
                "actual application path."
            ),
            (
                "No required integration "
                "layer is omitted."
            ),
        ),
        requires_repository_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .DEBUGGING
        ),
        title=(
            "Debug and Repair Problems"
        ),
        purpose=(
            "Diagnose failures from evidence "
            "instead of guessing."
        ),
        behaviors=(
            "Reproduce the failure.",
            "Inspect affected components.",
            "Inspect logs and outputs.",
            "Identify likely root cause.",
            "Create a repair candidate.",
            "Rerun the failing operation.",
            "Run regression tests.",
        ),
        required_inputs=(
            "problem report",
            "failure output",
            "repository context",
        ),
        expected_outputs=(
            "root cause",
            "repair candidate",
            "verification result",
        ),
        evaluation_requirements=(
            (
                "Reported failure is reproduced "
                "or clearly explained."
            ),
            (
                "Repair is verified against "
                "the original failure."
            ),
        ),
        requires_repository_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .TESTING_VERIFICATION
        ),
        title=(
            "Test and Verify"
        ),
        purpose=(
            "Require observable evidence before "
            "claiming completion."
        ),
        behaviors=(
            "Run compile checks.",
            "Run unit tests.",
            "Run integration tests.",
            "Run regression tests.",
            "Run builds when required.",
            "Inspect failures.",
            "Confirm expected behavior.",
        ),
        required_inputs=(
            "candidate implementation",
            "acceptance criteria",
        ),
        expected_outputs=(
            "test results",
            "verification evidence",
        ),
        evaluation_requirements=(
            (
                "Command completion alone "
                "does not count as proof."
            ),
            (
                "Completion requires evidence "
                "matching acceptance criteria."
            ),
        ),
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .APPLICATION_GENERATION
        ),
        title=(
            "Generate Applications"
        ),
        purpose=(
            "Turn application requests into "
            "verified application releases."
        ),
        behaviors=(
            "Interpret application request.",
            "Create requirements.",
            "Determine architecture.",
            "Create Engineering Plan.",
            "Create project structure.",
            "Generate implementation.",
            "Compile.",
            "Test.",
            "Build.",
            "Verify.",
            "Release.",
        ),
        required_inputs=(
            "application request",
            "platform capabilities",
            "engineering constraints",
        ),
        expected_outputs=(
            "application candidate",
            "build",
            "verified release",
        ),
        evaluation_requirements=(
            "Generated application builds.",
            "Acceptance tests pass.",
            "Release follows controlled process.",
        ),
        requires_repository_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .APPLICATION_MAINTENANCE
        ),
        title=(
            "Maintain Applications"
        ),
        purpose=(
            "Use runtime evidence to safely "
            "repair and evolve applications."
        ),
        behaviors=(
            "Read runtime evidence.",
            "Identify maintenance requirement.",
            "Create Engineering Plan.",
            "Create repair candidate.",
            "Test the repair.",
            "Verify regression safety.",
            "Create a new release.",
        ),
        required_inputs=(
            "runtime evidence",
            "application repository",
        ),
        expected_outputs=(
            "maintenance requirement",
            "repair candidate",
            "verified release",
        ),
        evaluation_requirements=(
            (
                "Runtime evidence does not "
                "directly modify application "
                "code."
            ),
            (
                "Maintenance changes follow "
                "the normal engineering "
                "lifecycle."
            ),
        ),
        requires_repository_context=True,
        requires_data_engine_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .INTELLIGENCE_INTEGRATION
        ),
        title=(
            "Use Intelligence Capabilities Correctly"
        ),
        purpose=(
            "Choose retrieval, deterministic "
            "tools, or model reasoning "
            "appropriately."
        ),
        behaviors=(
            "Retrieve grounded information first.",
            "Prefer deterministic capabilities.",
            (
                "Use model reasoning only "
                "when required."
            ),
            (
                "Do not invent unavailable "
                "information."
            ),
            (
                "Do not bypass runtime "
                "permissions."
            ),
        ),
        required_inputs=(
            "request",
            "capability registry",
            "retrieval context",
        ),
        expected_outputs=(
            "appropriate capability use",
            "grounded response",
        ),
        evaluation_requirements=(
            (
                "Grounded reasoning cannot "
                "occur without retrieval."
            ),
            (
                "Model proposals do not "
                "become authorization."
            ),
        ),
        requires_data_engine_context=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .UI_UX_GENERATION
        ),
        title=(
            "Generate High-Quality Application Interfaces"
        ),
        purpose=(
            "Generate usable interfaces rather "
            "than only compiling interfaces."
        ),
        behaviors=(
            "Create clear hierarchy.",
            "Use consistent components.",
            "Support responsive layouts.",
            "Provide loading states.",
            "Provide error states.",
            "Provide success states.",
            "Provide disabled states.",
            "Use accessible controls.",
            "Create coherent navigation.",
        ),
        required_inputs=(
            "application requirement",
            "existing design system",
        ),
        expected_outputs=(
            "usable interface candidate",
        ),
        evaluation_requirements=(
            "Interface builds.",
            "Required states exist.",
            "Application flow is usable.",
        ),
        requires_repository_context=True,
        requires_execution_feedback=True,
    ),

    LearningArea(
        id=(
            LearningAreaId
            .SECURITY_PERMISSIONS
        ),
        title=(
            "Respect Security and Permissions"
        ),
        purpose=(
            "Keep models inside controlled "
            "execution boundaries."
        ),
        behaviors=(
            "Propose actions.",
            "Wait for validation.",
            "Respect authorization.",
            "Use approved tools.",
            (
                "Never treat generated text "
                "as execution permission."
            ),
            (
                "Never directly release "
                "unverified artifacts."
            ),
        ),
        required_inputs=(
            "requested action",
            "permission context",
        ),
        expected_outputs=(
            "authorized action proposal",
            "structured rejection when denied",
        ),
        evaluation_requirements=(
            (
                "Unauthorized operations "
                "cannot execute."
            ),
            (
                "Failed validation stops "
                "the operation."
            ),
        ),
    ),

    LearningArea(
        id=(
            LearningAreaId
            .LEARN_FROM_OUTCOMES
        ),
        title=(
            "Learn From Verified Engineering Outcomes"
        ),
        purpose=(
            "Convert real successful and failed "
            "engineering work into future "
            "training evidence."
        ),
        behaviors=(
            "Capture request.",
            "Capture repository context.",
            "Capture Engineering Plan.",
            "Capture generated candidate.",
            "Capture test results.",
            "Capture corrections.",
            "Capture final verified outcome.",
            (
                "Separate successful outcomes "
                "from failed outcomes."
            ),
        ),
        required_inputs=(
            "engineering execution history",
            "verification evidence",
        ),
        expected_outputs=(
            "training candidate evidence",
        ),
        evaluation_requirements=(
            (
                "Only verified outcomes may "
                "be promoted into approved "
                "training datasets."
            ),
            (
                "Training lineage remains "
                "traceable to source evidence."
            ),
        ),
        requires_repository_context=True,
        requires_data_engine_context=True,
        requires_execution_feedback=True,
    ),
)


def get_learning_curriculum(
) -> tuple[
    LearningArea,
    ...
]:
    return LEARNING_CURRICULUM


def get_learning_area(
    area_id: LearningAreaId | str,
) -> LearningArea:
    normalized_id = (
        area_id
        if isinstance(
            area_id,
            LearningAreaId,
        )
        else LearningAreaId(
            area_id
        )
    )

    for area in (
        LEARNING_CURRICULUM
    ):
        if area.id == normalized_id:
            return area

    raise KeyError(
        normalized_id
    )


def validate_learning_curriculum(
) -> None:
    expected_count = 16

    if (
        len(
            LEARNING_CURRICULUM
        )
        != expected_count
    ):
        raise RuntimeError(
            "Model Development curriculum "
            "must contain exactly "
            f"{expected_count} learning areas."
        )

    ids = [
        area.id
        for area
        in LEARNING_CURRICULUM
    ]

    if (
        len(
            set(
                ids
            )
        )
        != len(
            ids
        )
    ):
        raise RuntimeError(
            "Learning-area IDs must be unique."
        )

    for area in (
        LEARNING_CURRICULUM
    ):
        if not area.title.strip():
            raise RuntimeError(
                f"{area.id.value}: "
                "title is empty."
            )

        if not area.purpose.strip():
            raise RuntimeError(
                f"{area.id.value}: "
                "purpose is empty."
            )

        if not area.behaviors:
            raise RuntimeError(
                f"{area.id.value}: "
                "behaviors are empty."
            )

        if not area.required_inputs:
            raise RuntimeError(
                f"{area.id.value}: "
                "required inputs are empty."
            )

        if not area.expected_outputs:
            raise RuntimeError(
                f"{area.id.value}: "
                "expected outputs are empty."
            )

        if not area.evaluation_requirements:
            raise RuntimeError(
                f"{area.id.value}: "
                "evaluation requirements "
                "are empty."
            )


validate_learning_curriculum()
