"""
ITIL-NEXT Timeline Service

HubSpot "engagements" pattern for activity feed.

The timeline is the heart of the ticket view:
- All activity in chronological order
- Emails, notes, system events, envelope summaries
- Scoped views (main timeline vs envelope threads)
- Visibility controls (public/internal/envelope-only)
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from ..models.ticket import (
    TimelineEntry,
    TimelineEntryType,
    Visibility
)


class TimelineService:
    """
    Manages ticket timeline (activity feed).
    
    Follows HubSpot pattern:
    - Entries are "engagements" attached to tickets
    - Can be emails, notes, calls, system events
    - Supports associations (envelope_id for scoping)
    
    Our additions:
    - Visibility levels (public/internal/envelope-only)
    - Envelope threading (separate streams that merge)
    """
    
    def __init__(
        self,
        timeline_repo,
        ticket_repo,
        agent_repo
    ):
        self.timeline_repo = timeline_repo
        self.ticket_repo = ticket_repo
        self.agent_repo = agent_repo
    
    async def add_entry(
        self,
        ticket_id: UUID,
        entry_type: TimelineEntryType,
        content: str,
        author_id: Optional[UUID] = None,
        author_type: str = "agent",
        visibility: Visibility = Visibility.INTERNAL,
        envelope_id: Optional[UUID] = None,
        subject: Optional[str] = None,
        content_html: Optional[str] = None,
        email_message_id: Optional[str] = None,
        email_from: Optional[str] = None,
        email_to: Optional[List[str]] = None,
        attachment_ids: Optional[List[UUID]] = None
    ) -> TimelineEntry:
        """
        Add an entry to the timeline.
        
        This is the generic method - specific helpers exist for
        common entry types (add_note, add_email, etc.)
        """
        entry = TimelineEntry(
            ticket_id=ticket_id,
            envelope_id=envelope_id,
            type=entry_type,
            visibility=visibility,
            author_id=author_id,
            author_type=author_type,
            subject=subject,
            content=content,
            content_html=content_html,
            email_message_id=email_message_id,
            email_from=email_from,
            email_to=email_to,
            attachment_ids=attachment_ids
        )
        
        await self.timeline_repo.add(entry)
        
        # Update ticket timestamp
        ticket = await self.ticket_repo.get(ticket_id)
        ticket.updated_at = datetime.utcnow()
        await self.ticket_repo.save(ticket)
        
        return entry
    
    async def add_note(
        self,
        ticket_id: UUID,
        agent_id: UUID,
        content: str,
        visibility: Visibility = Visibility.INTERNAL,
        envelope_id: Optional[UUID] = None
    ) -> TimelineEntry:
        """
        Add an agent note to the timeline.
        """
        return await self.add_entry(
            ticket_id=ticket_id,
            entry_type=TimelineEntryType.NOTE,
            content=content,
            author_id=agent_id,
            author_type="agent",
            visibility=visibility,
            envelope_id=envelope_id
        )
    
    async def add_email_inbound(
        self,
        ticket_id: UUID,
        email_from: str,
        email_to: List[str],
        subject: str,
        content: str,
        content_html: Optional[str] = None,
        email_message_id: Optional[str] = None,
        attachment_ids: Optional[List[UUID]] = None
    ) -> TimelineEntry:
        """
        Add an inbound email from customer.
        """
        return await self.add_entry(
            ticket_id=ticket_id,
            entry_type=TimelineEntryType.EMAIL_INBOUND,
            content=content,
            content_html=content_html,
            author_type="customer",
            visibility=Visibility.PUBLIC,  # Customer can see their own emails
            subject=subject,
            email_message_id=email_message_id,
            email_from=email_from,
            email_to=email_to,
            attachment_ids=attachment_ids
        )
    
    async def add_email_outbound(
        self,
        ticket_id: UUID,
        agent_id: UUID,
        email_from: str,
        email_to: List[str],
        subject: str,
        content: str,
        content_html: Optional[str] = None,
        email_message_id: Optional[str] = None,
        attachment_ids: Optional[List[UUID]] = None
    ) -> TimelineEntry:
        """
        Add an outbound email to customer.
        """
        return await self.add_entry(
            ticket_id=ticket_id,
            entry_type=TimelineEntryType.EMAIL_OUTBOUND,
            content=content,
            content_html=content_html,
            author_id=agent_id,
            author_type="agent",
            visibility=Visibility.PUBLIC,  # Customer can see our responses
            subject=subject,
            email_message_id=email_message_id,
            email_from=email_from,
            email_to=email_to,
            attachment_ids=attachment_ids
        )
    
    async def add_system_event(
        self,
        ticket_id: UUID,
        content: str,
        envelope_id: Optional[UUID] = None
    ) -> TimelineEntry:
        """
        Add a system event (status change, assignment, etc.)
        """
        return await self.add_entry(
            ticket_id=ticket_id,
            entry_type=TimelineEntryType.SYSTEM,
            content=content,
            author_type="system",
            visibility=Visibility.INTERNAL,
            envelope_id=envelope_id
        )
    
    async def get_timeline(
        self,
        ticket_id: UUID,
        viewer_id: Optional[UUID] = None,
        viewer_type: str = "agent",
        include_envelope_threads: bool = True,
        envelope_id: Optional[UUID] = None
    ) -> List[TimelineEntry]:
        """
        Get timeline entries for a ticket.
        
        Filters by visibility based on viewer:
        - Customer: Only PUBLIC entries
        - Agent (owner): All entries
        - Agent (envelope expert): INTERNAL + their envelope
        
        Args:
            ticket_id: The ticket
            viewer_id: Who's viewing (for permissions)
            viewer_type: "agent" or "customer"
            include_envelope_threads: Merge envelope threads into main
            envelope_id: If set, only get entries for this envelope
        """
        # Get all entries for ticket
        if envelope_id:
            entries = await self.timeline_repo.get_for_envelope(
                ticket_id, envelope_id
            )
        else:
            entries = await self.timeline_repo.get_for_ticket(ticket_id)
        
        # Filter by visibility
        filtered = []
        for entry in entries:
            if self._can_view(entry, viewer_id, viewer_type, envelope_id):
                filtered.append(entry)
        
        # Sort chronologically
        filtered.sort(key=lambda e: e.created_at)
        
        return filtered
    
    async def get_main_timeline(
        self,
        ticket_id: UUID,
        viewer_id: Optional[UUID] = None
    ) -> List[TimelineEntry]:
        """
        Get main timeline (no envelope threads).
        Envelope summaries appear when envelopes complete.
        """
        entries = await self.timeline_repo.get_for_ticket(
            ticket_id,
            envelope_id=None  # Main thread only
        )
        
        # Add envelope completion summaries
        envelope_completions = await self.timeline_repo.get_by_type(
            ticket_id,
            TimelineEntryType.ENVELOPE_COMPLETED
        )
        entries.extend(envelope_completions)
        
        # Filter and sort
        filtered = [
            e for e in entries
            if self._can_view(e, viewer_id, "agent", None)
        ]
        filtered.sort(key=lambda e: e.created_at)
        
        return filtered
    
    async def get_envelope_thread(
        self,
        ticket_id: UUID,
        envelope_id: UUID,
        viewer_id: UUID
    ) -> List[TimelineEntry]:
        """
        Get entries for a specific envelope thread.
        Only owner and assigned expert can view.
        """
        entries = await self.timeline_repo.get_for_envelope(
            ticket_id, envelope_id
        )
        
        # Sort chronologically
        entries.sort(key=lambda e: e.created_at)
        
        return entries
    
    async def get_customer_view(
        self,
        ticket_id: UUID
    ) -> List[TimelineEntry]:
        """
        Get timeline as customer sees it.
        Only PUBLIC entries (their emails and our responses).
        """
        entries = await self.timeline_repo.get_for_ticket(ticket_id)
        
        public_entries = [
            e for e in entries
            if e.visibility == Visibility.PUBLIC
        ]
        
        public_entries.sort(key=lambda e: e.created_at)
        return public_entries
    
    def _can_view(
        self,
        entry: TimelineEntry,
        viewer_id: Optional[UUID],
        viewer_type: str,
        viewing_envelope_id: Optional[UUID]
    ) -> bool:
        """
        Check if viewer can see this entry.
        """
        # Customers only see PUBLIC
        if viewer_type == "customer":
            return entry.visibility == Visibility.PUBLIC
        
        # PUBLIC and INTERNAL visible to all agents
        if entry.visibility in [Visibility.PUBLIC, Visibility.INTERNAL]:
            return True
        
        # ENVELOPE_ONLY requires being in that envelope context
        if entry.visibility == Visibility.ENVELOPE_ONLY:
            # If viewing specific envelope, check match
            if viewing_envelope_id:
                return entry.envelope_id == viewing_envelope_id
            # Otherwise, need to be owner or assigned expert
            # (This requires ticket context - simplified for now)
            return True
        
        return False


class TimelineSearch:
    """
    Search within ticket timelines.
    """
    
    def __init__(self, timeline_repo):
        self.timeline_repo = timeline_repo
    
    async def search(
        self,
        ticket_id: UUID,
        query: str,
        entry_types: Optional[List[TimelineEntryType]] = None
    ) -> List[TimelineEntry]:
        """
        Full-text search within a ticket's timeline.
        """
        return await self.timeline_repo.search(
            ticket_id=ticket_id,
            query=query,
            entry_types=entry_types
        )
    
    async def find_emails(
        self,
        ticket_id: UUID,
        email_address: Optional[str] = None
    ) -> List[TimelineEntry]:
        """
        Find all emails in a ticket, optionally filtered by address.
        """
        entries = await self.timeline_repo.get_by_types(
            ticket_id,
            [TimelineEntryType.EMAIL_INBOUND, TimelineEntryType.EMAIL_OUTBOUND]
        )
        
        if email_address:
            entries = [
                e for e in entries
                if (
                    e.email_from == email_address or
                    (e.email_to and email_address in e.email_to)
                )
            ]
        
        return entries
