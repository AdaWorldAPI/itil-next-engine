"""
ITIL-NEXT Resolution Service

Sony empowerment pattern:
- Agents have discretionary authority up to limit
- Structured documentation (what/why/when/where)
- Calibration workflow for edge cases

The key: Trust agents to resolve, document for alignment.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from ..models.ticket import (
    Resolution,
    ResolutionType,
    EmpowermentTier,
    TimelineEntry,
    TimelineEntryType,
    Visibility,
    CaseFlag,
    CaseFlagType
)


class ResolutionError(Exception):
    """Raised when resolution operations fail."""
    pass


class ResolutionService:
    """
    Manages resolutions with empowerment tiers.
    
    Empowerment Model:
    - Tier 1 (Agent): Up to €100, just document
    - Tier 2 (Team Lead): €100-500, quick approval
    - Tier 3 (Manager): >€500, calibration review
    
    Documentation (What/Why/When/Where):
    - WHAT went wrong (root cause)
    - WHY customer is eligible (entitlement)
    - WHAT resolution provided
    - Timestamps auto-captured
    """
    
    def __init__(
        self,
        resolution_repo,
        ticket_repo,
        agent_repo,
        team_repo,
        timeline_repo,
        calibration_repo,
        notification_service
    ):
        self.resolution_repo = resolution_repo
        self.ticket_repo = ticket_repo
        self.agent_repo = agent_repo
        self.team_repo = team_repo
        self.timeline_repo = timeline_repo
        self.calibration_repo = calibration_repo
        self.notifications = notification_service
    
    async def create_resolution(
        self,
        ticket_id: UUID,
        agent_id: UUID,
        what_went_wrong: str,
        what_went_wrong_category: Optional[str],
        why_eligible: str,
        why_eligible_category: Optional[str],
        resolution_type: ResolutionType,
        resolution_details: Optional[str] = None,
        amount: Optional[float] = None,
        currency: str = "EUR"
    ) -> Resolution:
        """
        Create a resolution with empowerment check.
        
        Automatically determines tier based on amount vs limits.
        Routes for approval if needed.
        """
        ticket = await self.ticket_repo.get(ticket_id)
        agent = await self.agent_repo.get(agent_id)
        
        # Validate ownership
        if ticket.owner_id != agent_id:
            raise ResolutionError(
                "Only ticket owner can create resolutions."
            )
        
        # Determine empowerment tier
        tier = await self._determine_tier(agent, amount)
        
        resolution = Resolution(
            ticket_id=ticket_id,
            agent_id=agent_id,
            what_went_wrong=what_went_wrong,
            what_went_wrong_category=what_went_wrong_category,
            why_eligible=why_eligible,
            why_eligible_category=why_eligible_category,
            resolution_type=resolution_type,
            resolution_details=resolution_details,
            amount=amount,
            currency=currency,
            empowerment_tier=tier,
            calibration_status="pending" if tier == EmpowermentTier.MANAGER else "not_required"
        )
        
        # Handle based on tier
        if tier == EmpowermentTier.AGENT:
            # Agent discretion - save immediately
            resolution.approved_by = agent_id  # Self-approved
            resolution.approved_at = datetime.utcnow()
            await self.resolution_repo.save(resolution)
            await self._log_resolution(resolution, agent)
            
        elif tier == EmpowermentTier.TEAM_LEAD:
            # Needs team lead approval
            await self.resolution_repo.save(resolution)
            await self._request_approval(resolution, agent, "team_lead")
            
        else:  # MANAGER
            # Needs manager approval + goes to calibration
            await self.resolution_repo.save(resolution)
            await self._request_approval(resolution, agent, "manager")
            await self._create_calibration_item(resolution, "tier3")
        
        # Check for case flags that require calibration
        await self._check_flag_calibration(ticket_id, resolution)
        
        return resolution
    
    async def approve_resolution(
        self,
        resolution_id: UUID,
        approver_id: UUID,
        approved: bool,
        notes: Optional[str] = None
    ) -> Resolution:
        """
        Team lead or manager approves/rejects resolution.
        """
        resolution = await self.resolution_repo.get(resolution_id)
        approver = await self.agent_repo.get(approver_id)
        
        # TODO: Validate approver has appropriate role
        
        if approved:
            resolution.approved_by = approver_id
            resolution.approved_at = datetime.utcnow()
            
            agent = await self.agent_repo.get(resolution.agent_id)
            await self._log_resolution(resolution, agent)
            
            # Notify agent
            await self.notifications.notify_resolution_approved(
                resolution, approver
            )
        else:
            resolution.calibration_status = "rejected"
            
            # Notify agent with feedback
            await self.notifications.notify_resolution_rejected(
                resolution, approver, notes
            )
        
        await self.resolution_repo.save(resolution)
        return resolution
    
    async def get_pending_approvals(
        self,
        approver_id: UUID
    ) -> List[Resolution]:
        """
        Get resolutions awaiting this approver's review.
        """
        agent = await self.agent_repo.get(approver_id)
        
        # Get resolutions from teams this agent leads
        # TODO: Role-based filtering
        return await self.resolution_repo.get_pending_for_approver(approver_id)
    
    async def _determine_tier(
        self,
        agent,
        amount: Optional[float]
    ) -> EmpowermentTier:
        """
        Determine empowerment tier based on amount and limits.
        """
        if amount is None or amount == 0:
            return EmpowermentTier.AGENT
        
        # Get team limits (use first team for now)
        if agent.team_ids:
            team = await self.team_repo.get(agent.team_ids[0])
            tier1_limit = team.tier1_limit
            tier2_limit = team.tier2_limit
        else:
            # Fallback defaults
            tier1_limit = 100.0
            tier2_limit = 500.0
        
        # Also check agent's personal limit
        personal_limit = agent.empowerment_limit
        effective_tier1 = min(tier1_limit, personal_limit)
        
        if amount <= effective_tier1:
            return EmpowermentTier.AGENT
        elif amount <= tier2_limit:
            return EmpowermentTier.TEAM_LEAD
        else:
            return EmpowermentTier.MANAGER
    
    async def _log_resolution(
        self,
        resolution: Resolution,
        agent
    ) -> None:
        """
        Log resolution to ticket timeline.
        """
        amount_str = (
            f"{resolution.currency} {resolution.amount:.2f}"
            if resolution.amount
            else "No compensation"
        )
        
        await self.timeline_repo.add(TimelineEntry(
            ticket_id=resolution.ticket_id,
            type=TimelineEntryType.RESOLUTION,
            visibility=Visibility.INTERNAL,
            author_id=resolution.agent_id,
            content=(
                f"✅ Resolution provided\n\n"
                f"**What went wrong:** {resolution.what_went_wrong}\n"
                f"**Why eligible:** {resolution.why_eligible}\n"
                f"**Resolution:** {resolution.resolution_type.value}\n"
                f"**Amount:** {amount_str}\n"
                f"**Tier:** {resolution.empowerment_tier.value}"
            )
        ))
    
    async def _request_approval(
        self,
        resolution: Resolution,
        agent,
        level: str
    ) -> None:
        """
        Request approval from team lead or manager.
        """
        # TODO: Find appropriate approver
        # TODO: Send notification
        pass
    
    async def _create_calibration_item(
        self,
        resolution: Resolution,
        reason: str
    ) -> None:
        """
        Add resolution to calibration queue.
        """
        await self.calibration_repo.add_item(
            resolution_id=resolution.id,
            reason=reason
        )
    
    async def _check_flag_calibration(
        self,
        ticket_id: UUID,
        resolution: Resolution
    ) -> None:
        """
        Check if ticket flags require calibration.
        
        Sony pattern: Physical damage and social media cases
        always go to calibration review.
        """
        flags = await self.ticket_repo.get_flags(ticket_id)
        
        calibration_flags = {
            CaseFlagType.PHYSICAL_DAMAGE,
            CaseFlagType.SOCIAL_MEDIA,
            CaseFlagType.LEGAL
        }
        
        for flag in flags:
            if flag.type in calibration_flags:
                await self._create_calibration_item(
                    resolution,
                    reason=f"flagged_{flag.type.value}"
                )
                break  # One calibration item is enough


class CalibrationService:
    """
    Weekly calibration workflow (Sony pattern).
    
    Reviews:
    - All tier 3 resolutions
    - Flagged cases (physical damage, social media)
    - Random sample from tier 1-2
    - Cases with customer complaints
    """
    
    def __init__(
        self,
        calibration_repo,
        resolution_repo,
        ticket_repo
    ):
        self.calibration_repo = calibration_repo
        self.resolution_repo = resolution_repo
        self.ticket_repo = ticket_repo
    
    async def generate_weekly_queue(
        self,
        week_start: datetime,
        week_end: datetime,
        sample_percentage: float = 0.05  # 5% random sample
    ) -> List[dict]:
        """
        Generate calibration queue for the week.
        """
        items = []
        
        # 1. All tier 3 resolutions
        tier3 = await self.resolution_repo.get_by_tier(
            EmpowermentTier.MANAGER,
            week_start,
            week_end
        )
        items.extend([
            {"resolution": r, "reason": "tier3"} 
            for r in tier3
        ])
        
        # 2. All flagged cases
        flagged = await self.calibration_repo.get_by_reason_prefix(
            "flagged_",
            week_start,
            week_end
        )
        items.extend(flagged)
        
        # 3. Random sample from tier 1-2
        tier1_2 = await self.resolution_repo.get_by_tiers(
            [EmpowermentTier.AGENT, EmpowermentTier.TEAM_LEAD],
            week_start,
            week_end
        )
        sample_size = int(len(tier1_2) * sample_percentage)
        import random
        sample = random.sample(tier1_2, min(sample_size, len(tier1_2)))
        items.extend([
            {"resolution": r, "reason": "random_sample"}
            for r in sample
        ])
        
        # 4. Cases with complaints (TODO: integrate with feedback system)
        
        return items
    
    async def review_item(
        self,
        item_id: UUID,
        reviewer_id: UUID,
        outcome: str,  # "upheld" | "revised" | "coaching_needed"
        notes: str
    ) -> dict:
        """
        Record calibration review outcome.
        """
        item = await self.calibration_repo.get(item_id)
        resolution = await self.resolution_repo.get(item.resolution_id)
        
        item.review_status = "reviewed"
        item.outcome = outcome
        item.reviewer_notes = notes
        item.reviewed_at = datetime.utcnow()
        item.reviewer_id = reviewer_id
        
        await self.calibration_repo.save(item)
        
        # Update resolution
        resolution.calibration_status = outcome
        await self.resolution_repo.save(resolution)
        
        # If coaching needed, notify agent's team lead
        if outcome == "coaching_needed":
            # TODO: Create coaching task
            pass
        
        return {"item": item, "resolution": resolution}
    
    async def get_calibration_report(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> dict:
        """
        Generate calibration metrics report.
        """
        items = await self.calibration_repo.get_reviewed(
            period_start,
            period_end
        )
        
        total = len(items)
        if total == 0:
            return {"total": 0, "message": "No calibration data"}
        
        upheld = len([i for i in items if i.outcome == "upheld"])
        revised = len([i for i in items if i.outcome == "revised"])
        coaching = len([i for i in items if i.outcome == "coaching_needed"])
        
        # Group by reason
        by_reason = {}
        for item in items:
            reason = item.reason
            if reason not in by_reason:
                by_reason[reason] = {"total": 0, "upheld": 0}
            by_reason[reason]["total"] += 1
            if item.outcome == "upheld":
                by_reason[reason]["upheld"] += 1
        
        # Calculate uphold rates
        for reason, stats in by_reason.items():
            stats["uphold_rate"] = (
                stats["upheld"] / stats["total"] * 100
                if stats["total"] > 0 else 0
            )
        
        return {
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "totals": {
                "reviewed": total,
                "upheld": upheld,
                "revised": revised,
                "coaching_needed": coaching,
                "uphold_rate": upheld / total * 100
            },
            "by_reason": by_reason
        }
