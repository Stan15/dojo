import sys
import warnings
import re
from pathlib import Path

# Fallback templates in case files are missing or unreadable in a frozen binary
FALLBACK_TEMPLATES = {
    "exercise_generate.md": (
        "Draft practice candidates from the provided source references.\n"
        "If topic is provided, treat it as an optional parent-topic hint, not a single-topic assertion. "
        "Return candidates that may span multiple subtopics.\n"
        "If you realize you lack sufficient context about the user's goals, prior knowledge, or learning style for this topic to generate useful, calibrated exercises, or if you determine a pedagogical intervention is needed, you may instead generate 1–3 highly targeted, concise diagnostic questions to help personalize future sessions (set their 'quality' to 'diagnostic').\n\n"
        "ADDITIONAL PEDAGOGICAL GUIDELINES:\n"
        "1. Self-Containment (No Fake Attachments): If no grounding source material is available (source content is empty), you must NOT refer to external or non-existent files, templates, worksheets, or 'checklists below'. Ensure all instructions and tasks are fully self-contained and answerable using only the text inside the prompt.\n"
        "2. Domain-Specific Practice (No Meta-Study Drills): Focus practice exercises on active production, retrieval, and application of the target domain itself. Do NOT generate meta-study or plan-reflection exercises (e.g. asking the user to explain their own study targets, scoring rubrics, or study schedules) even if the active topic path represents an orientation or diagnostic milestone.\n"
        "3. Complete Prompt Packaging: The complete body of the exercise (including any sub-tasks, checklist items, options, or context) must be written entirely inside the single string 'prompt' field. Do NOT output custom keys like 'learner_tasks' or 'tasks' for prompt content.\n\n"
        "{{ active_topics_context }}\n"
        "{{ phase_focus_context }}\n"
        "{{ learner_profile_context }}\n"
        "{{ schema_instructions }}"
    ),
    "profile_consolidate.md": (
        "Analyze the learner's recent practice attempts, user feedback, and goals to refine the campaign mission and strategy.\n\n"
        "PEDAGOGICAL PRINCIPLES FOR CONSOLIDATION:\n"
        "1. Stability & Pacing: Prefer a stable, consistent attack plan. Avoid unnecessary churn. Proactively refine the active or future phases only when the learner is stuck, exhibits prerequisites gaps, demonstrates mastery ahead of schedule, or shifts interest.\n"
        "2. Self-Stated Constraints & Timeline-Awareness: Adapt the plan to the learner's constraints. If they face a tight timeline or milestone, compress the attack plan to target the highest-leverage concepts first and scale down completion criteria.\n"
        "3. Hypothesis-Driven Calibration: Actively manage learner hypotheses (misconceptions/patterns). Create new hypotheses for new mistake patterns, refine active ones, and archive them when the learner consistently demonstrates correct production. Use these hypotheses to adjust difficulty and scaffolding.\n"
        "4. Goal-Based Progression: Sequence the attack plan logically to match the learner's overall mission. Ensure early stages focus on low-stakes diagnostic calibration to discover baseline capabilities, and design subsequent phases to build and interleave complex skills progressively.\n"
        "5. Behavioral Signals (Skips & Feedback): Treat skips (e.g. 'too_easy', 'too_hard') and user feedback as critical calibration signals. Adjust strategy parameters (mode, difficulty, scaffolding) to keep the learner in their Zone of Proximal Development.\n\n"
        "{{ schema_instructions }}"
    )
}

def load_prompt(filename: str, placeholders: dict[str, str]) -> str:
    """
    Loads prompt template from the local prompts folder. Falls back to embedded defaults if missing.
    Interpolates {{ placeholder }} double-brace variables safely, asserting no unmatched variables remain.
    """
    template_text = None
    
    # 1. Resolve relative path (supporting PyInstaller _MEIPASS when frozen)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS) / "dojo" / "prompts"
    else:
        base_path = Path(__file__).parent
        
    prompt_file = base_path / filename
    if prompt_file.exists():
        try:
            template_text = prompt_file.read_text(encoding="utf-8")
        except Exception as exc:
            warnings.warn(f"Failed to read prompt file {filename}: {exc}. Using fallback template.")
            
    if template_text is None:
        template_text = FALLBACK_TEMPLATES.get(filename)
        if template_text is None:
            raise FileNotFoundError(f"Prompt template {filename} not found and no fallback exists.")

    # 2. Extract and verify placeholders in template
    found_placeholders = re.findall(r"\{\{\s*(\w+)\s*\}\}", template_text)
    
    # 3. Perform string replacement
    result_text = template_text
    for key, val in placeholders.items():
        placeholder_pat = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")
        result_text = placeholder_pat.sub(val, result_text)
        
    # Verify that all found placeholders were replaced
    remaining_placeholders = re.findall(r"\{\{\s*(\w+)\s*\}\}", result_text)
    if remaining_placeholders:
        warnings.warn(
            f"Prompt template {filename} contains remaining un-interpolated placeholders: "
            f"{', '.join(set(remaining_placeholders))}. Missing keys from placeholders input: "
            f"{list(placeholders.keys())}"
        )
        
    return result_text
