"""
ITIL-NEXT Envelope Service

Amdocs "sub-case" pattern + Sony tab UI awareness.

Key insight: Escalation brings expertise IN, not hands responsibility OFF.

Owner creates envelope → Expert works in envelope → Owner closes envelope
Customer sees: One agent handling their issue
Reality: Multiple experts contributed via envelopes
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from ..models.ticket import (
    Ticket,
    Envelope,
    EnvelopeStatus,
    TicketStatus,
    TimelineEntry,
    TimelineEntryType,
    Visibility
)


class EnvelopeError(Exception):
    """Raised when envelope operations fail."""
    pass


class EnvelopeService:
    """
    Manages parallel assist envelopes.
    
    Terminology:
    - Ticket Owner: Agent who accepted the ticket (immutable)
    - Envelope: Request for expert help (Amdocs "sub-case")
    - Expert: Agent assigned to help via envelope
    
    UI Pattern (Sony):
    - Owner sees: Their ticket with envelope indicators
    - Expert sees: Tabs [Main Ticket (read)] [My Envelope (work)] [+ Add]
    - Expert can add 3rd level envelope from their view
    """
    
    # Default SLA for envelope response
    DEFAULT_RESPONSE_HOURS = 4
    
    def __init__(
        self, 
        envelope_repo,
        ticket_repo, 
        agent_repo, 
        team_repo,
        timeline_repo,
        notification_service
    ):
        self.envelope_repo = envelope_repo
        self.ticket_repo = ticket_repo
        self.agent_repo = agent_repo
        self.team_repo = team_repo
        self.timeline_repo = timeline_repo
        self.notifications = notification_service
    
    async def create_envelope(
        self,
        ticket_id: UUID,
        requested_by: UUID,
        reason: str,
        team_id: Optional[UUID] = None,
        assigned_to: Optional[UUID] = None,
        response_hours: int = DEFAULT_RESPONSE_HOURS
    ) -> Envelope:
        """
        Create an envelope (parallel assist request).
        
        This is the 1-CLICK action that replaces Valuemation's 15-20 clicks.
        
        Args:
            ticket_id: The ticket needing help
            requested_by: Usually the ticket owner
            reason: Why help is needed (shown to expert)
            team_id: Route to a team (first to accept)
            assigned_to: Or route to specific agent
            response_hours: SLA for expert to respond
        """
        ticket = await self.ticket_repo.get(ticket_id)
        requester = await self.agent_repo.get(requested_by)
        
        # Validation: Must be owner OR existing envelope expert
        if ticket.owner_id != requested_by:
            # Check if requester is an active envelope expert
            # (Allows 2nd level to create 3rd level envelope - Sony pattern)
            active_envelopes = await self.envelope_repo.get_active_for_ticket(ticket_id)
            expert_ids = [e.assigned_to for e in active_envelopes if e.assigned_to]
            
            if requested_by not in expert_ids:
                raise EnvelopeError(
                    "Only ticket owner or active envelope experts can create envelopes."
                )
        
        # Create envelope
        envelope = Envelope(
            ticket_id=ticket_id,
            requested_by=requested_by,
            team_id=team_id,
            assigned_to=assigned_to,
            reason=reason,
            status=EnvelopeStatus.PENDING,
            response_due_at=datetime.utcnow() + timedelta(hours=response_hours)
        )
        
        await self.envelope_repo.save(envelope)
        
        # Update ticket status
        ticket.status = TicketStatus.WAITING_INTERNAL
        ticket.has_active_envelopes = True
        ticket.updated_at = datetime.utcnow()
        await self.ticket_repo.save(ticket)
        
        # Timeline entry (visible to owner and future expert)
        target = "team" if team_id else "agent"
        target_name = await self._get_target_name(team_id, assigned_to)
        
        await self.timeline_repo.add(TimelineEntry(
            ticket_id=ticket_id,
            envelope_id=envelope.id,
            type=TimelineEntryType.ENVELOPE_CREATED,
            visibility=Visibility.ENVELOPE_ONLY,
            author_id=requested_by,
            content=f"📨 Envelope created for {target_name}\nReason: {reason}"
        ))
        
        # Notify team/agent
        await self._notify_envelope_created(envelope, ticket, requester)
        
        return envelope
    
    async def accept_envelope(
        self,
        envelope_id: UUID,
        agent_id: UUID
    ) -> Envelope:
        """
        Expert accepts an envelope.
        
        After this, the expert can work in the envelope.
        """
        envelope = await self.envelope_repo.get(envelope_id)
        agent = await self.agent_repo.get(agent_id)
        
        if envelope.status != EnvelopeStatus.PENDING:
            raise EnvelopeError(
                f"Envelope is {envelope.status}, cannot accept."
            )
        
        # If routed to team, anyone on team can accept
        if envelope.team_id:
            agent_teams = set(agent.team_ids)
            if envelope.team_id not in agent_teams:
                raise EnvelopeError(
                    "You are not a member of the team this envelope is assigned to."
                )
        # If routed to specific agent, only they can accept
        elif envelope.assigned_to and envelope.assigned_to != agent_id:
            raise EnvelopeError(
                "This envelope is assigned to another agent."
            )
        
        # Accept
        envelope.assigned_to = agent_id
        envelope.status = EnvelopeStatus.ACTIVE
        envelope.accepted_at = datetime.utcnow()
        
        await self.envelope_repo.save(envelope)
        
        # Timeline
        await self.timeline_repo.add(TimelineEntry(
            ticket_id=envelope.ticket_id,
            envelope_id=envelope_id,
            type=TimelineEntryType.SYSTEM,
            visibility=Visibility.ENVELOPE_ONLY,
            author_id=agent_id,
            content=f"✅ {agent.name} accepted the envelope"
        ))
        
        # Notify owner
        await self._notify_envelope_accepted(envelope, agent)
        
        return envelope
    
    async def add_envelope_note(
        self,
        envelope_id: UUID,
        agent_id: UUID,
        content: str,
        visibility: Visibility = Visibility.ENVELOPE_ONLY
    ) -> TimelineEntry:
        """
        Add a note to an envelope thread.
        
        Only owner and assigned expert can add notes.
        """
        envelope = await self.envelope_repo.get(envelope_id)
        ticket = await self.ticket_repo.get(envelope.ticket_id)
        
        # Validate: owner or assigned expert
        if agent_id not in [ticket.owner_id, envelope.assigned_to]:
            raise EnvelopeError(
                "Only ticket owner or assigned expert can add notes to envelope."
            )
        
        entry = TimelineEntry(
            ticket_id=envelope.ticket_id,
            envelope_id=envelope_id,
            type=TimelineEntryType.NOTE,
            visibility=visibility,
            author_id=agent_id,
            content=content
        )
        
        await self.timeline_repo.add(entry)
        
        # Notify the other party
        other_party = (
            envelope.assigned_to 
            if agent_id == ticket.owner_id 
            else ticket.owner_id
        )
        if other_party:
            await self.notifications.notify_envelope_update(
                envelope, agent_id, other_party
            )
        
        return entry
    
    async def complete_envelope(
        self,
        envelope_id: UUID,
        completed_by: UUID,
        summary: str
    ) -> Envelope:
        """
        Complete an envelope.
        
        Can be completed by owner (got what they needed) or expert (done helping).
        Summary is posted to main timeline.
        """
        envelope = await self.envelope_repo.get(envelope_id)
        ticket = await self.ticket_repo.get(envelope.ticket_id)
        agent = await self.agent_repo.get(completed_by)
        
        if envelope.status != EnvelopeStatus.ACTIVE:
            raise EnvelopeError(
                f"Envelope is {envelope.status}, cannot complete."
            )
        
        # Either owner or expert can complete
        if completed_by not in [ticket.owner_id, envelope.assigned_to]:
            raise EnvelopeError(
                "Only ticket owner or assigned expert can complete envelope."
            )
        
        envelope.status = EnvelopeStatus.COMPLETED
        envelope.completed_at = datetime.utcnow()
        envelope.summary = summary
        
        await self.envelope_repo.save(envelope)
        
        # Post summary to main timeline (owner can see full context)
        expert = await self.agent_repo.get(envelope.assigned_to)
        await self.timeline_repo.add(TimelineEntry(
            ticket_id=envelope.ticket_id,
            type=TimelineEntryType.ENVELOPE_COMPLETED,
            visibility=Visibility.INTERNAL,  # Main timeline, but internal
            author_id=completed_by,
            content=(
                f"📨 Envelope completed\n"
                f"Expert: {expert.name}\n"
                f"Summary: {summary}"
            )
        ))
        
        # Check if ticket should change status
        await self._update_ticket_envelope_status(envelope.ticket_id)
        
        # Notify
        await self._notify_envelope_completed(envelope, agent, summary)
        
        return envelope
    
    async def get_expert_view(
        self,
        agent_id: UUID,
        ticket_id: UUID
    ) -> dict:
        """
        Get the expert's view of a ticket (Sony tab pattern).
        
        Returns:
        - Main ticket (read-only context)
        - Their envelope(s)
        - Option to add next-level envelope
        """
        ticket = await self.ticket_repo.get(ticket_id)
        all_envelopes = await self.envelope_repo.get_for_ticket(ticket_id)
        
        # Find envelopes where this agent is involved
        my_envelopes = [
            e for e in all_envelopes 
            if e.assigned_to == agent_id
        ]
        
        # Pending envelopes for their teams
        agent = await self.agent_repo.get(agent_id)
        available_envelopes = [
            e for e in all_envelopes
            if e.status == EnvelopeStatus.PENDING
            and e.team_id in agent.team_ids
            and e.assigned_to is None
        ]
        
        return {
            "ticket": ticket,  # Read-only context
            "my_envelopes": my_envelopes,
            "available_envelopes": available_envelopes,
            "can_add_envelope": len(my_envelopes) > 0,  # Active experts can add
            "is_owner": ticket.owner_id == agent_id
        }
    
    async def get_owner_view(
        self,
        owner_id: UUID,
        ticket_id: UUID
    ) -> dict:
        """
        Get the owner's view of envelopes on their ticket.
        
        Returns envelope status indicators (not full content).
        """
        ticket = await self.ticket_repo.get(ticket_id)
        
        if ticket.owner_id != owner_id:
            raise EnvelopeError("Access denied: not ticket owner")
        
        envelopes = await self.envelope_repo.get_for_ticket(ticket_id)
        
        return {
            "ticket": ticket,
            "envelopes": [
                {
                    "id": e.id,
                    "status": e.status,
                    "team_or_agent": await self._get_target_name(e.team_id, e.assigned_to),
                    "reason": e.reason,
                    "response_due_at": e.response_due_at,
                    "summary": e.summary if e.status == EnvelopeStatus.COMPLETED else None
                }
                for e in envelopes
            ]
        }
    
    # =========================================================================
    # Private helpers
    # =========================================================================
    
    async def _get_target_name(
        self, 
        team_id: Optional[UUID], 
        agent_id: Optional[UUID]
    ) -> str:
        if agent_id:
            agent = await self.agent_repo.get(agent_id)
            return agent.name
        elif team_id:
            team = await self.team_repo.get(team_id)
            return f"Team: {team.name}"
        return "Unassigned"
    
    async def _update_ticket_envelope_status(self, ticket_id: UUID) -> None:
        """Update ticket's envelope status indicator."""
        envelopes = await self.envelope_repo.get_for_ticket(ticket_id)
        active_envelopes = [
            e for e in envelopes 
            if e.status in [EnvelopeStatus.PENDING, EnvelopeStatus.ACTIVE]
        ]
        
        ticket = await self.ticket_repo.get(ticket_id)
        ticket.has_active_envelopes = len(active_envelopes) > 0
        
        # If no more active envelopes and was waiting, go back to in_progress
        if not ticket.has_active_envelopes and ticket.status == TicketStatus.WAITING_INTERNAL:
            ticket.status = TicketStatus.IN_PROGRESS
        
        ticket.updated_at = datetime.utcnow()
        await self.ticket_repo.save(ticket)
    
    async def _notify_envelope_created(
        self, 
        envelope: Envelope, 
        ticket: Ticket,
        requester
    ) -> None:
        """Notify team/agent of new envelope."""
        # TODO: Route to notification service
        pass
    
    async def _notify_envelope_accepted(
        self, 
        envelope: Envelope, 
        agent
    ) -> None:
        """Notify owner that expert accepted."""
        # TODO: Route to notification service
        pass
    
    async def _notify_envelope_completed(
        self, 
        envelope: Envelope, 
        agent,
        summary: str
    ) -> None:
        """Notify relevant parties of completion."""
        # TODO: Route to notification service
        pass
