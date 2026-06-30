"""CRUD операции для SEO сценариев"""
from typing import List, Optional, Tuple
from .models import SeoScenarioModel
from db import db_connect
from uuid import UUID, uuid4
import logging

logger = logging.getLogger(__name__)


async def add_seo_scenario(
    user_id: int,
    scenario_type: str,
    title: str,
    request: str,
    response: str,
    analysis_id: Optional[str] = None
) -> SeoScenarioModel:
    """Добавить новый SEO сценарий"""
    conn = await db_connect()
    try:
        scenario_id = str(uuid4())
        
        result = await conn.fetchrow("""
            INSERT INTO seo_scenarios 
            (scenario_id, user_id, analysis_id, type, title, request, response)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING scenario_id, user_id, analysis_id, type, title, request, response, created_at, updated_at
        """, scenario_id, user_id, analysis_id, scenario_type, title, request, response)
        
        logger.info(f"[SEO-CRUD] Added SEO scenario {scenario_id} for user {user_id}")
        return SeoScenarioModel(**result)
    finally:
        await conn.close()


async def get_seo_scenario(scenario_id: str, user_id: int) -> Optional[SeoScenarioModel]:
    """Получить SEO сценарий по ID"""
    conn = await db_connect()
    try:
        result = await conn.fetchrow("""
            SELECT * FROM seo_scenarios
            WHERE scenario_id = $1 AND user_id = $2
        """, scenario_id, user_id)
        
        if result:
            return SeoScenarioModel(**result)
        return None
    finally:
        await conn.close()


async def list_seo_scenarios(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    scenario_type: Optional[str] = None,
    analysis_id: Optional[str] = None
) -> Tuple[int, List[SeoScenarioModel]]:
    """Получить список SEO сценариев пользователя"""
    conn = await db_connect()
    try:
        # Строим условия фильтрации
        where_clauses = ["user_id = $1"]
        params = [user_id]
        param_idx = 2
        
        if scenario_type:
            where_clauses.append(f"type = ${param_idx}")
            params.append(scenario_type)
            param_idx += 1
        
        if analysis_id:
            where_clauses.append(f"analysis_id = ${param_idx}")
            params.append(analysis_id)
            param_idx += 1
        
        where_sql = " AND ".join(where_clauses)
        
        # Считаем общее количество
        count_result = await conn.fetchval(f"""
            SELECT COUNT(*) FROM seo_scenarios
            WHERE {where_sql}
        """, *params)
        
        # Добавляем limit и offset
        params.append(limit)
        params.append(offset)
        
        # Получаем сценарии
        results = await conn.fetch(f"""
            SELECT * FROM seo_scenarios
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """, *params)
        
        scenarios = [SeoScenarioModel(**row) for row in results]
        return count_result or 0, scenarios
    finally:
        await conn.close()


async def update_seo_scenario(
    scenario_id: str,
    user_id: int,
    **updates
) -> Optional[SeoScenarioModel]:
    """Обновить SEO сценарий"""
    conn = await db_connect()
    try:
        # Строим динамический UPDATE запрос
        allowed_fields = {'title', 'request', 'response', 'type', 'analysis_id'}
        update_parts = []
        params = []
        param_idx = 1
        
        for key, value in updates.items():
            if key in allowed_fields:
                update_parts.append(f"{key} = ${param_idx}")
                params.append(value)
                param_idx += 1
        
        if not update_parts:
            return await get_seo_scenario(scenario_id, user_id)
        
        params.extend([scenario_id, user_id])
        
        result = await conn.fetchrow(f"""
            UPDATE seo_scenarios
            SET {', '.join(update_parts)}
            WHERE scenario_id = ${param_idx} AND user_id = ${param_idx + 1}
            RETURNING scenario_id, user_id, analysis_id, type, title, request, response, created_at, updated_at
        """, *params)
        
        if result:
            logger.info(f"[SEO-CRUD] Updated SEO scenario {scenario_id}")
            return SeoScenarioModel(**result)
        return None
    finally:
        await conn.close()


async def delete_seo_scenario(scenario_id: str, user_id: int) -> bool:
    """Удалить SEO сценарий"""
    conn = await db_connect()
    try:
        result = await conn.execute("""
            DELETE FROM seo_scenarios
            WHERE scenario_id = $1 AND user_id = $2
        """, scenario_id, user_id)
        
        deleted = result == "DELETE 1"
        if deleted:
            logger.info(f"[SEO-CRUD] Deleted SEO scenario {scenario_id}")
        return deleted
    finally:
        await conn.close()
