from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_MODELS_DIRECTORY = Path(
    "data/model_training/bases"
)

CANDIDATES_DIRECTORY = Path(
    "data/model_training/candidates"
)


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def trainable_parameter_sha256(
    model: Any,
) -> str:
    digest = hashlib.sha256()

    found = 0

    for name, parameter in sorted(
        model.named_parameters()
    ):
        if not parameter.requires_grad:
            continue

        found += 1

        digest.update(
            name.encode(
                "utf-8"
            )
        )

        digest.update(
            parameter.detach()
            .cpu()
            .contiguous()
            .numpy()
            .tobytes()
        )

    if found == 0:
        raise RuntimeError(
            "No trainable LoRA parameters "
            "were found."
        )

    return digest.hexdigest()


def require_text(
    value: str,
    *,
    field_name: str,
) -> str:
    value = value.strip()

    if not value:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return value


def run_training_proof(
    *,
    model_name: str,
    instruction: str,
    expected_response: str,
    expected_base_sha256: str,
) -> dict[str, Any]:
    import torch

    from peft import (
        LoraConfig,
        PeftModel,
        TaskType,
        get_peft_model,
    )

    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
    )

    model_name = require_text(
        model_name,
        field_name="model_name",
    )

    instruction = require_text(
        instruction,
        field_name="instruction",
    )

    expected_response = require_text(
        expected_response,
        field_name="expected_response",
    )

    expected_base_sha256 = (
        require_text(
            expected_base_sha256,
            field_name=(
                "expected_base_sha256"
            ),
        )
    )

    base_directory = (
        BASE_MODELS_DIRECTORY
        / model_name
    ).resolve()

    if not base_directory.is_dir():
        raise RuntimeError(
            "Base model directory "
            f"does not exist: {base_directory}"
        )

    base_weights_path = (
        base_directory
        / "model.safetensors"
    )

    if not base_weights_path.is_file():
        raise RuntimeError(
            "Base model weights were not found."
        )

    base_before_sha256 = (
        sha256_file(
            base_weights_path
        )
    )

    if (
        base_before_sha256
        != expected_base_sha256
    ):
        raise RuntimeError(
            "Current Qwen base model does not "
            "match the captured baseline.\n"
            f"expected={expected_base_sha256}\n"
            f"actual={base_before_sha256}"
        )

    tokenizer = (
        AutoTokenizer.from_pretrained(
            base_directory,
            local_files_only=True,
        )
    )

    if (
        tokenizer.pad_token_id
        is None
        and tokenizer.eos_token_id
        is not None
    ):
        tokenizer.pad_token = (
            tokenizer.eos_token
        )

    base_model = (
        AutoModelForCausalLM
        .from_pretrained(
            base_directory,
            local_files_only=True,
            dtype=torch.float32,
        )
    )

    lora_configuration = LoraConfig(
        task_type=(
            TaskType.CAUSAL_LM
        ),
        inference_mode=False,
        r=8,
        lora_alpha=16,
        lora_dropout=0.0,
        bias="none",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
        ],
    )

    model = get_peft_model(
        base_model,
        lora_configuration,
    )

    model.train()

    trainable_parameters = [
        parameter
        for parameter
        in model.parameters()
        if parameter.requires_grad
    ]

    trainable_parameter_count = sum(
        parameter.numel()
        for parameter
        in trainable_parameters
    )

    if trainable_parameter_count == 0:
        raise RuntimeError(
            "LoRA produced no "
            "trainable parameters."
        )

    prompt = (
        "Instruction:\n"
        f"{instruction}\n\n"
        "Response:\n"
    )

    prompt_token_ids = (
        tokenizer(
            prompt,
            add_special_tokens=False,
        )[
            "input_ids"
        ]
    )

    response_token_ids = (
        tokenizer(
            expected_response,
            add_special_tokens=False,
        )[
            "input_ids"
        ]
    )

    if not response_token_ids:
        raise RuntimeError(
            "Expected response produced "
            "no training tokens."
        )

    eos_tokens: list[int] = []

    if tokenizer.eos_token_id is not None:
        eos_tokens = [
            tokenizer.eos_token_id
        ]

    input_token_ids = (
        prompt_token_ids
        + response_token_ids
        + eos_tokens
    )

    labels = (
        [-100]
        * len(
            prompt_token_ids
        )
        + response_token_ids
        + eos_tokens
    )

    if len(
        input_token_ids
    ) > 256:
        raise RuntimeError(
            "Training example is longer "
            "than 256 tokens. Use a shorter "
            "instruction or response."
        )

    input_ids = torch.tensor(
        [
            input_token_ids
        ],
        dtype=torch.long,
    )

    attention_mask = torch.ones_like(
        input_ids
    )

    label_tensor = torch.tensor(
        [
            labels
        ],
        dtype=torch.long,
    )

    optimizer = torch.optim.AdamW(
        trainable_parameters,
        lr=1e-3,
    )

    lora_before_sha256 = (
        trainable_parameter_sha256(
            model
        )
    )

    optimizer.zero_grad(
        set_to_none=True
    )

    output = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        labels=label_tensor,
    )

    loss = output.loss

    if not torch.isfinite(
        loss
    ):
        raise RuntimeError(
            "Training loss was not finite."
        )

    loss_value = float(
        loss.detach()
        .cpu()
        .item()
    )

    loss.backward()

    gradient_parameter_count = 0

    for parameter in (
        trainable_parameters
    ):
        gradient = parameter.grad

        if gradient is None:
            continue

        if (
            torch.count_nonzero(
                gradient
            ).item()
            > 0
        ):
            gradient_parameter_count += 1

    if gradient_parameter_count == 0:
        raise RuntimeError(
            "Backward propagation produced "
            "no non-zero LoRA gradients."
        )

    optimizer.step()

    lora_after_sha256 = (
        trainable_parameter_sha256(
            model
        )
    )

    lora_weights_changed = (
        lora_before_sha256
        != lora_after_sha256
    )

    if not lora_weights_changed:
        raise RuntimeError(
            "LoRA parameter hash did not "
            "change after optimizer.step()."
        )

    candidate_id = str(
        uuid4()
    )

    candidate_directory = (
        CANDIDATES_DIRECTORY
        / candidate_id
    ).resolve()

    candidate_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    model.save_pretrained(
        candidate_directory,
        safe_serialization=True,
    )

    adapter_path = (
        candidate_directory
        / "adapter_model.safetensors"
    )

    if not adapter_path.is_file():
        raise RuntimeError(
            "Trained adapter was not saved."
        )

    adapter_sha256 = (
        sha256_file(
            adapter_path
        )
    )

    base_after_sha256 = (
        sha256_file(
            base_weights_path
        )
    )

    base_model_unchanged = (
        base_before_sha256
        == base_after_sha256
    )

    if not base_model_unchanged:
        raise RuntimeError(
            "The original Qwen base model "
            "changed during LoRA training."
        )

    manifest = {
        "candidate_id": (
            candidate_id
        ),
        "model_name": (
            model_name
        ),
        "training_type": (
            "lora_instruction_fine_tuning_proof"
        ),
        "base_model_before_sha256": (
            base_before_sha256
        ),
        "base_model_after_sha256": (
            base_after_sha256
        ),
        "base_model_unchanged": (
            base_model_unchanged
        ),
        "trainable_parameter_count": (
            trainable_parameter_count
        ),
        "instruction_token_count": (
            len(
                prompt_token_ids
            )
        ),
        "response_token_count": (
            len(
                response_token_ids
            )
        ),
        "loss": (
            loss_value
        ),
        "backward_pass_proven": True,
        "nonzero_gradient_parameters": (
            gradient_parameter_count
        ),
        "optimizer_step_proven": True,
        "lora_before_sha256": (
            lora_before_sha256
        ),
        "lora_after_sha256": (
            lora_after_sha256
        ),
        "lora_weights_changed": (
            lora_weights_changed
        ),
        "adapter_saved": True,
        "adapter_sha256": (
            adapter_sha256
        ),
        "released": False,
        "activated": False,
    }

    manifest_path = (
        candidate_directory
        / "training_proof_manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    del optimizer
    del model
    del base_model

    gc.collect()

    reloaded_base_model = (
        AutoModelForCausalLM
        .from_pretrained(
            base_directory,
            local_files_only=True,
            dtype=torch.float32,
        )
    )

    reloaded_model = (
        PeftModel.from_pretrained(
            reloaded_base_model,
            candidate_directory,
            is_trainable=False,
        )
    )

    adapter_reload_proven = (
        reloaded_model is not None
    )

    manifest[
        "adapter_reload_proven"
    ] = adapter_reload_proven

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        **manifest,
        "candidate_directory": str(
            candidate_directory
        ),
        "manifest_path": str(
            manifest_path
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one controlled LoRA "
            "instruction fine-tuning step "
            "and prove the weight change."
        )
    )

    parser.add_argument(
        "--model",
        required=True,
    )

    parser.add_argument(
        "--instruction",
        required=True,
    )

    parser.add_argument(
        "--response",
        required=True,
    )

    parser.add_argument(
        "--expected-base-sha256",
        required=True,
    )

    arguments = parser.parse_args()

    result = run_training_proof(
        model_name=(
            arguments.model
        ),
        instruction=(
            arguments.instruction
        ),
        expected_response=(
            arguments.response
        ),
        expected_base_sha256=(
            arguments
            .expected_base_sha256
        ),
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
