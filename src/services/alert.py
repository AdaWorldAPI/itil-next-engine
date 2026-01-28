"""
ITIL-NEXT Alert Service

SolarWinds Web Help Desk pattern: Escalating alert matrix.

3 conditions × 3 levels × progressive recipients.
Business time aware.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Set
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# =============================================================================
# MODELS
# =============================================================================

class AlertCondition(str, Enum):
    NOT_ASSIGNED = "not_assigned"    # Ticket sitting in queue
    NOT_UPDATED = "not_updated"      # Ticket going stale
    NOT_COMPLETED = "not_completed"  # Approaching/past due


class AlertTrigger(str, Enum):
    AFTER_CREATION = "after_creation"
    SINCE_LAST_UPDATE = "since_last_update"
    BEFORE_DUE_DATE = "before_due_date"


class RecipientType(str, Enum):
    TECH = "tech"           # The assigned agent (owner)
    SUPERVISOR = "supervisor"  # Team lead
    GROUP_MANAGER = "group_manager"  # Manager


class TimeUnit(str, Enum):
    MINUTES = "minutes"
    HOURS = "hours"


class AlertRule(BaseModel):
    """Single alert rule within a level."""
    condition: AlertCondition
    time_value: int
    time_unit: TimeUnit
    trigger: AlertTrigger
    recipients: Set[RecipientType]
    
    @property
    def duration(self) -> timedelta:
        if self.time_unit == TimeUnit.MINUTES:
            return timedelta(minutes=self.time_value)
        return timedelta(hours=self.time_value)


class AlertLevel(BaseModel):
    """A level of escalation (1, 2, or 3)."""
    level: int
    rules: List[AlertRule]


class PriorityAlertConfig(BaseModel):
    """
    Complete alert configuration for a priority level.
    
    SolarWinds pattern: Each priority has its own alert matrix.
    """
    id: UUID = Field(default_factory=uuid4)
    priority_name: str  # "critical", "high", "medium", "low"
    display_order: int
    color: str  # Hex color for UI
    
    # SLA times
    due_time_hours: float  # Target resolution time
    client_reminder_hours: float  # How often to remind customer
    
    # Alert levels (typically 3)
    alert_levels: List[AlertLevel]
    
    # Business hours config
    use_business_time: bool = True
    business_start_hour: int = 8  # 8 AM
    business_end_hour: int = 18   # 6 PM
    business_days: List[int] = Field(default_factory=lambda: [0,1,2,3,4])  # Mon-Fri


class Alert(BaseModel):
    """An active or triggered alert."""
    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    
    condition: AlertCondition
    level: int
    
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    
    recipients_notified: List[UUID] = Field(default_factory=list)


# =============================================================================
# DEFAULT CONFIGURATIONS
# =============================================================================

def create_critical_config() -> PriorityAlertConfig:
    """Critical priority - tight SLAs (from SolarWinds screenshot)."""
    return PriorityAlertConfig(
        priority_name="critical",
        display_order=1,
        color="#FFD700",  # Gold/Yellow
        due_time_hours=1,
        client_reminder_hours=1,
        alert_levels=[
            AlertLevel(level=1, rules=[
                AlertRule(
                    condition=AlertCondition.NOT_ASSIGNED,
                    time_value=5, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.AFTER_CREATION,
                    recipients={RecipientType.GROUP_MANAGER}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_UPDATED,
                    time_value=15, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.SINCE_LAST_UPDATE,
                    recipients={RecipientType.TECH}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_COMPLETED,
                    time_value=30, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.BEFORE_DUE_DATE,
                    recipients={RecipientType.TECH}
                ),
            ]),
            AlertLevel(level=2, rules=[
                AlertRule(
                    condition=AlertCondition.NOT_ASSIGNED,
                    time_value=10, time_unit=TimeUnit.HOURS,
                    trigger=AlertTrigger.AFTER_CREATION,
                    recipients={RecipientType.GROUP_MANAGER}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_UPDATED,
                    time_value=30, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.SINCE_LAST_UPDATE,
                    recipients={RecipientType.TECH, RecipientType.SUPERVISOR}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_COMPLETED,
                    time_value=15, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.BEFORE_DUE_DATE,
                    recipients={RecipientType.TECH, RecipientType.SUPERVISOR}
                ),
            ]),
            AlertLevel(level=3, rules=[
                AlertRule(
                    condition=AlertCondition.NOT_ASSIGNED,
                    time_value=15, time_unit=TimeUnit.HOURS,
                    trigger=AlertTrigger.AFTER_CREATION,
                    recipients={RecipientType.GROUP_MANAGER}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_UPDATED,
                    time_value=45, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.SINCE_LAST_UPDATE,
                    recipients={RecipientType.TECH, RecipientType.SUPERVISOR, RecipientType.GROUP_MANAGER}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_COMPLETED,
                    time_value=0, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.BEFORE_DUE_DATE,
                    recipients={RecipientType.TECH, RecipientType.SUPERVISOR, RecipientType.GROUP_MANAGER}
                ),
            ]),
        ]
    )


def create_high_config() -> PriorityAlertConfig:
    """High priority - 4 hour SLA."""
    return PriorityAlertConfig(
        priority_name="high",
        display_order=2,
        color="#FF6B6B",  # Red
        due_time_hours=4,
        client_reminder_hours=2,
        alert_levels=[
            AlertLevel(level=1, rules=[
                AlertRule(
                    condition=AlertCondition.NOT_ASSIGNED,
                    time_value=15, time_unit=TimeUnit.MINUTES,
                    trigger=AlertTrigger.AFTER_CREATION,
                    recipients={RecipientType.GROUP_MANAGER}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_UPDATED,
                    time_value=1, time_unit=TimeUnit.HOURS,
                    trigger=AlertTrigger.SINCE_LAST_UPDATE,
                    recipients={RecipientType.TECH}
                ),
                AlertRule(
                    condition=AlertCondition.NOT_COMPLETED,
                    time_value=1, time_unit=TimeUnit.HOURS,
                    trigger=AlertTrigger.BEFORE_DUE_DATE,
                    recipients={RecipientType.TECH}
                ),
            ]),
            # ... Level 2 and 3 would follow similar pattern with longer times
        ]
    )


def create_medium_config() -> PriorityAlertConfig:
    """Medium priority - 8 hour SLA."""
    return PriorityAlertConfig(
        priority_name="medium",
        display_order=3,
        color="#4ECDC4",  # Teal
        due_time_hours=8,
        client_reminder_hours=4,
        alert_levels=[]  # Configure as needed
    )


def create_low_config() -> PriorityAlertConfig:
    """Low priority - 24 hour SLA."""
    return PriorityAlertConfig(
        priority_name="low",
        display_order=4,
        color="#95E1D3",  # Light green
        due_time_hours=24,
        client_reminder_hours=8,
        alert_levels=[]  # Configure as needed
    )


# =============================================================================
# SERVICE
# =============================================================================

class AlertService:
    """
    Manages ticket alerts using escalating matrix pattern.
    
    Runs periodically (e.g., every minute) to check for alert conditions.
    """
    
    def __init__(
        self,
        ticket_repo,
        alert_repo,
        alert_config_repo,
        agent_repo,
        team_repo,
        notification_service,
        business_calendar
    ):
        self.tickets = ticket_repo
        self.alerts = alert_repo
        self.configs = alert_config_repo
        self.agents = agent_repo
        self.teams = team_repo
        self.notifications = notification_service
        self.calendar = business_calendar
    
    async def check_ticket_alerts(self, ticket_id: UUID) -> List[Alert]:
        """
        Check a single ticket for alert conditions.
        
        Called by scheduler or on ticket update.
        """
        ticket = await self.tickets.get(ticket_id)
        config = await self.configs.get_for_priority(ticket.priority)
        
        if not config or not config.alert_levels:
            return []
        
        now = datetime.utcnow()
        triggered_alerts = []
        
        for level in config.alert_levels:
            for rule in level.rules:
                if await self._should_trigger(ticket, rule, config, now):
                    # Check if already alerted at this level for this condition
                    existing = await self.alerts.get_active(
                        ticket_id, rule.condition, level.level
                    )
                    if not existing:
                        alert = await self._trigger_alert(
                            ticket, rule, level.level, config
                        )
                        triggered_alerts.append(alert)
        
        return triggered_alerts
    
    async def check_all_open_tickets(self) -> List[Alert]:
        """
        Batch check all open tickets.
        
        Called by periodic scheduler (e.g., every minute).
        """
        open_tickets = await self.tickets.get_open()
        all_alerts = []
        
        for ticket in open_tickets:
            alerts = await self.check_ticket_alerts(ticket.id)
            all_alerts.extend(alerts)
        
        return all_alerts
    
    async def acknowledge_alert(
        self, 
        alert_id: UUID, 
        agent_id: UUID
    ) -> Alert:
        """Mark an alert as acknowledged."""
        alert = await self.alerts.get(alert_id)
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = agent_id
        await self.alerts.save(alert)
        return alert
    
    async def get_pending_alerts(
        self, 
        agent_id: UUID
    ) -> List[Alert]:
        """Get unacknowledged alerts for an agent."""
        return await self.alerts.get_pending_for_agent(agent_id)
    
    # =========================================================================
    # Private methods
    # =========================================================================
    
    async def _should_trigger(
        self,
        ticket,
        rule: AlertRule,
        config: PriorityAlertConfig,
        now: datetime
    ) -> bool:
        """Determine if a rule should trigger."""
        
        if rule.condition == AlertCondition.NOT_ASSIGNED:
            if ticket.owner_id is not None:
                return False  # Assigned, no alert
            
            if rule.trigger == AlertTrigger.AFTER_CREATION:
                elapsed = self._calc_business_time(
                    ticket.created_at, now, config
                )
                return elapsed >= rule.duration
        
        elif rule.condition == AlertCondition.NOT_UPDATED:
            if rule.trigger == AlertTrigger.SINCE_LAST_UPDATE:
                elapsed = self._calc_business_time(
                    ticket.updated_at, now, config
                )
                return elapsed >= rule.duration
        
        elif rule.condition == AlertCondition.NOT_COMPLETED:
            if ticket.resolved_at is not None:
                return False  # Already resolved
            
            if rule.trigger == AlertTrigger.BEFORE_DUE_DATE:
                if not ticket.sla_breach_at:
                    return False  # No due date set
                
                time_until_due = ticket.sla_breach_at - now
                # Alert if time until due <= rule duration
                # (e.g., alert 30min before due)
                return time_until_due <= rule.duration
        
        return False
    
    def _calc_business_time(
        self,
        start: datetime,
        end: datetime,
        config: PriorityAlertConfig
    ) -> timedelta:
        """
        Calculate business time between two datetimes.
        
        If use_business_time is False, returns simple difference.
        Otherwise, only counts hours within business_start/end on business_days.
        """
        if not config.use_business_time:
            return end - start
        
        # Delegate to business calendar service
        return self.calendar.business_time_between(
            start, end,
            start_hour=config.business_start_hour,
            end_hour=config.business_end_hour,
            business_days=config.business_days
        )
    
    async def _trigger_alert(
        self,
        ticket,
        rule: AlertRule,
        level: int,
        config: PriorityAlertConfig
    ) -> Alert:
        """Create and send an alert."""
        
        # Resolve recipients to actual agent IDs
        recipient_ids = await self._resolve_recipients(ticket, rule.recipients)
        
        alert = Alert(
            ticket_id=ticket.id,
            condition=rule.condition,
            level=level,
            triggered_at=datetime.utcnow(),
            recipients_notified=recipient_ids
        )
        
        await self.alerts.save(alert)
        
        # Send notifications
        for agent_id in recipient_ids:
            await self.notifications.send_alert(
                agent_id=agent_id,
                ticket=ticket,
                alert=alert,
                condition=rule.condition,
                level=level
            )
        
        return alert
    
    async def _resolve_recipients(
        self,
        ticket,
        recipient_types: Set[RecipientType]
    ) -> List[UUID]:
        """Convert recipient types to actual agent IDs."""
        recipient_ids = []
        
        for rtype in recipient_types:
            if rtype == RecipientType.TECH:
                if ticket.owner_id:
                    recipient_ids.append(ticket.owner_id)
            
            elif rtype == RecipientType.SUPERVISOR:
                # Get team lead for ticket's assigned team
                if ticket.owner_id:
                    owner = await self.agents.get(ticket.owner_id)
                    for team_id in owner.team_ids:
                        team = await self.teams.get(team_id)
                        if hasattr(team, 'supervisor_id') and team.supervisor_id:
                            recipient_ids.append(team.supervisor_id)
                            break  # Just first team's supervisor
            
            elif rtype == RecipientType.GROUP_MANAGER:
                # Get manager for the ticket's team/queue
                # TODO: Implement manager lookup
                pass
        
        return list(set(recipient_ids))  # Deduplicate
