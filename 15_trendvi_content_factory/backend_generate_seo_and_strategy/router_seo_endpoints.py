"""REST endpoints для SEO сценариев (добавить в router.py)"""

# Добавить в импорты router.py:
# from generate_seo.crud_seo import add_seo_scenario, get_seo_scenario, list_seo_scenarios, delete_seo_scenario, update_seo_scenario
# from generate_seo.models import SeoScenarioModel, CreateSeoScenarioRequest, SeoScenarioListResponse

# Добавить в роутер:

# ============ SEO СЦЕНАРИИ ============

@generate_router.post("/seo/scenarios")
async def create_seo_scenario_endpoint(
    body: CreateSeoScenarioRequest,
    user: AuthUserModel = Depends(get_current_user)
) -> dict:
    """
    Создать SEO сценарий напрямую (уже сгенерированный).
    Обычно используется после завершения Celery task.
    """
    try:
        scenario = await add_seo_scenario(
            user_id=user.user_id,
            scenario_type=body.type,
            title=body.title or body.request[:60],
            request=body.request,
            response=body.response,
            analysis_id=body.analysis_id
        )
        
        return {
            "status": "success",
            "scenario": scenario.model_dump()
        }
    except Exception as e:
        logger.error(f"Error creating SEO scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@generate_router.get("/seo/scenarios/{scenario_id}")
async def get_seo_scenario_endpoint(
    scenario_id: str,
    user: AuthUserModel = Depends(get_current_user)
) -> dict:
    """
    Получить SEO сценарий по ID
    """
    try:
        scenario = await get_seo_scenario(scenario_id, user.user_id)
        
        if not scenario:
            raise HTTPException(status_code=404, detail="SEO scenario not found")
        
        return {
            "status": "success",
            "scenario": scenario.model_dump()
        }
    except Exception as e:
        logger.error(f"Error getting SEO scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@generate_router.get("/seo/scenarios")
async def list_seo_scenarios_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: Optional[str] = Query(None),
    analysis_id: Optional[str] = Query(None),
    user: AuthUserModel = Depends(get_current_user)
) -> dict:
    """
    Получить список SEO сценариев пользователя
    
    Query params:
    - limit: количество результатов (1-100, по умол 50)
    - offset: смещение (по умол 0)
    - type: фильтр по типу (video/shorts, опционально)
    - analysis_id: фильтр по проекту (опционально)
    """
    try:
        total, scenarios = await list_seo_scenarios(
            user_id=user.user_id,
            limit=limit,
            offset=offset,
            scenario_type=type,
            analysis_id=analysis_id
        )
        
        return {
            "status": "success",
            "total": total,
            "limit": limit,
            "offset": offset,
            "scenarios": [s.model_dump() for s in scenarios]
        }
    except Exception as e:
        logger.error(f"Error listing SEO scenarios: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@generate_router.delete("/seo/scenarios/{scenario_id}")
async def delete_seo_scenario_endpoint(
    scenario_id: str,
    user: AuthUserModel = Depends(get_current_user)
) -> dict:
    """
    Удалить SEO сценарий
    """
    try:
        success = await delete_seo_scenario(scenario_id, user.user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="SEO scenario not found")
        
        return {
            "status": "success",
            "message": "SEO scenario deleted"
        }
    except Exception as e:
        logger.error(f"Error deleting SEO scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ SEO ГЕНЕРАЦИЯ (НОВЫЕ ENDPOINTS) ============

@generate_router.post("/seo/video")
async def generate_seo_video_endpoint(
    request: str = Body(embed=True),
    analysis_id: Optional[str] = Body(None, embed=True),
    user: AuthUserModel = Depends(get_current_user)
) -> dict:
    """
    Начать генерацию SEO рекомендаций для видео.
    Возвращает task_id для поллинга статуса.
    """
    from generate.tasks_seo import generate_seo_scenario
    
    try:
        if not request:
            raise HTTPException(status_code=400, detail="Request text is required")
        
        # Проверяем подписку и кредиты (если нужно)
        # await check_user_subscription(user.user_id)
        
        # Запускаем задачу в очередь
        task = generate_seo_scenario.apply_async(
            args=(user.user_id, request, "video", analysis_id),
            queue="seo_scenarios"
        )
        
        logger.info(f"[seo-endpoint] Queued task {task.id} for user {user.user_id}")
        
        return {
            "status": "queued",
            "task_id": task.id
        }
    except Exception as e:
        logger.error(f"Error queuing SEO video generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@generate_router.post("/seo/shorts")
async def generate_seo_shorts_endpoint(
    request: str = Body(embed=True),
    analysis_id: Optional[str] = Body(None, embed=True),
    user: AuthUserModel = Depends(get_current_user)
) -> dict:
    """
    Начать генерацию SEO рекомендаций для Shorts.
    Возвращает task_id для поллинга статуса.
    """
    from generate.tasks_seo import generate_seo_scenario
    
    try:
        if not request:
            raise HTTPException(status_code=400, detail="Request text is required")
        
        # Запускаем задачу в очередь
        task = generate_seo_scenario.apply_async(
            args=(user.user_id, request, "shorts", analysis_id),
            queue="seo_scenarios"
        )
        
        logger.info(f"[seo-endpoint] Queued task {task.id} for user {user.user_id}")
        
        return {
            "status": "queued",
            "task_id": task.id
        }
    except Exception as e:
        logger.error(f"Error queuing SEO shorts generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
