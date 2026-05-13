"""Pixellab animation template registry.

Maps high-level action names (`idle`, `walk`, `running`, ...) to the
Pixellab `template_animation_id` they should render with, plus the
directions and frame_count those templates expect.

We default to **template mode** for these stages — Pixellab's skeleton-based
templates produce stable, predictable motion at 1 generation per direction.
v3 (prompt-driven) mode is reserved for one-off custom animations Pixellab
doesn't cover; do NOT add new entries here that route to v3.

Adding a new action (e.g., "running"):

    1. Add entry to DEFAULT_TEMPLATES below.
    2. In the orchestrator (npc_moving.py / npc_static.py):
       a. Add a `@stage("add_<action>_animation")` function that calls
          `run_character_animation_template(ctx, "<action>", ...)`.
       b. Append the stage name to STAGES.
       c. Call the stage function in main().
    3. Add a CLI flag `--<action>-template-id` (optional, lets caller swap
       the default template for a variant).

That's the whole pattern.
"""
from __future__ import annotations

from dataclasses import dataclass


CARDINAL_DIRECTIONS: list[str] = ["south", "east", "north", "west"]
ALL_8_DIRECTIONS: list[str] = [
    "south", "east", "north", "west",
    "south-east", "north-east", "north-west", "south-west",
]


@dataclass(frozen=True)
class AnimationTemplate:
    """Per-action defaults for Pixellab template-mode animation."""
    template_id: str
    directions: list[str]
    frame_count: int  # Pixellab-determined; we send as hint, server may ignore


# Action → default template. Caller (CLI flag) can override template_id only;
# directions/frame_count are intrinsic to the chosen template family.
DEFAULT_TEMPLATES: dict[str, AnimationTemplate] = {
    "idle": AnimationTemplate(
        template_id="breathing-idle",
        directions=CARDINAL_DIRECTIONS,
        frame_count=5,
    ),
    "walk": AnimationTemplate(
        template_id="walking-6-frames",
        directions=ALL_8_DIRECTIONS,
        frame_count=6,
    ),
    # To add: "running": AnimationTemplate(template_id="running-N-frames", ...)
    # See module docstring for orchestrator wiring steps.
}


def get_template(action: str, override_template_id: str | None = None) -> AnimationTemplate:
    """Look up the template config for an action, optionally swapping template_id.

    `override_template_id`: if a CLI flag like --walk-template-id was given,
    use that instead of the default. directions/frame_count come from the
    base config (caller's swap probably stays in same template family).
    """
    if action not in DEFAULT_TEMPLATES:
        raise KeyError(
            f"unknown animation action {action!r}; known: "
            f"{sorted(DEFAULT_TEMPLATES.keys())}. To add a new one, see "
            f"the module docstring in pipeline/animation_templates.py."
        )
    base = DEFAULT_TEMPLATES[action]
    if override_template_id:
        return AnimationTemplate(
            template_id=override_template_id,
            directions=base.directions,
            frame_count=base.frame_count,
        )
    return base
