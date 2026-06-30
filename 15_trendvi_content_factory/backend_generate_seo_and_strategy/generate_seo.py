"""Functions for generating YouTube SEO recommendations."""
from typing import Dict, Any, Optional
import json
import logging
import re

logger = logging.getLogger(__name__)

def _lang_prompt(lang: str) -> str:
    lang_norm = (lang or "ru").lower()
    if lang_norm == "en":
        return "English"
    if lang_norm == "zh":
        return "Chinese"
    return "Russian"


async def generate_seo_video_completion(
    request: str,
    project_data: Optional[Dict[str, Any]] = None,
    lang: str = "ru",
    is_transcript: bool = False,
) -> Dict[str, Any]:
    """Generate structured SEO recommendations for YouTube long-form videos."""
    return await _generate_seo_completion(
        request=request,
        project_data=project_data,
        lang=lang,
        is_shorts=False,
        is_transcript=is_transcript,
    )


async def generate_seo_shorts_completion(
    request: str,
    project_data: Optional[Dict[str, Any]] = None,
    lang: str = "ru",
    is_transcript: bool = False,
) -> Dict[str, Any]:
    """Generate structured SEO recommendations for YouTube Shorts."""
    return await _generate_seo_completion(
        request=request,
        project_data=project_data,
        lang=lang,
        is_shorts=True,
        is_transcript=is_transcript,
    )


def _extract_json_payload(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    candidate = text.strip()
    if candidate.startswith("```"):
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", candidate, flags=re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _to_score(value: Any) -> int:
    try:
        score = int(float(value))
    except Exception:
        score = 0
    return max(0, min(100, score))


def _normalize_list(value: Any, limit: int) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = []

    unique = []
    seen = set()
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _normalize_description_text(value: str) -> str:
    text = " ".join((value or "").split()).strip()
    if not text:
        return ""

    # Split on common sentence terminators for RU/EN/ZH.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", text) if s.strip()]

    if len(sentences) > 10:
        sentences = sentences[:10]

    return " ".join(sentences).strip()


def _normalize_competitor_summary(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _text_blob_for_language_check(normalized: Dict[str, Any]) -> str:
    chunks = []
    chunks.append(str(normalized.get("competitor_summary") or ""))
    for item in normalized.get("titles") or []:
        chunks.append(str(item.get("title", "")))
        chunks.append(str(item.get("angle", "")))
        chunks.append(str(item.get("why_it_works", "")))
        chunks.append(str(item.get("target_query", "")))
    chunks.append(str(normalized.get("description") or ""))
    chunks.extend(normalized.get("tags") or [])
    chunks.extend(normalized.get("keywords_core") or [])
    return " ".join(chunks)


def _validate_language_consistency(normalized: Dict[str, Any], lang: str) -> None:
    text = _text_blob_for_language_check(normalized)
    if not text.strip():
        raise ValueError("Language check failed: empty output")

    latin_chars = len(re.findall(r"[A-Za-z]", text))
    cyrillic_chars = len(re.findall(r"[А-Яа-яЁё]", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))

    if lang == "ru":
        if cyrillic_chars < max(20, latin_chars * 2):
            raise ValueError("Language mix detected: expected Russian output")
    elif lang == "en":
        if latin_chars < max(30, cyrillic_chars * 2):
            raise ValueError("Language mix detected: expected English output")
    elif lang == "zh":
        if cjk_chars < 20:
            raise ValueError("Language mix detected: expected Chinese output")


def _validate_title_quality(normalized: Dict[str, Any]) -> None:
    titles = normalized.get("titles") or []
    if not titles:
        raise ValueError("No titles generated")

    title_texts = [str(item.get("title") or "").strip() for item in titles]
    if any(len(t) < 28 for t in title_texts):
        raise ValueError("Titles are too short and generic")

    starts_how = 0
    for t in title_texts:
        low = t.lower()
        if low.startswith("как ") or low.startswith("how ") or low.startswith("如何"):
            starts_how += 1
    if starts_how > max(2, len(title_texts) // 2):
        raise ValueError("Title openers are repetitive")



def _normalize_payload(payload: Dict[str, Any], is_shorts: bool, require_competitor_summary: bool = False) -> Dict[str, Any]:
    max_titles = 4 if is_shorts else 6
    min_titles = 3 if is_shorts else 5

    titles_raw = payload.get("titles") or []
    normalized_titles = []
    seen_titles = set()

    for item in titles_raw:
        if isinstance(item, str):
            data = {
                "title": item.strip(),
                "angle": "",
                "why_it_works": "",
                "target_query": "",
                "scores": {"ctr": 0, "relevance": 0, "uniqueness": 0},
                "risk_flags": [],
            }
        elif isinstance(item, dict):
            scores = item.get("scores") or {}
            data = {
                "title": str(item.get("title", "")).strip(),
                "angle": str(item.get("angle", "")).strip(),
                "why_it_works": str(item.get("why_it_works", "")).strip(),
                "target_query": str(item.get("target_query", "")).strip(),
                "scores": {
                    "ctr": _to_score(scores.get("ctr")),
                    "relevance": _to_score(scores.get("relevance")),
                    "uniqueness": _to_score(scores.get("uniqueness")),
                },
                "risk_flags": _normalize_list(item.get("risk_flags") or [], 4),
            }
        else:
            continue

        if not data["title"]:
            continue

        key = data["title"].lower()
        if key in seen_titles:
            continue

        seen_titles.add(key)
        normalized_titles.append(data)
        if len(normalized_titles) >= max_titles:
            break

    description_raw = payload.get("description")
    if isinstance(description_raw, dict):
        description_text = str(
            description_raw.get("full_text")
            or description_raw.get("text")
            or description_raw.get("description")
            or ""
        ).strip()
    else:
        description_text = str(description_raw or "").strip()

    description_text = _normalize_description_text(description_text)

    tags_list = _normalize_list(payload.get("tags"), 20 if not is_shorts else 15)
    keywords_core_list = _normalize_list(payload.get("keywords_core"), 12 if not is_shorts else 8)
    competitor_patterns = _normalize_list(payload.get("competitor_patterns_used"), 6)
    competitor_summary = _normalize_competitor_summary(payload.get("competitor_summary"))
    
    normalized = {
        "competitor_summary": competitor_summary,
        "titles": normalized_titles,
        "description": description_text,
        "tags": ", ".join(tags_list),
        "keywords_core": ", ".join(keywords_core_list),
        "competitor_patterns_used": competitor_patterns,
    }

    if len(normalized["titles"]) < min_titles:
        raise ValueError(f"Insufficient title variants: {len(normalized['titles'])}")
    if not normalized["description"]:
        raise ValueError("Description is empty")

    sentence_count = len([s for s in re.split(r"(?<=[.!?。！？])\s+", normalized["description"]) if s.strip()])
    if sentence_count < 8:
        raise ValueError("Description must contain 8-10 sentences")
    if len(tags_list) < 8:
        raise ValueError("Insufficient tags")
    if require_competitor_summary and not normalized["competitor_summary"]:
        raise ValueError("Competitor summary is empty")
    if require_competitor_summary and len(competitor_patterns) < 3:
        raise ValueError("Competitor patterns are missing")

    _validate_title_quality(normalized)

    return normalized


def _build_prompt(
    request: str,
    lang: str,
    is_shorts: bool,
    project_data: Optional[Dict[str, Any]],
    analysis_context: str,
    is_transcript: bool = False,
) -> str:
    output_language = _lang_prompt(lang)
    title_count = 4 if is_shorts else 6
    tags_count = 15 if is_shorts else 20
    keyword_count = 8 if is_shorts else 12
    format_name = "YouTube Shorts" if is_shorts else "YouTube long-form videos"

    project_desc = ""
    if project_data and project_data.get("description"):
        project_desc = f"Project/channel context: {project_data['description']}\n"

    if is_transcript:
        request_label = "Video transcript (base ALL SEO output strictly on this video's actual content — titles, description, tags must reflect what this specific video is about):"
        task_extra = "- The primary input is the video transcript. ALL titles, description, tags and keywords must be derived from and faithful to the actual content of this transcript. Do not generate generic channel-level content.\n"
    else:
        request_label = "User request:"
        task_extra = ""

    return f"""You are a senior YouTube SEO strategist.

Write all text fields in {output_language} only.
Return STRICT VALID JSON only. No markdown, no comments, no code fences.

Task:
- First, synthesize one compact competitor-summary paragraph about what titles, hooks, packaging angles, and SEO patterns competitors are using, plus what the creator should keep in mind.
- Create SEO package for {format_name}.
- If competitor analysis context is provided, use it as a required grounding source for the competitor summary, title angles, description framing, and competitor_patterns_used.
- Be specific and non-generic. No filler phrases.
- Do not fabricate facts, numbers, or claims.
- Keep all generated text strictly in one language ({output_language}).
- Description must be one continuous creator-ready text block of 8-10 sentences.
{task_extra}
{project_desc}{analysis_context}
{request_label}
{request}

Hard quality rules:
- If competitor/context summary is available, competitor_summary must explain what stands out in competitors' titles/angles and give concrete cautions or opportunities for this creator.
- Titles must be distinct in angle and wording.
- Avoid template repetition, but keep strong CTR intent.
- Include concrete audience benefit in each title idea.
- Description should be creator-ready and searchable.
- Titles should feel punchy and curiosity-driven (without fake promises).
- Use varied opening patterns (question, contrarian claim, myth busting, mistake, practical outcome).
- Do not generate bland repetitive "How to ..." headlines.

Output JSON schema:
{{
    "competitor_summary": "...one paragraph grounded in competitor/context data, or empty string if no such data exists...",
  "titles": [
    {{
      "title": "...",
      "angle": "...",
      "why_it_works": "...",
      "target_query": "...",
      "scores": {{"ctr": 0-100, "relevance": 0-100, "uniqueness": 0-100}},
      "risk_flags": ["optional_risk_flag"]
    }}
  ],
  "description": "...continuous plain text, 8-10 sentences...",
  "tags": ["..."],
  "keywords_core": ["..."],
    "competitor_patterns_used": ["..."]
}}

Cardinality constraints:
- competitor_summary: 1 compact paragraph if competitor/context exists, otherwise empty string
- titles: exactly {title_count}
- tags: exactly {tags_count}
- keywords_core: exactly {keyword_count}
- competitor_patterns_used: 3 to 5 items
- risk_flags: only if risk exists; otherwise []
- description: plain continuous paragraph text only (no labels like Hook/Value/CTA, no markdown)
"""


async def _generate_seo_completion(
    request: str,
    project_data: Optional[Dict[str, Any]],
    lang: str,
    is_shorts: bool,
    is_transcript: bool = False,
) -> Dict[str, Any]:
    from .generate import _call_openai_with_proxy_fallback, _truncate_context

    lang_norm = (lang or "en").lower()
    if lang_norm not in ("ru", "en", "zh"):
        lang_norm = "en"

    analysis_context = ""
    has_analysis_context = False
    if project_data and project_data.get("analysis_reports"):
        max_chars = 1600 if is_shorts else 2200
        summary = _truncate_context(project_data["analysis_reports"], max_chars)
        analysis_context = f"Competitor/context summary:\n{summary}\n"
        has_analysis_context = True

    base_prompt = _build_prompt(
        request=request,
        lang=lang_norm,
        is_shorts=is_shorts,
        project_data=project_data,
        analysis_context=analysis_context,
        is_transcript=is_transcript,
    )

    def _build_fix_prompt(previous_output: str, validation_error: str) -> str:
        return (
            f"{base_prompt}\n\n"
            "CORRECTION MODE:\n"
            "Your previous response failed strict validation.\n"
            f"Validation error: {validation_error}\n"
            "Return corrected STRICT VALID JSON only.\n"
            "Do not add explanations, markdown, or code fences.\n\n"
            "Previous response:\n"
            f"{previous_output}"
        )

    try:
        max_retries = 2
        attempt = 0
        prompt = base_prompt
        cumulative_input_tokens = 0
        cumulative_output_tokens = 0
        cumulative_total_tokens = 0

        while True:
            result, input_tokens, output_tokens, total_tokens = await _call_openai_with_proxy_fallback(
                prompt=prompt,
                model="gpt-4o",
                max_tokens=2200 if not is_shorts else 1400,
                timeout=50 if not is_shorts else 40,
                temperature=0.45,
            )

            cumulative_input_tokens += input_tokens
            cumulative_output_tokens += output_tokens
            cumulative_total_tokens += total_tokens

            try:
                payload = _extract_json_payload(result)
                if not payload:
                    raise ValueError("Model did not return valid JSON")

                normalized = _normalize_payload(
                    payload,
                    is_shorts=is_shorts,
                    require_competitor_summary=has_analysis_context,
                )
                _validate_language_consistency(normalized, lang_norm)

                logger.info(
                    "[GPT] Generated SEO %s recommendations: titles=%d, tags=%d, tokens=%d, retries=%d",
                    "shorts" if is_shorts else "video",
                    len(normalized["titles"]),
                    len(normalized["tags"]),
                    cumulative_total_tokens,
                    attempt,
                )

                return {
                    "result": json.dumps(normalized, ensure_ascii=False, indent=2),
                    "input_tokens": cumulative_input_tokens,
                    "output_tokens": cumulative_output_tokens,
                    "total_tokens": cumulative_total_tokens,
                }
            except Exception as validation_error:
                if attempt >= max_retries:
                    raise

                attempt += 1
                logger.warning(
                    "[GPT] SEO %s validation failed on attempt %d: %s. Retrying with correction prompt.",
                    "shorts" if is_shorts else "video",
                    attempt,
                    validation_error,
                )
                prompt = _build_fix_prompt(result, str(validation_error))
    except Exception as e:
        logger.error(
            "[GPT] Failed to generate SEO %s: %s: %s",
            "shorts" if is_shorts else "video",
            type(e).__name__,
            e,
        )
        raise
