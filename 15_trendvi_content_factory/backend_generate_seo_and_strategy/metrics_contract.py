from typing import Dict, Any

METRICS_SCHEMA_VERSION = "2026-02-24.v1"


def get_metrics_contract() -> Dict[str, Any]:
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "score_formula": {
            "name": "strategy_score",
            "range": "0-100",
            "components": [
                {
                    "key": "trend",
                    "label": "Trend Potential",
                    "description": "Short-term momentum based on relative views and comments",
                },
                {
                    "key": "evergreen",
                    "label": "Evergreen Potential",
                    "description": "Sustainable relevance proxy from engagement quality",
                },
                {
                    "key": "subscriber",
                    "label": "Subscriber Impact",
                    "description": "Proxy of subscription-driving potential",
                },
                {
                    "key": "niche",
                    "label": "Underserved Demand",
                    "description": "Gap between observed supply and desired content mix",
                },
            ],
            "modes": {
                "trend": {"trend": 0.50, "evergreen": 0.20, "subscriber": 0.20, "niche": 0.10},
                "evergreen": {"trend": 0.20, "evergreen": 0.50, "subscriber": 0.20, "niche": 0.10},
                "niche": {"trend": 0.20, "evergreen": 0.20, "subscriber": 0.20, "niche": 0.40},
            },
        },
        "derived_metrics": {
            "readiness": "Composite readiness score of strategy stack and freshness",
            "long_tail_coverage": "Share of videos persisting in long period buckets",
            "long_tail_strength": "Relative strength proxy of persistent videos",
            "classifier_confidence": "Average confidence of content type labels",
        },
        "statuses": {
            "allowed_values": ["ready", "pending", "stale"],
            "keys": ["strategy_status", "demand_status", "classifier_status", "freshness_status"],
        },
    }
