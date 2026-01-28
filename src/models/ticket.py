"""
ITIL-NEXT Ticket Model

HubSpot DNA + Amdocs Envelope + Sony Empowerment

Core principles:
1. Ticket = Customer request for help (HubSpot)
2. Owner is IMMUTABLE after accept (our innovation)
3. Envelopes = Parallel assist (Amdocs sub-case)
4. Timeline = Activity feed (HubSpot engagements)
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class TicketType(str, Enum):
    INCIDENT = "incident"
    REQUEST = "request"
    CHANGE = "change"
    PROBLEM = "problem"


class TicketStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    WAITING_INTERNAL = "waiting_internal"  # Waiting on envelope
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    CRITICAL = "critical"  # Base score: 100
    HIGH = "high"          # Base score: 70
    MEDIUM = "medium"      # Base score: 40
    LOW = "low"            # Base score: 10


class EnvelopeStatus(str, Enum):
    PENDING = "pending"    # Waiting for expert to accept
    ACTIVE = "active"      # Expert working on it
    COMPLETED = "completed"  # Expert finished, back to owner


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TimelineEntryType(str, Enum):
    EMAIL_INBOUND = "email_inbound"
    EMAIL_OUTBOUND = "email_outbound"
    NOTE = "note"
    SYSTEM = "system"
    ENVELOPE_CREATED = "envelope_created"
    ENVELOPE_COMPLETED = "envelope_completed"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    STATUS_CHANGE = "status_change"
    RESOLUTION = "resolution"


class Visibility(str, Enum):
    PUBLIC = "public"           # Customer can see
    INTERNAL = "internal"       # Agents only
    ENVELOPE_ONLY = "envelope_only"  # Owner + envelope experts only


class CaseFlagType(str, Enum):
    PHYSICAL_DAMAGE = "physical_damage"
    SOCIAL_MEDIA = "social_media"
    VIP = "vip"
    LEGAL = "legal"
    REPEAT_CONTACT = "repeat_contact"


class EmpowermentTier(str, Enum):
    AGENT = "agent"           # Self-service up to limit
    TEAM_LEAD = "team_lead"   # Needs TL approval
    MANAGER = "manager"       # Needs manager + calibration


class ResolutionType(str, Enum):
    REFUND = "refund"
    CREDIT = "credit"
    REPLACEMENT = "replacement"
    REPAIR = "repair"
    INFORMATION = "information"
    WORKAROUND = "workaround"
    NO_ACTION = "no_action"


# =============================================================================
# CORE MODELS
# =============================================================================

class Ticket(BaseModel):
    """
    The core ticket entity.
    
    HubSpot pattern: Object with properties + associations
    Our addition: Immutable owner_id after accept
    """
    id: UUID = Field(default_factory=uuid4)
    reference: str = Field(..., description="Human-readable ID, e.g. INC-2024-001234")
    
    # Core properties (HubSpot style)
    subject: str
    description: Optional[str] = None
    type: TicketType = TicketType.INCIDENT
    status: TicketStatus = TicketStatus.NEW
    priority: Priority = Priority.MEDIUM
    
    # Pipeline (HubSpot concept)
    pipeline_id: Optional[UUID] = None
    pipeline_stage_id: Optional[UUID] = None
    
    # Ownership (OUR CORE INNOVATION - immutable after accept)
    owner_id: Optional[UUID] = None  # Set on accept(), then IMMUTABLE
    owner_accepted_at: Optional[datetime] = None
    
    # Associations (HubSpot pattern)
    requester_id: UUID  # Contact who raised the ticket
    company_id: Optional[UUID] = None
    
    # SLA
    sla_id: Optional[UUID] = None
    sla_breach_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # External references
    msgraph_conversation_id: Optional[str] = None  # MS Graph email thread
    hubspot_id: Optional[str] = None
    
    # Computed (not stored, calculated on read)
    priority_score: Optional[float] = None
    has_active_envelopes: bool = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class Envelope(BaseModel):
    """
    Parallel assist envelope (Amdocs "sub-case").
    
    Owner creates envelope to get help.
    Expert works in envelope.
    Owner remains owner of ticket.
    
    Sony UI: Experts see as tabs in their view.
    """
    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    
    # Who created and who's working
    requested_by: UUID  # The ticket owner
    assigned_to: Optional[UUID] = None  # Specific expert
    team_id: Optional[UUID] = None  # Or team (first to accept)
    
    # Status
    status: EnvelopeStatus = EnvelopeStatus.PENDING
    
    # Context
    reason: str  # Why help is needed
    summary: Optional[str] = None  # Filled when completed
    
    # Timestamps  
    created_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # SLA for envelope response
    response_due_at: Optional[datetime] = None


class Task(BaseModel):
    """
    Smaller work item (Amdocs pattern).
    
    Can be standalone on ticket or under an envelope.
    Examples: Order part, get approval, schedule callback.
    """
    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    envelope_id: Optional[UUID] = None  # If under an envelope
    
    title: str
    description: Optional[str] = None
    
    assigned_to: Optional[UUID] = None
    status: TaskStatus = TaskStatus.TODO
    
    due_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class TimelineEntry(BaseModel):
    """
    Activity on a ticket (HubSpot "engagement").
    
    Forms the timeline/activity feed.
    Scoped by envelope_id for envelope-specific entries.
    """
    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    envelope_id: Optional[UUID] = None  # Null = main timeline
    
    type: TimelineEntryType
    visibility: Visibility = Visibility.INTERNAL
    
    # Author
    author_id: Optional[UUID] = None  # Agent, or None for system
    author_type: str = "agent"  # agent, system, customer
    
    # Content
    subject: Optional[str] = None
    content: str
    content_html: Optional[str] = None
    
    # For emails
    email_message_id: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[List[str]] = None
    
    # Attachments
    attachment_ids: Optional[List[UUID]] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CaseFlag(BaseModel):
    """
    Special handling markers (Sony pattern).
    
    Flags trigger special workflows:
    - social_media: Priority boost, manager visibility
    - legal: Auto-create legal envelope
    - repeat_contact: Escalation suggested
    """
    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    
    type: CaseFlagType
    reason: str
    
    added_by: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Some flags auto-clear
    cleared_at: Optional[datetime] = None
    cleared_by: Optional[UUID] = None


class Resolution(BaseModel):
    """
    Compensation/resolution record (Sony pattern).
    
    What/Why/When/Where documentation for calibration.
    """
    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    
    # Who resolved
    agent_id: UUID
    
    # What/Why documentation
    what_went_wrong: str
    what_went_wrong_category: Optional[str] = None
    why_eligible: str
    why_eligible_category: Optional[str] = None
    
    # Resolution details
    resolution_type: ResolutionType
    resolution_details: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "EUR"
    
    # Empowerment tracking
    empowerment_tier: EmpowermentTier
    approved_by: Optional[UUID] = None  # If tier > agent
    approved_at: Optional[datetime] = None
    
    # Calibration
    calibration_status: str = "pending"  # pending, reviewed, upheld, revised
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# SUPPORTING MODELS
# =============================================================================

class Contact(BaseModel):
    """Customer/requester (HubSpot Contact)."""
    id: UUID = Field(default_factory=uuid4)
    
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    
    company_id: Optional[UUID] = None
    tier: str = "standard"  # standard, premium, vip
    
    # External
    hubspot_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.email


class Company(BaseModel):
    """Customer organization (HubSpot Company)."""
    id: UUID = Field(default_factory=uuid4)
    
    name: str
    domain: Optional[str] = None
    
    tier: str = "standard"  # standard, premium, vip
    sla_id: Optional[UUID] = None  # Default SLA for this company
    
    # External
    hubspot_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Agent(BaseModel):
    """Support agent."""
    id: UUID = Field(default_factory=uuid4)
    
    email: str
    name: str
    
    team_ids: List[UUID] = Field(default_factory=list)
    skill_ids: List[UUID] = Field(default_factory=list)
    
    # Capacity
    max_tickets: int = 25
    current_tickets: int = 0
    
    # Empowerment
    empowerment_limit: float = 100.0  # EUR, agent discretion limit
    
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Team(BaseModel):
    """Agent team/group."""
    id: UUID = Field(default_factory=uuid4)
    
    name: str
    description: Optional[str] = None
    
    # Empowerment config
    tier1_limit: float = 100.0   # Agent discretion
    tier2_limit: float = 500.0   # Team lead approval
    # Above tier2 = manager/calibration
    
    # Notification channel
    teams_channel_webhook: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
