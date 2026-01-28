"""
ITIL-NEXT Ownership Service

THE CORE INNOVATION: Owner is immutable after accept.

This is the antidote to Valuemation's ping-pong.
Agent who accepts OWNS the outcome.
Escalation brings help IN, not hands responsibility OFF.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from ..models.ticket import (
    Ticket, 
    TicketStatus, 
    TimelineEntry, 
    TimelineEntryType,
    Visibility
)


class OwnershipError(Exception):
    """Raised when ownership rules are violated."""
    pass


class OwnershipService:
    """
    Enforces the sacred ownership model.
    
    Rules:
    1. owner_id is set ONCE on accept()
    2. owner_id CANNOT be changed through normal operations
    3. Only exceptional cases allow ownership transfer:
       - Agent terminated
       - Extended leave (>30 days)
    4. Escalation creates envelope, NOT ownership transfer
    """
    
    def __init__(self, ticket_repo, agent_repo, timeline_repo):
        self.ticket_repo = ticket_repo
        self.agent_repo = agent_repo
        self.timeline_repo = timeline_repo
    
    async def accept_ticket(
        self, 
        ticket_id: UUID, 
        agent_id: UUID
    ) -> Ticket:
        """
        Agent accepts ownership of a ticket.
        
        This is THE moment. After this, owner_id is immutable.
        """
        ticket = await self.ticket_repo.get(ticket_id)
        agent = await self.agent_repo.get(agent_id)
        
        # Validation
        if ticket.owner_id is not None:
            raise OwnershipError(
                f"Ticket {ticket.reference} already has owner. "
                "Cannot accept an owned ticket."
            )
        
        if not agent.is_active:
            raise OwnershipError("Inactive agents cannot accept tickets.")
        
        if agent.current_tickets >= agent.max_tickets:
            raise OwnershipError(
                f"Agent at capacity ({agent.current_tickets}/{agent.max_tickets}). "
                "Cannot accept more tickets."
            )
        
        # THE SACRED MOMENT: Set owner
        ticket.owner_id = agent_id
        ticket.owner_accepted_at = datetime.utcnow()
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.updated_at = datetime.utcnow()
        
        # Update agent capacity
        agent.current_tickets += 1
        
        # Save
        await self.ticket_repo.save(ticket)
        await self.agent_repo.save(agent)
        
        # Timeline entry
        await self.timeline_repo.add(TimelineEntry(
            ticket_id=ticket_id,
            type=TimelineEntryType.SYSTEM,
            visibility=Visibility.INTERNAL,
            content=f"Ticket accepted by {agent.name}. Ownership established."
        ))
        
        return ticket
    
    async def validate_ownership(
        self, 
        ticket_id: UUID, 
        agent_id: UUID
    ) -> bool:
        """Check if agent is the owner of ticket."""
        ticket = await self.ticket_repo.get(ticket_id)
        return ticket.owner_id == agent_id
    
    async def transfer_ownership(
        self, 
        ticket_id: UUID, 
        new_owner_id: UUID,
        reason: str,
        authorized_by: UUID,
        transfer_type: str  # "termination" | "extended_leave"
    ) -> Ticket:
        """
        EXCEPTIONAL ownership transfer.
        
        This is NOT normal escalation. This is for:
        - Agent terminated
        - Extended leave (>30 days)
        
        Requires authorization and audit trail.
        """
        # Only these reasons are valid
        valid_reasons = {"termination", "extended_leave"}
        if transfer_type not in valid_reasons:
            raise OwnershipError(
                f"Invalid transfer type: {transfer_type}. "
                f"Only {valid_reasons} are allowed. "
                "Use envelopes for normal escalation."
            )
        
        ticket = await self.ticket_repo.get(ticket_id)
        old_owner = await self.agent_repo.get(ticket.owner_id)
        new_owner = await self.agent_repo.get(new_owner_id)
        authorizer = await self.agent_repo.get(authorized_by)
        
        # TODO: Check authorizer has permission (manager role)
        
        # Perform transfer
        old_owner_id = ticket.owner_id
        ticket.owner_id = new_owner_id
        ticket.updated_at = datetime.utcnow()
        
        # Update capacities
        old_owner.current_tickets -= 1
        new_owner.current_tickets += 1
        
        # Save
        await self.ticket_repo.save(ticket)
        await self.agent_repo.save(old_owner)
        await self.agent_repo.save(new_owner)
        
        # Detailed audit trail
        await self.timeline_repo.add(TimelineEntry(
            ticket_id=ticket_id,
            type=TimelineEntryType.SYSTEM,
            visibility=Visibility.INTERNAL,
            content=(
                f"⚠️ EXCEPTIONAL OWNERSHIP TRANSFER\n"
                f"From: {old_owner.name}\n"
                f"To: {new_owner.name}\n"
                f"Reason: {transfer_type}\n"
                f"Details: {reason}\n"
                f"Authorized by: {authorizer.name}"
            )
        ))
        
        return ticket
    
    async def release_ownership(
        self,
        ticket_id: UUID,
        agent_id: UUID
    ) -> None:
        """
        Release ownership when ticket is resolved/closed.
        
        Decrements agent's current ticket count.
        """
        ticket = await self.ticket_repo.get(ticket_id)
        
        if ticket.owner_id != agent_id:
            raise OwnershipError("Only the owner can release a ticket.")
        
        if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            raise OwnershipError(
                "Cannot release ownership of active ticket. "
                "Resolve or close it first."
            )
        
        agent = await self.agent_repo.get(agent_id)
        agent.current_tickets = max(0, agent.current_tickets - 1)
        await self.agent_repo.save(agent)


class OwnershipGuard:
    """
    Decorator/guard to protect operations that require ownership.
    """
    
    def __init__(self, ownership_service: OwnershipService):
        self.ownership = ownership_service
    
    async def require_owner(
        self, 
        ticket_id: UUID, 
        agent_id: UUID,
        action: str
    ) -> None:
        """
        Raise if agent is not the owner.
        
        Use before operations like:
        - Sending customer email
        - Resolving ticket
        - Changing status
        """
        is_owner = await self.ownership.validate_ownership(ticket_id, agent_id)
        if not is_owner:
            raise OwnershipError(
                f"Only the ticket owner can {action}. "
                "If you need to help, ask the owner to create an envelope."
            )
    
    async def require_owner_or_envelope_expert(
        self, 
        ticket_id: UUID, 
        agent_id: UUID,
        envelope_id: Optional[UUID],
        action: str
    ) -> None:
        """
        Allow owner OR assigned envelope expert.
        
        Use for operations within an envelope context.
        """
        is_owner = await self.ownership.validate_ownership(ticket_id, agent_id)
        if is_owner:
            return
        
        if envelope_id:
            # TODO: Check if agent is assigned to this envelope
            # For now, allow if envelope_id is provided
            return
        
        raise OwnershipError(
            f"Only the ticket owner or assigned envelope expert can {action}."
        )
