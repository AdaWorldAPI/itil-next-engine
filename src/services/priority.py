"""
ITIL-NEXT Priority Service

Dynamic priority scoring with urgency multipliers.

Formula: calculated_score = base_priority × urgency_multipliers

This ensures a Medium ticket about to breach SLA for a VIP
ranks higher than a High ticket with plenty of time.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from dataclasses import dataclass

from ..models.ticket import (
    Ticket,
    Priority,
    TicketStatus,
    CaseFlagType
)


@dataclass
class PriorityScore:
    """Breakdown of priority calculation."""
    ticket_id: UUID
    base_priority: int
    multipliers: dict
    calculated_score: float
    calculated_at: datetime


class PriorityService:
    """
    Dynamic priority scoring.
    
    Base Priorities:
    - Critical: 100
    - High: 70
    - Medium: 40
    - Low: 10
    
    Urgency Multipliers:
    - SLA breach proximity: 1.0 - 3.0×
    - VIP customer: 1.5×
    - Escalation pending: 1.3×
    - Staleness (no update): 1.2 - 1.4×
    - Social media flag: 1.5×
    - Repeat contact flag: 1.3×
    
    Example:
    Medium (40) × SLA<4h (2.0) × VIP (1.5) = 120
    This ranks HIGHER than High base (70)
    """
    
    BASE_SCORES = {
        Priority.CRITICAL: 100,
        Priority.HIGH: 70,
        Priority.MEDIUM: 40,
        Priority.LOW: 10
    }
    
    def __init__(
        self,
        ticket_repo,
        contact_repo,
        company_repo,
        envelope_repo,
        sla_repo
    ):
        self.ticket_repo = ticket_repo
        self.contact_repo = contact_repo
        self.company_repo = company_repo
        self.envelope_repo = envelope_repo
        self.sla_repo = sla_repo
    
    async def calculate_score(
        self,
        ticket_id: UUID
    ) -> PriorityScore:
        """
        Calculate dynamic priority score for a ticket.
        """
        ticket = await self.ticket_repo.get(ticket_id)
        
        # Base score
        base = self.BASE_SCORES.get(ticket.priority, 40)
        
        # Collect multipliers
        multipliers = {}
        
        # 1. SLA breach proximity
        sla_mult = await self._sla_multiplier(ticket)
        if sla_mult > 1.0:
            multipliers["sla_proximity"] = sla_mult
        
        # 2. VIP customer
        vip_mult = await self._vip_multiplier(ticket)
        if vip_mult > 1.0:
            multipliers["vip_customer"] = vip_mult
        
        # 3. Escalation pending
        esc_mult = await self._escalation_multiplier(ticket)
        if esc_mult > 1.0:
            multipliers["escalation_pending"] = esc_mult
        
        # 4. Staleness
        stale_mult = self._staleness_multiplier(ticket)
        if stale_mult > 1.0:
            multipliers["staleness"] = stale_mult
        
        # 5. Case flags
        flag_mult = await self._flag_multiplier(ticket)
        if flag_mult > 1.0:
            multipliers["case_flags"] = flag_mult
        
        # 6. Customer waiting
        wait_mult = self._customer_waiting_multiplier(ticket)
        if wait_mult > 1.0:
            multipliers["customer_waiting"] = wait_mult
        
        # Calculate final score
        total_multiplier = 1.0
        for mult in multipliers.values():
            total_multiplier *= mult
        
        calculated = base * total_multiplier
        
        return PriorityScore(
            ticket_id=ticket_id,
            base_priority=base,
            multipliers=multipliers,
            calculated_score=round(calculated, 2),
            calculated_at=datetime.utcnow()
        )
    
    async def get_work_queue(
        self,
        agent_id: UUID,
        limit: int = 50
    ) -> List[dict]:
        """
        Get prioritized work queue for an agent.
        
        Returns tickets sorted by calculated priority score.
        Grouped into: Needs Attention / Waiting / On Track
        """
        # Get agent's tickets
        tickets = await self.ticket_repo.get_for_agent(agent_id)
        
        # Calculate scores
        scored = []
        for ticket in tickets:
            if ticket.status in [TicketStatus.CLOSED, TicketStatus.RESOLVED]:
                continue
            
            score = await self.calculate_score(ticket.id)
            scored.append({
                "ticket": ticket,
                "score": score
            })
        
        # Sort by score descending
        scored.sort(key=lambda x: x["score"].calculated_score, reverse=True)
        
        # Categorize
        needs_attention = []
        waiting = []
        on_track = []
        
        for item in scored[:limit]:
            ticket = item["ticket"]
            score = item["score"]
            
            # Needs attention: High score OR specific conditions
            if (
                score.calculated_score >= 80 or
                "sla_proximity" in score.multipliers or
                ticket.status == TicketStatus.WAITING_CUSTOMER
            ):
                needs_attention.append(item)
            elif ticket.status == TicketStatus.WAITING_INTERNAL:
                waiting.append(item)
            else:
                on_track.append(item)
        
        return {
            "needs_attention": needs_attention,
            "waiting_on_others": waiting,
            "on_track": on_track,
            "total": len(scored)
        }
    
    async def get_team_queue(
        self,
        team_id: UUID,
        limit: int = 100
    ) -> List[dict]:
        """
        Get prioritized queue for a team.
        Useful for Kanban board and team leads.
        """
        tickets = await self.ticket_repo.get_for_team(team_id)
        
        scored = []
        for ticket in tickets:
            if ticket.status in [TicketStatus.CLOSED, TicketStatus.RESOLVED]:
                continue
            
            score = await self.calculate_score(ticket.id)
            scored.append({
                "ticket": ticket,
                "score": score
            })
        
        scored.sort(key=lambda x: x["score"].calculated_score, reverse=True)
        return scored[:limit]
    
    # =========================================================================
    # Multiplier calculations
    # =========================================================================
    
    async def _sla_multiplier(self, ticket: Ticket) -> float:
        """
        SLA breach proximity multiplier.
        
        - >24h remaining: 1.0×
        - 12-24h: 1.3×
        - 4-12h: 1.7×
        - 1-4h: 2.0×
        - <1h: 2.5×
        - BREACHED: 3.0×
        """
        if not ticket.sla_breach_at:
            return 1.0
        
        now = datetime.utcnow()
        time_to_breach = ticket.sla_breach_at - now
        hours = time_to_breach.total_seconds() / 3600
        
        if hours < 0:
            return 3.0  # Already breached
        elif hours < 1:
            return 2.5
        elif hours < 4:
            return 2.0
        elif hours < 12:
            return 1.7
        elif hours < 24:
            return 1.3
        else:
            return 1.0
    
    async def _vip_multiplier(self, ticket: Ticket) -> float:
        """
        VIP customer multiplier.
        
        - VIP: 1.5×
        - Premium: 1.2×
        - Standard: 1.0×
        """
        contact = await self.contact_repo.get(ticket.requester_id)
        
        # Check contact tier
        if contact.tier == "vip":
            return 1.5
        elif contact.tier == "premium":
            return 1.2
        
        # Also check company tier
        if ticket.company_id:
            company = await self.company_repo.get(ticket.company_id)
            if company.tier == "vip":
                return 1.5
            elif company.tier == "premium":
                return 1.2
        
        return 1.0
    
    async def _escalation_multiplier(self, ticket: Ticket) -> float:
        """
        Pending escalation/envelope multiplier.
        
        Active envelope waiting = 1.3×
        (Expert responded, owner should review)
        """
        if not ticket.has_active_envelopes:
            return 1.0
        
        # Check if any envelope has expert response
        envelopes = await self.envelope_repo.get_active_for_ticket(ticket.id)
        for env in envelopes:
            # TODO: Check if expert has responded
            # For now, just having active envelopes gets a boost
            return 1.3
        
        return 1.0
    
    def _staleness_multiplier(self, ticket: Ticket) -> float:
        """
        Staleness multiplier (no updates).
        
        - 3-7 days: 1.2×
        - 7-14 days: 1.3×
        - >14 days: 1.4×
        """
        days_since_update = (
            datetime.utcnow() - ticket.updated_at
        ).days
        
        if days_since_update > 14:
            return 1.4
        elif days_since_update > 7:
            return 1.3
        elif days_since_update > 3:
            return 1.2
        else:
            return 1.0
    
    async def _flag_multiplier(self, ticket: Ticket) -> float:
        """
        Case flag multiplier.
        
        - Social media: 1.5× (reputation risk)
        - Legal: 1.5× (compliance risk)
        - Repeat contact: 1.3× (frustrated customer)
        """
        flags = await self.ticket_repo.get_flags(ticket.id)
        
        max_mult = 1.0
        for flag in flags:
            if flag.type == CaseFlagType.SOCIAL_MEDIA:
                max_mult = max(max_mult, 1.5)
            elif flag.type == CaseFlagType.LEGAL:
                max_mult = max(max_mult, 1.5)
            elif flag.type == CaseFlagType.REPEAT_CONTACT:
                max_mult = max(max_mult, 1.3)
        
        return max_mult
    
    def _customer_waiting_multiplier(self, ticket: Ticket) -> float:
        """
        Customer waiting for response multiplier.
        
        If status is IN_PROGRESS and last activity was customer,
        they're waiting for us.
        """
        if ticket.status != TicketStatus.IN_PROGRESS:
            return 1.0
        
        # TODO: Check if last timeline entry was from customer
        # For now, use first_response tracking
        if not ticket.first_response_at:
            # No response yet - customer waiting
            hours_waiting = (
                datetime.utcnow() - ticket.created_at
            ).total_seconds() / 3600
            
            if hours_waiting > 4:
                return 1.4
            elif hours_waiting > 2:
                return 1.2
        
        return 1.0


class WorkQueueSection:
    """Work queue section for UI rendering."""
    
    NEEDS_ATTENTION = "needs_attention"
    WAITING_ON_OTHERS = "waiting_on_others"
    ON_TRACK = "on_track"
