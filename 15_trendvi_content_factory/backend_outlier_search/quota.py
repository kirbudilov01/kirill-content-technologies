import logging
from datetime import datetime, timedelta

import redis

logger = logging.getLogger(__name__)


class OutlierQuotaTracker:
    def __init__(
        self,
        redis_url: str = "redis://:trendvi@redis:6379/0",
        max_searches_per_week: int = 15,
    ):
        if "?" not in redis_url:
            redis_url += "?socket_keepalive=0"
        self.redis_client = redis.from_url(redis_url, decode_responses=True, socket_keepalive=False)
        self.max_searches_per_week = int(max_searches_per_week or 15)

    def _get_key(self, user_id: str) -> str:
        return f"outlier_search_quota:{user_id}"

    def get_remaining_searches(self, user_id: str) -> int:
        key = self._get_key(user_id)
        try:
            used = self.redis_client.get(key)
            if used is None:
                return self.max_searches_per_week
            remaining = self.max_searches_per_week - int(used)
            return max(0, remaining)
        except Exception as e:
            logger.error("[OutlierQuota] get_remaining_searches failed: %s", e)
            return self.max_searches_per_week

    def can_search(self, user_id: str) -> bool:
        return self.get_remaining_searches(user_id) > 0

    def increment_search_count(self, user_id: str) -> int:
        key = self._get_key(user_id)
        try:
            new_count = self.redis_client.incr(key)
            if new_count == 1:
                self.redis_client.expire(key, 7 * 24 * 60 * 60)
            return new_count
        except Exception as e:
            logger.error("[OutlierQuota] increment_search_count failed: %s", e)
            return 0

    def get_quota_info(self, user_id: str) -> dict:
        key = self._get_key(user_id)
        try:
            used = int(self.redis_client.get(key) or 0)
            remaining = max(0, self.max_searches_per_week - used)
            ttl = self.redis_client.ttl(key)
            if ttl > 0:
                reset_date = datetime.utcnow() + timedelta(seconds=ttl)
            else:
                reset_date = datetime.utcnow() + timedelta(days=7)

            return {
                "searches_used": used,
                "searches_remaining": remaining,
                "searches_limit": self.max_searches_per_week,
                "reset_date": reset_date.isoformat() + "Z",
            }
        except Exception as e:
            logger.error("[OutlierQuota] get_quota_info failed: %s", e)
            return {
                "searches_used": 0,
                "searches_remaining": self.max_searches_per_week,
                "searches_limit": self.max_searches_per_week,
                "reset_date": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
            }
