from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


def verify_web_application_behavior(
    workspace: Path,
    entry_file: str = "index.html",
    timeout_ms: int = 15_000,
) -> dict[str, Any]:
    """Execute domain-agnostic behavioral verification in headless Chromium.

    Verifies that a generated HTML/JS application:
    1. Renders in a real browser engine with zero uncaught page or console errors.
    2. Exposes interactive UI controls (inputs, selects, textareas, or buttons).
    3. Mutates DOM state in response to user input and action triggers.
    """
    from playwright.sync_api import sync_playwright

    target_html = (workspace / entry_file).resolve()
    if not target_html.is_file():
        return {
            "execution_id": str(uuid4()),
            "stage": "functional_test",
            "success": False,
            "error": f"Entry HTML file missing: {entry_file}",
            "js_errors": [],
            "controls_discovered": 0,
            "controls_exercised": 0,
            "dom_mutated": False,
            "duration_seconds": 0.0,
        }

    chrome_bin = os.environ.get("CHROMIUM_BIN", "/usr/bin/google-chrome-stable")
    execution_id = str(uuid4())
    started = time.monotonic()
    js_errors: list[str] = []
    controls_discovered = 0
    controls_exercised = 0
    dom_mutated = False
    error_detail: str | None = None

    try:
        with sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {"headless": True}
            if Path(chrome_bin).is_file():
                launch_kwargs["executable_path"] = chrome_bin

            browser = p.chromium.launch(**launch_kwargs)
            try:
                context = browser.new_context(offline=True)
                page = context.new_page()
                page.set_default_timeout(timeout_ms)

                page.on("pageerror", lambda err: js_errors.append(str(err)))
                page.on(
                    "console",
                    lambda msg: js_errors.append(msg.text)
                    if msg.type == "error"
                    else None,
                )

                page.goto(target_html.as_uri(), wait_until="load")
                page.wait_for_timeout(150)

                baseline_html = page.locator("body").inner_html()
                baseline_text = page.locator("body").inner_text().strip()

                text_inputs = page.locator(
                    "input[type='text']:visible, input:not([type]):visible, textarea:visible"
                )
                num_inputs = page.locator("input[type='number']:visible")
                selects = page.locator("select:visible")
                buttons = page.locator(
                    "button:visible, input[type='submit']:visible, input[type='button']:visible"
                )

                controls_discovered = (
                    text_inputs.count()
                    + num_inputs.count()
                    + selects.count()
                    + buttons.count()
                )

                # Populate visible inputs with representative valid values
                for idx in range(min(text_inputs.count(), 3)):
                    inp = text_inputs.nth(idx)
                    if inp.is_enabled():
                        inp.fill(f"Sample Item {idx + 1}")
                        controls_exercised += 1

                for idx in range(min(num_inputs.count(), 3)):
                    inp = num_inputs.nth(idx)
                    if inp.is_enabled():
                        inp.fill("25")
                        controls_exercised += 1

                for idx in range(min(selects.count(), 2)):
                    sel = selects.nth(idx)
                    if sel.is_enabled():
                        options = sel.locator("option")
                        if options.count() > 1:
                            val = options.nth(1).get_attribute("value")
                            if val is not None:
                                sel.select_option(val)
                                controls_exercised += 1

                # Prioritize primary creation/action buttons before destructive/reset controls
                primary_buttons = buttons.filter(
                    has_text=re.compile(
                        r"add|create|submit|save|calculate|start|new|next|send|record",
                        re.I,
                    )
                )
                target_buttons = (
                    primary_buttons if primary_buttons.count() > 0 else buttons
                )

                for idx in range(min(target_buttons.count(), 3)):
                    btn = target_buttons.nth(idx)
                    if btn.is_enabled():
                        btn.click()
                        controls_exercised += 1
                        page.wait_for_timeout(100)
                        current_html = page.locator("body").inner_html()
                        current_text = page.locator("body").inner_text().strip()
                        if (
                            current_html != baseline_html
                            or current_text != baseline_text
                        ):
                            dom_mutated = True
                            break

                # Fallback: if no primary button mutated DOM, exercise remaining interactive buttons
                if not dom_mutated and buttons.count() > 0:
                    for idx in range(min(buttons.count(), 5)):
                        btn = buttons.nth(idx)
                        if btn.is_enabled():
                            btn.click()
                            controls_exercised += 1
                            page.wait_for_timeout(100)
                            if (
                                page.locator("body").inner_html() != baseline_html
                                or page.locator("body").inner_text().strip() != baseline_text
                            ):
                                dom_mutated = True
                                break

                if js_errors:
                    error_detail = f"Runtime JavaScript error(s): {js_errors[:3]}"
                elif controls_discovered == 0:
                    error_detail = "No interactive controls rendered in browser DOM."
                elif not dom_mutated:
                    error_detail = "Interactive controls did not produce any observable DOM state mutation."
            finally:
                browser.close()
    except Exception as exc:
        error_detail = f"{type(exc).__name__}: {exc}"

    duration = round(time.monotonic() - started, 3)
    success = error_detail is None and len(js_errors) == 0 and dom_mutated

    return {
        "execution_id": execution_id,
        "stage": "functional_test",
        "success": success,
        "error": error_detail,
        "js_errors": js_errors[:10],
        "controls_discovered": controls_discovered,
        "controls_exercised": controls_exercised,
        "dom_mutated": dom_mutated,
        "duration_seconds": duration,
    }
