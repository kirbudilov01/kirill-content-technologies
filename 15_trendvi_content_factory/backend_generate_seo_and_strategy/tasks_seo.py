"""Celery tasks для SEO сценариев"""
import logging
from typing import Optional, Dict, Any
from celery_config import celery_app
from generate.crud_seo import add_seo_scenario
from generate.generate_seo import generate_seo_video_completion, generate_seo_shorts_completion
from generate.crud import add_user_credit, get_competitor_analysis_by_id, list_competitor_gpt_reports
from generate.utils import GetVideoException, check_link, get_video_transcript

logger = logging.getLogger(__name__)

_SEO_ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
    "Titles are too short and generic": {
        "ru": "Модель сгенерировала слишком короткие заголовки. Добавьте больше деталей о видео в запросе: тему, аудиторию, ключевые обещания ролика.",
        "en": "The model generated titles that are too short. Add more details to your request: topic, audience, key promises.",
        "es": "El modelo generó títulos demasiado cortos. Añade más detalles: tema, audiencia, promesas clave.",
        "de": "Das Modell hat zu kurze Titel generiert. Füge mehr Details zum Video hinzu: Thema, Zielgruppe, Kernversprechen.",
    },
    "Title openers are repetitive": {
        "ru": "Заголовки получились однообразными — все начинаются похожим образом. Попробуйте переформулировать запрос или укажите разные углы подачи.",
        "en": "Generated titles are too repetitive in structure. Try rephrasing your request or specifying different angles.",
        "es": "Los títulos generados son demasiado repetitivos. Reformula la solicitud o indica distintos enfoques.",
        "de": "Die generierten Titel sind zu gleichförmig. Formuliere die Anfrage um oder gib verschiedene Blickwinkel an.",
    },
    "Description must contain 8-10 sentences": {
        "ru": "Описание получилось слишком коротким. Добавьте больше контекста о видео в промпт.",
        "en": "The generated description is too short. Add more context about the video to your prompt.",
        "es": "La descripción generada es demasiado corta. Añade más contexto sobre el vídeo.",
        "de": "Die generierte Beschreibung ist zu kurz. Ergänze den Prompt um mehr Kontext zum Video.",
    },
    "Insufficient tags": {
        "ru": "Модель сгенерировала недостаточно тегов. Попробуйте снова или расширьте описание темы.",
        "en": "Not enough tags were generated. Try again or expand the topic description.",
        "es": "No se generaron suficientes etiquetas. Inténtalo de nuevo o amplía la descripción del tema.",
        "de": "Es wurden zu wenige Tags generiert. Versuche es erneut oder erweitere die Themenbeschreibung.",
    },
    "Competitor summary is empty": {
        "ru": "Не удалось построить сводку по конкурентам — в выбранном проекте недостаточно данных research. Попробуйте без привязки к проекту.",
        "en": "Could not build competitor summary — the selected project has insufficient research data. Try without a project.",
        "es": "No se pudo generar el resumen de competidores — el proyecto seleccionado tiene datos de investigación insuficientes.",
        "de": "Competitor-Summary konnte nicht erstellt werden — unzureichende Research-Daten im Projekt. Versuche es ohne Projekt.",
    },
    "не удалось получить субтитры": {
        "ru": "Не удалось получить субтитры по ссылке. Убедитесь, что видео загружено с доступом по ссылке и субтитры включены.",
        "en": "Could not fetch subtitles from the link. Make sure the video is published with link access and subtitles are enabled.",
        "es": "No se pudieron obtener los subtítulos del enlace. Verifica que el vídeo sea accesible y tenga subtítulos activados.",
        "de": "Untertitel konnten nicht geladen werden. Stelle sicher, dass das Video per Link zugänglich ist und Untertitel aktiviert sind.",
    },
    "youtube вернул ошибку 429": {
        "ru": "YouTube временно заблокировал запрос (слишком много запросов). Подождите 2–3 минуты и попробуйте снова, или используйте режим «Ручной промпт» вместо ссылки.",
        "en": "YouTube temporarily blocked the request (too many requests). Wait 2–3 minutes and try again, or use Manual prompt mode instead of a link.",
        "es": "YouTube bloqueó temporalmente la solicitud (demasiadas peticiones). Espera 2–3 minutos e inténtalo de nuevo, o usa el modo de prompt manual.",
        "de": "YouTube hat die Anfrage vorübergehend gesperrt (zu viele Anfragen). Warte 2–3 Minuten und versuche es erneut, oder nutze den manuellen Prompt-Modus.",
    },
    "автор запретил скачивать субтитры": {
        "ru": "Автор видео отключил субтитры — их нельзя скачать автоматически. Скопируйте текст вручную и используйте режим «Ручной промпт».",
        "en": "The video author disabled subtitles — they cannot be downloaded automatically. Copy the text manually and use Manual prompt mode.",
        "es": "El autor del vídeo desactivó los subtítulos. Cópialos manualmente y usa el modo de prompt manual.",
        "de": "Der Video-Autor hat Untertitel deaktiviert — sie können nicht automatisch geladen werden. Kopiere den Text manuell und nutze den manuellen Modus.",
    },
    "видео не имеет доступных субтитров": {
        "ru": "У этого видео нет доступных субтитров. Используйте режим «Ручной промпт» и вставьте текст вручную.",
        "en": "This video has no available subtitles. Use Manual prompt mode and paste the text manually.",
        "es": "Este vídeo no tiene subtítulos disponibles. Usa el modo de prompt manual y pega el texto manualmente.",
        "de": "Dieses Video hat keine verfügbaren Untertitel. Nutze den manuellen Prompt-Modus und füge den Text manuell ein.",
    },
    "не удалось скачать файл субтитров": {
        "ru": "Не удалось скачать файл субтитров у YouTube. Попробуйте снова через минуту или используйте режим «Ручной промпт».",
        "en": "Could not download the subtitle file from YouTube. Try again in a minute or use Manual prompt mode.",
        "es": "No se pudo descargar el archivo de subtítulos desde YouTube. Inténtalo de nuevo en un minuto o usa el modo manual.",
        "de": "Die Untertiteldatei konnte nicht von YouTube geladen werden. Versuche es in einer Minute erneut oder nutze den manuellen Modus.",
    },
    "субтитры видео пусты или не загружены": {
        "ru": "YouTube вернул пустые субтитры для этого видео. Попробуйте другой ролик или вставьте текст вручную.",
        "en": "YouTube returned empty subtitles for this video. Try another video or paste the text manually.",
        "es": "YouTube devolvió subtítulos vacíos para este vídeo. Prueba con otro vídeo o pega el texto manualmente.",
        "de": "YouTube hat leere Untertitel für dieses Video zurückgegeben. Versuche ein anderes Video oder füge den Text manuell ein.",
    },
}


def _seo_error_user_message(error_text: str, lang: str) -> str:
    lang_key = lang.lower()[:2] if lang else "en"
    if lang_key not in {"ru", "en", "es", "de"}:
        lang_key = "en"
    err_lower = error_text.lower()
    for key, translations in _SEO_ERROR_MESSAGES.items():
        if key.lower() in err_lower:
            return translations.get(lang_key, translations.get("en", error_text))
    return ""


def _is_youtube_request(value: str) -> bool:
    request_text = str(value or "").strip().lower()
    return bool(request_text) and "://" in request_text and (
        "youtube.com/" in request_text or "youtu.be/" in request_text
    )


def _resolve_generation_input(request_text: str, source_mode: str) -> str:
    normalized_request = str(request_text or "").strip()
    normalized_mode = str(source_mode or "auto").strip().lower()

    if normalized_mode not in {"auto", "manual", "youtube_link"}:
        normalized_mode = "auto"

    if normalized_mode == "manual":
        return normalized_request, False

    should_fetch_transcript = normalized_mode == "youtube_link" or _is_youtube_request(normalized_request)
    if not should_fetch_transcript:
        return normalized_request, False

    video_id = check_link(normalized_request)
    transcript_text = str(get_video_transcript(video_id) or "").strip()
    if not transcript_text:
        raise GetVideoException("Не удалось получить субтитры по ссылке на видео")

    logger.info(
        "[seo-worker] Using fetched transcript for SEO generation: mode=%s, video_id=%s, chars=%d",
        normalized_mode,
        video_id,
        len(transcript_text),
    )
    return transcript_text, True


def _build_analysis_reports_context(reports, max_items: int = 10, max_chars_per_item: int = 320) -> str:
    """Build a compact, ordered reports summary for SEO prompts."""
    if not reports:
        return ""

    ordered_keys = [
        ("all", "project"),
        ("strategy", "project"),
        ("demand", "project"),
        ("shorts", "48h"),
        ("shorts", "7d"),
        ("shorts", "30d"),
        ("videos", "7d"),
        ("videos", "30d"),
        ("videos", "90d"),
        ("viral_shorts", "7d"),
    ]

    indexed = {}
    for report in reports:
        key = (getattr(report, "content_type", None), getattr(report, "period", None))
        if key not in indexed and getattr(report, "report_text", None):
            indexed[key] = report

    ordered_reports = []
    for key in ordered_keys:
        report = indexed.pop(key, None)
        if report:
            ordered_reports.append(report)

    ordered_reports.extend(indexed.values())

    chunks = []
    for report in ordered_reports[:max_items]:
        text = " ".join(str(getattr(report, "report_text", "")).split())
        if not text:
            continue
        excerpt = text[:max_chars_per_item] + ("…" if len(text) > max_chars_per_item else "")
        content_type = getattr(report, "content_type", "unknown")
        period = getattr(report, "period", "unknown")
        chunks.append(f"[{content_type}:{period}] {excerpt}")

    return "\n".join(chunks)


@celery_app.task(name="generate.tasks.generate_seo_scenario", bind=True, queue="seo_scenarios")
def generate_seo_scenario(
    self,
    user_id: int,
    request_text: str,
    scenario_type: str = "video",
    analysis_id: Optional[str] = None,
    scenario_title: Optional[str] = None,
    lang: str = "",
    source_mode: str = "auto",
) -> Dict[str, Any]:
    """
    Celery task для генерации SEO сценария.
    
    Args:
        user_id: ID пользователя
        request_text: Описание видео/сценария
        scenario_type: "video" или "shorts"
        analysis_id: ID анализа конкурентов (опционально)
        scenario_title: Заголовок (опционально)
    
    Returns:
        Dict с результатом генерации
    """
    import asyncio

    refunded_credit = False

    def _refund_seo_credit_once() -> None:
        nonlocal refunded_credit
        if refunded_credit:
            return
        refunded_credit = True
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(add_user_credit(user_id, 1))
        finally:
            loop.close()
    
    try:
        logger.info(f"[seo-worker] Generating {scenario_type} SEO scenario for user {user_id}...")
        
        # Fetch competitor analysis for context if provided
        project_data = None
        effective_lang = (lang or "").lower()
        if effective_lang not in ("ru", "en", "zh"):
            effective_lang = ""

        if analysis_id:
            try:
                # Нужно обернуть async в sync контекст
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                analysis_data = loop.run_until_complete(
                    get_competitor_analysis_by_id(analysis_id, user_id)
                )
                
                if analysis_data:
                    analysis_lang = (getattr(analysis_data, "lang", "") or "").lower()
                    if analysis_lang in ("ru", "en", "zh") and not effective_lang:
                        effective_lang = analysis_lang

                    project_data = {
                        "name": analysis_data.name,
                        "description": analysis_data.description or analysis_data.name or "",
                        "lang": analysis_lang if analysis_lang in ("ru", "en", "zh") else None,
                    }

                    reports = loop.run_until_complete(
                        list_competitor_gpt_reports(analysis_id)
                    )
                    if reports:
                        reports_context = _build_analysis_reports_context(reports)
                        if reports_context:
                            project_data["analysis_reports"] = reports_context

                    logger.info(f"[seo-worker] Loaded project context for analysis {analysis_id}")
                
                loop.close()
            except Exception as e:
                logger.warning(f"[seo-worker] Failed to load analysis context: {e}")
                project_data = None

        if not effective_lang:
            effective_lang = "en"
        
        generation_input, is_transcript = _resolve_generation_input(request_text, source_mode)

        # Generate completion based on type
        logger.info(f"[seo-worker] Generating {scenario_type} SEO recommendations...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if scenario_type == "video":
            gen_result = loop.run_until_complete(
                generate_seo_video_completion(
                    generation_input,
                    project_data,
                    effective_lang,
                    is_transcript=is_transcript,
                )
            )
        else:  # shorts
            gen_result = loop.run_until_complete(
                generate_seo_shorts_completion(
                    generation_input,
                    project_data,
                    effective_lang,
                    is_transcript=is_transcript,
                )
            )
        
        loop.close()
        
        # Validate generation result
        if not gen_result or not gen_result.get("result"):
            raise ValueError("Generation returned empty result")
        
        # Use provided title or generate one from request
        title = scenario_title or request_text[:100]
        
        # Save scenario to database
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        scenario = loop.run_until_complete(
            add_seo_scenario(
                user_id=user_id,
                scenario_type=scenario_type,
                title=title,
                request=request_text,
                response=gen_result["result"],
                analysis_id=analysis_id
            )
        )
        
        loop.close()
        
        logger.info(
            f"[seo-worker] ✅ Generated {scenario_type} SEO recommendations, saved as {scenario.scenario_id}, "
            f"tokens(in={gen_result.get('input_tokens', 0)}, out={gen_result.get('output_tokens', 0)})"
        )
        
        return {
            "status": "success",
            "scenario_id": str(scenario.scenario_id),
            "type": scenario_type,
            "title": title,
            "result": gen_result["result"],
            "source_mode": source_mode,
            "token_usage": {
                "input_tokens": gen_result.get("input_tokens", 0),
                "output_tokens": gen_result.get("output_tokens", 0),
                "total_tokens": gen_result.get("total_tokens", 0),
            }
        }
        
    except Exception as e:
        logger.error(f"[seo-worker] ❌ Task failed: {type(e).__name__}: {str(e)}")
        _refund_seo_credit_once()
        user_message = _seo_error_user_message(str(e), effective_lang if 'effective_lang' in dir() else "en")
        return {
            "status": "error",
            "error": str(e),
            "user_message": user_message,
        }
