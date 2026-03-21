from backend.app.config import settings


def get_identity_threshold(risk_level: str, policy_override: float | None = None) -> float:
    """Return the identity similarity threshold for a given risk level."""
    if policy_override is not None:
        return policy_override
    defaults = {
        "low": 0.0,       # no ECG required
        "high": settings.identity_threshold,
        "critical": settings.identity_threshold + 0.1,
    }
    return defaults.get(risk_level, settings.identity_threshold)


def get_anomaly_threshold(risk_level: str, policy_override: float | None = None) -> float:
    """Return the anomaly score threshold for a given risk level."""
    if policy_override is not None:
        return policy_override
    defaults = {
        "low": 999.0,     # effectively disabled
        "high": settings.anomaly_threshold,
        "critical": settings.anomaly_threshold * 0.8,
    }
    return defaults.get(risk_level, settings.anomaly_threshold)
