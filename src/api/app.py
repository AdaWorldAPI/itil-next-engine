"""
ITIL-NEXT API

FastAPI application with:
- Ticket CRUD with ownership protection
- Envelope management
- Resolution with empowerment
- Priority-based work queues
- Timeline access
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from .models import (
    Ticket, 
    TicketType, 
    TicketStatus, 
    Priority,
    Envelope,
    TimelineEntry,
    Resolution,
    ResolutionType
)

# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="ITIL-NEXT Engine",
    description="Ticket system with sacred ownership and parallel escalation",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateTicketRequest(BaseModel):
    subject: str
    description: Optional[str] = None
    type: TicketType = TicketType.INCIDENT
    priority: Priority = Priority.MEDIUM
    requester_id: UUID
    company_id: Optional[UUID] = None


class AcceptTicketRequest(BaseModel):
    agent_id: UUID


class CreateEnvelopeRequest(BaseModel):
    reason: str
    team_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    response_hours: int = 4


class AddNoteRequest(BaseModel):
    content: str
    visibility: str = "internal"  # public, internal, envelope_only
    envelope_id: Optional[UUID] = None


class CreateResolutionRequest(BaseModel):
    what_went_wrong: str
    what_went_wrong_category: Optional[str] = None
    why_eligible: str
    why_eligible_category: Optional[str] = None
    resolution_type: ResolutionType
    resolution_details: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "EUR"


class CompleteEnvelopeRequest(BaseModel):
    summary: str


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "itil-next-engine",
        "version": "0.1.0"
    }


# =============================================================================
# TICKET ENDPOINTS
# =============================================================================

@app.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(request: CreateTicketRequest):
    """
    Create a new ticket.
    
    Ticket starts with no owner. An agent must accept() to own it.
    """
    # TODO: Inject ticket service
    # ticket = await ticket_service.create(request)
    return {
        "message": "Ticket created",
        "reference": "INC-2024-000001",  # TODO: Generate
        "status": "new"
    }


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: UUID):
    """
    Get ticket details.
    """
    # TODO: Inject ticket service
    return {"id": ticket_id, "message": "TODO: Implement"}


@app.post("/tickets/{ticket_id}/accept")
async def accept_ticket(ticket_id: UUID, request: AcceptTicketRequest):
    """
    Accept ownership of a ticket.
    
    THIS IS THE SACRED MOMENT.
    After this, owner_id is IMMUTABLE.
    """
    # TODO: Inject ownership service
    # ticket = await ownership_service.accept_ticket(ticket_id, request.agent_id)
    return {
        "message": "Ticket accepted",
        "ticket_id": ticket_id,
        "owner_id": request.agent_id,
        "warning": "Ownership is now immutable. You own this outcome."
    }


@app.get("/tickets/{ticket_id}/timeline")
async def get_timeline(
    ticket_id: UUID,
    viewer_id: Optional[UUID] = None,
    include_envelopes: bool = True
):
    """
    Get ticket timeline (activity feed).
    
    HubSpot-style engagement list.
    """
    # TODO: Inject timeline service
    return {"ticket_id": ticket_id, "entries": []}


@app.post("/tickets/{ticket_id}/notes")
async def add_note(ticket_id: UUID, request: AddNoteRequest):
    """
    Add a note to the ticket timeline.
    """
    # TODO: Inject timeline service
    return {"message": "Note added", "ticket_id": ticket_id}


# =============================================================================
# ENVELOPE ENDPOINTS
# =============================================================================

@app.post("/tickets/{ticket_id}/envelopes", status_code=status.HTTP_201_CREATED)
async def create_envelope(
    ticket_id: UUID, 
    request: CreateEnvelopeRequest,
    agent_id: UUID  # From auth
):
    """
    Create an envelope (parallel assist request).
    
    This is the 1-CLICK replacement for Valuemation's 15-20 clicks.
    
    Owner creates envelope → Expert works → Owner closes
    Customer sees: One agent handling their issue
    Reality: Multiple experts contributed
    """
    # TODO: Inject envelope service
    return {
        "message": "Envelope created",
        "ticket_id": ticket_id,
        "target": request.team_id or request.assigned_to
    }


@app.post("/envelopes/{envelope_id}/accept")
async def accept_envelope(envelope_id: UUID, agent_id: UUID):
    """
    Accept an envelope assignment.
    """
    # TODO: Inject envelope service
    return {"message": "Envelope accepted", "envelope_id": envelope_id}


@app.post("/envelopes/{envelope_id}/notes")
async def add_envelope_note(envelope_id: UUID, request: AddNoteRequest, agent_id: UUID):
    """
    Add a note to envelope thread.
    
    Only owner and assigned expert can see/add to envelope thread.
    """
    # TODO: Inject envelope service
    return {"message": "Note added to envelope", "envelope_id": envelope_id}


@app.post("/envelopes/{envelope_id}/complete")
async def complete_envelope(
    envelope_id: UUID, 
    request: CompleteEnvelopeRequest,
    agent_id: UUID
):
    """
    Complete an envelope.
    
    Summary is posted to main timeline.
    """
    # TODO: Inject envelope service
    return {
        "message": "Envelope completed",
        "envelope_id": envelope_id,
        "summary_posted": True
    }


@app.get("/agents/{agent_id}/envelopes")
async def get_agent_envelopes(agent_id: UUID, status: Optional[str] = None):
    """
    Get envelopes assigned to or available for an agent.
    
    Sony tab pattern: Expert sees their envelopes as tabs.
    """
    # TODO: Inject envelope service
    return {
        "agent_id": agent_id,
        "my_envelopes": [],
        "available_envelopes": []
    }


# =============================================================================
# RESOLUTION ENDPOINTS
# =============================================================================

@app.post("/tickets/{ticket_id}/resolutions", status_code=status.HTTP_201_CREATED)
async def create_resolution(
    ticket_id: UUID,
    request: CreateResolutionRequest,
    agent_id: UUID
):
    """
    Create a resolution with empowerment check.
    
    Sony pattern:
    - Tier 1 (Agent): Up to limit, just document
    - Tier 2 (Team Lead): Needs approval
    - Tier 3 (Manager): Needs approval + calibration
    """
    # TODO: Inject resolution service
    return {
        "message": "Resolution created",
        "ticket_id": ticket_id,
        "empowerment_tier": "agent",  # TODO: Calculate
        "requires_approval": False
    }


@app.get("/agents/{agent_id}/pending-approvals")
async def get_pending_approvals(agent_id: UUID):
    """
    Get resolutions awaiting this approver's review.
    
    For team leads and managers.
    """
    # TODO: Inject resolution service
    return {"agent_id": agent_id, "pending": []}


@app.post("/resolutions/{resolution_id}/approve")
async def approve_resolution(
    resolution_id: UUID,
    approved: bool,
    notes: Optional[str] = None,
    approver_id: UUID = None
):
    """
    Approve or reject a resolution.
    """
    # TODO: Inject resolution service
    return {
        "message": "approved" if approved else "rejected",
        "resolution_id": resolution_id
    }


# =============================================================================
# WORK QUEUE ENDPOINTS
# =============================================================================

@app.get("/agents/{agent_id}/work-queue")
async def get_work_queue(agent_id: UUID):
    """
    Get prioritized work queue for an agent.
    
    Sorted by dynamic priority score.
    Grouped: Needs Attention / Waiting / On Track
    """
    # TODO: Inject priority service
    return {
        "agent_id": agent_id,
        "needs_attention": [],
        "waiting_on_others": [],
        "on_track": [],
        "total": 0
    }


@app.get("/teams/{team_id}/queue")
async def get_team_queue(team_id: UUID):
    """
    Get prioritized queue for a team.
    
    For Kanban boards and team lead views.
    """
    # TODO: Inject priority service
    return {"team_id": team_id, "tickets": []}


# =============================================================================
# CALIBRATION ENDPOINTS
# =============================================================================

@app.get("/calibration/queue")
async def get_calibration_queue(
    week_start: Optional[datetime] = None,
    week_end: Optional[datetime] = None
):
    """
    Get calibration queue for the week.
    
    Sony pattern: Weekly review of edge cases.
    """
    # TODO: Inject calibration service
    return {"items": [], "total": 0}


@app.post("/calibration/{item_id}/review")
async def review_calibration_item(
    item_id: UUID,
    outcome: str,  # upheld, revised, coaching_needed
    notes: str,
    reviewer_id: UUID
):
    """
    Record calibration review outcome.
    """
    # TODO: Inject calibration service
    return {"message": "Review recorded", "item_id": item_id, "outcome": outcome}


@app.get("/calibration/report")
async def get_calibration_report(
    period_start: datetime,
    period_end: datetime
):
    """
    Generate calibration metrics report.
    """
    # TODO: Inject calibration service
    return {
        "period": {"start": period_start, "end": period_end},
        "uphold_rate": 0,
        "by_reason": {}
    }


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
