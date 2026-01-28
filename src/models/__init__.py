"""
ITIL-NEXT Engine Models

HubSpot DNA + Amdocs Envelope + Sony Empowerment + SolarWinds Alerts
"""

from .ticket import (
    # Enums
    TicketType,
    TicketStatus,
    Priority,
    EnvelopeStatus,
    TaskStatus,
    TimelineEntryType,
    Visibility,
    CaseFlagType,
    EmpowermentTier,
    ResolutionType,
    
    # Core models
    Ticket,
    Envelope,
    Task,
    TimelineEntry,
    CaseFlag,
    Resolution,
    
    # Supporting models
    Contact,
    Company,
    Agent,
    Team,
)

__all__ = [
    "TicketType", "TicketStatus", "Priority", "EnvelopeStatus", "TaskStatus",
    "TimelineEntryType", "Visibility", "CaseFlagType", "EmpowermentTier", "ResolutionType",
    "Ticket", "Envelope", "Task", "TimelineEntry", "CaseFlag", "Resolution",
    "Contact", "Company", "Agent", "Team",
]
