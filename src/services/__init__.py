"""
ITIL-NEXT Engine Services

Core business logic for ticket management.
DNA from: HubSpot + Amdocs + Sony + SolarWinds
"""

from .ownership import OwnershipService, OwnershipGuard, OwnershipError
from .envelope import EnvelopeService, EnvelopeError
from .alert import AlertService, PriorityAlertConfig, AlertLevel, AlertRule
from .timeline import TimelineService
from .priority import PriorityService
from .resolution import ResolutionService

__all__ = [
    # Ownership (THE CORE INNOVATION)
    "OwnershipService", "OwnershipGuard", "OwnershipError",
    
    # Envelopes (Amdocs sub-case)
    "EnvelopeService", "EnvelopeError", 
    
    # Alerts (SolarWinds escalation matrix)
    "AlertService", "PriorityAlertConfig", "AlertLevel", "AlertRule",
    
    # Timeline (HubSpot engagements)
    "TimelineService",
    
    # Priority scoring
    "PriorityService",
    
    # Resolution tracking (Sony empowerment)
    "ResolutionService",
]
