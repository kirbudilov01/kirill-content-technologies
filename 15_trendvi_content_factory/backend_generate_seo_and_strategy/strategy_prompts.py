from typing import Dict, Any, List


def _safe_text(value: Any, fallback: str = "—") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def build_strategy_prompts(payload: Dict[str, Any]) -> Dict[str, str]:
    """Build reusable prompt templates for strategy and demand workers.

    Payload keys are optional. Missing keys are replaced with safe defaults.
    """
    project_name = _safe_text(payload.get("project_name"), "Untitled Project")
    mode = _safe_text(payload.get("mode"), "trend")
    lang = _safe_text(payload.get("lang"), "ru")
    top_format = _safe_text(payload.get("top_format"), "unknown")
    top_score = _safe_text(payload.get("top_score"), "0")
    readiness = _safe_text(payload.get("readiness"), "0")
    classifier_confidence = _safe_text(payload.get("classifier_confidence"), "0")
    long_tail_coverage = _safe_text(payload.get("long_tail_coverage"), "0")
    demand_gaps: List[str] = payload.get("demand_gaps") or []
    demand_gap_text = ", ".join(demand_gaps[:5]) if demand_gaps else "no explicit demand gaps found"

    strategy_system = (
        "You are TrendVI Strategy Assistant. "
        "Return concise, actionable channel strategy based on provided metrics. "
        "Do not hallucinate missing data. If confidence is low, say it clearly."
    )

    strategy_user = f"""
Project: {project_name}
Language: {lang}
Mode: {mode}
Top format: {top_format}
Top strategy score: {top_score}
Readiness score: {readiness}
Classifier confidence: {classifier_confidence}
Long-tail coverage (proxy): {long_tail_coverage}
Demand gaps: {demand_gap_text}

Task:
1) Write a 30-second client pitch.
2) Propose a 14-day execution plan (3-5 steps).
3) Define KPI targets for 14 days.
4) Add top 3 risks and mitigation actions.
5) Keep output concise and consultation-ready.
""".strip()

    demand_system = (
        "You are TrendVI Demand Gap Analyst. "
        "Find underserved demand opportunities from topic/format mix and confidence signals. "
        "Be specific, practical, and non-generic. "
        "Always return structured, decision-ready output."
    )

    demand_user = f"""
Project: {project_name}
Mode: {mode}
Top format: {top_format}
Classifier confidence: {classifier_confidence}
Known demand gaps: {demand_gap_text}

Task:
1) Rank top 5 underfilled demand opportunities.
2) For each opportunity include exactly:
    - theme_cluster
    - user_pain
    - why_now
    - recommended_format
    - hook_example (1 short title line)
    - test_plan_14_days (2 concrete video tests)
    - expected_signal (comments_rate / subscriber_intent / retention_proxy)
    - confidence (0-100)
3) Add priority_score (0-100) and sort descending.
4) Mark low-confidence items explicitly and do not hallucinate facts.

Output format (strict):
- Section A: "Top Opportunities" (numbered 1..5)
- Section B: "14-day Test Plan" (exactly 5 bullet points)
- Section C: "Risks & Filters" (3 bullets: what to avoid)

Rules:
- No generic advice like "post regularly" without concrete topic/format.
- Use short, actionable language for consultation handoff.
- If data is weak, say "low confidence" and reduce certainty.
""".strip()

    classifier_system = (
        "You are TrendVI Content Type Classifier QA. "
        "Validate content type labels and assign confidence 0-100 with short reason."
    )

    classifier_user = f"""
Project: {project_name}
Current classifier confidence: {classifier_confidence}

Task:
1) Validate labels: news, guide, beginner, breakdown, case, other.
2) Return corrected label when needed.
3) Provide confidence and short reason.
4) Keep response machine-readable JSON array.
""".strip()

    return {
        "strategy_system": strategy_system,
        "strategy_user": strategy_user,
        "demand_system": demand_system,
        "demand_user": demand_user,
        "classifier_system": classifier_system,
        "classifier_user": classifier_user,
    }
