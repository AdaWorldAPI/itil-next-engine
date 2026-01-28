# ITIL-NEXT Engine Context

## Purpose

The Engine is the heart of ITIL-NEXT. It implements:
- Ticket lifecycle (create → work → escalate → resolve)
- Ownership model (sacred, immutable until resolution)
- Parallel escalation (expertise joins, doesn't replace)
- SLA enforcement (time-to-value, not time-to-response)
- Routing rules (Orchestra patterns)

## Data Model

```
┌─────────────────────────────────────────────────────────────────┐
│                         CORE ENTITIES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   TICKET (Case)                                                  │
│   ├── id: UUID                                                  │
│   ├── reference: string (human-readable, e.g., INC-2024-1234)   │
│   ├── type: enum (incident, request, change, problem)           │
│   ├── status: enum (new, in_progress, escalated, resolved)      │
│   ├── owner_id: UUID → Agent (IMMUTABLE after accept)           │
│   ├── requester_id: UUID → Contact                              │
│   ├── created_at, updated_at, resolved_at                       │
│   ├── sla_id: UUID → SLA                                        │
│   └── timeline: TimelineEntry[]                                 │
│                                                                  │
│   AGENT                                                          │
│   ├── id: UUID                                                  │
│   ├── email: string                                             │
│   ├── name: string                                              │
│   ├── teams: Team[]                                             │
│   ├── skills: Skill[]                                           │
│   └── capacity: { current, max }                                │
│                                                                  │
│   ENVELOPE (Sub-case) — Amdocs pattern                          │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID → Ticket                                  │
│   ├── requested_by: UUID → Agent (the owner)                    │
│   ├── assigned_to: UUID → Agent (the expert)                    │
│   ├── team_id: UUID → Team (or specific agent)                  │
│   ├── status: enum (pending, active, completed)                 │
│   ├── reason: string                                            │
│   ├── created_at, completed_at                                  │
│   └── thread: TimelineEntry[] (scoped to this envelope)         │
│                                                                  │
│   TASK — smaller work items (Amdocs pattern)                    │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID → Ticket                                  │
│   ├── envelope_id: UUID? → Envelope (can be standalone)         │
│   ├── title: string                                             │
│   ├── description: string                                       │
│   ├── assigned_to: UUID → Agent                                 │
│   ├── status: enum (todo, in_progress, done, cancelled)         │
│   ├── due_date: datetime?                                       │
│   └── created_at, completed_at                                  │
│                                                                  │
│   TIMELINE_ENTRY                                                 │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID                                           │
│   ├── envelope_id: UUID? (null = main thread)                   │
│   ├── type: enum (email, note, system, envelope_request, task)  │
│   ├── visibility: enum (public, internal, envelope_only)        │
│   ├── author_id: UUID → Agent                                   │
│   ├── content: text                                             │
│   └── created_at                                                │
│                                                                  │
│   CONTACT (Customer)                                             │
│   ├── id: UUID                                                  │
│   ├── email: string                                             │
│   ├── name: string                                              │
│   ├── company_id: UUID? → Company                               │
│   ├── tier: enum (standard, premium, vip)                       │
│   └── hubspot_id: string? (for CRM linking)                     │
│                                                                  │
│   CASE_FLAG — special handling markers                          │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID → Ticket                                  │
│   ├── type: enum (physical_damage, social_media, vip,          │
│   │              legal, repeat_contact)                         │
│   ├── added_by: UUID → Agent                                    │
│   ├── reason: string                                            │
│   └── created_at                                                │
│                                                                  │
│   RESOLUTION — compensation/resolution tracking (Sony pattern)  │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID → Ticket                                  │
│   ├── agent_id: UUID → Agent                                    │
│   ├── what_went_wrong: enum + text                              │
│   ├── why_eligible: enum + text                                 │
│   ├── resolution_type: enum (refund, credit, replacement, etc.) │
│   ├── amount: decimal?                                          │
│   ├── empowerment_tier: enum (agent, team_lead, manager)        │
│   ├── approved_by: UUID? → Agent (if tier > agent)              │
│   ├── calibration_status: enum (pending, reviewed, upheld, revised)│
│   └── created_at                                                │
│                                                                  │
│   EMPOWERMENT_CONFIG — per-team authorization limits            │
│   ├── team_id: UUID → Team                                      │
│   ├── tier1_limit: decimal (agent discretion)                   │
│   ├── tier2_limit: decimal (team lead approval)                 │
│   └── tier3_requires: string (manager/calibration)              │
│                                                                  │
│   CALIBRATION_ITEM — weekly review queue                        │
│   ├── id: UUID                                                  │
│   ├── resolution_id: UUID → Resolution                          │
│   ├── reason: enum (tier3, flagged, random_sample, complaint)   │
│   ├── review_status: enum (pending, reviewed)                   │
│   ├── outcome: enum (upheld, revised, coaching_needed)          │
│   ├── reviewer_notes: text                                      │
│   └── reviewed_at: datetime?                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Entity Relationships (Amdocs-Inspired)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│   TICKET (Case)                                                  │
│   │                                                              │
│   ├── has_one OWNER (Agent) ─── immutable after accept          │
│   │                                                              │
│   ├── has_many ENVELOPES (Sub-cases)                            │
│   │   │                                                          │
│   │   ├── owned by EXPERT (Agent)                               │
│   │   ├── has_many TIMELINE_ENTRIES (scoped)                    │
│   │   └── can have TASKS                                        │
│   │                                                              │
│   ├── has_many TASKS (standalone or under envelope)             │
│   │                                                              │
│   └── has_many TIMELINE_ENTRIES (main thread)                   │
│                                                                  │
│   Key insight: Envelopes and Tasks are CHILDREN of Ticket.      │
│   They don't replace the ticket, they contribute to it.         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## State Machines

### Ticket Lifecycle

```
                    ┌───────────────┐
                    │     NEW       │
                    └───────┬───────┘
                            │ accept()
                            ▼
                    ┌───────────────┐
             ┌──────│  IN_PROGRESS  │──────┐
             │      └───────────────┘      │
             │              │              │
    escalate()              │              │ resolve()
             │              │              │
             ▼              │              ▼
    ┌───────────────┐       │      ┌───────────────┐
    │   ESCALATED   │───────┘      │   RESOLVED    │
    └───────────────┘  de-escalate └───────────────┘
```

**Note:** ESCALATED doesn't change owner. It's a flag indicating active parallel work.

### Escalation Lifecycle

```
    ┌───────────────┐
    │    PENDING    │  ← Created, waiting for expert
    └───────┬───────┘
            │ accept()
            ▼
    ┌───────────────┐
    │    ACTIVE     │  ← Expert is working
    └───────┬───────┘
            │ complete() / cancel()
            ▼
    ┌───────────────┐
    │   COMPLETED   │  ← Expert done, owner continues
    └───────────────┘
```

## Key Services

### OwnershipService

```python
class OwnershipService:
    def accept_ticket(ticket_id, agent_id) -> Ticket:
        """
        Agent accepts ownership. This is IMMUTABLE.
        After this, only system can change owner (e.g., agent leaves company).
        """
        
    def can_transfer(ticket_id, reason) -> bool:
        """
        Returns False in 99% of cases.
        Only allows: agent_terminated, agent_on_extended_leave
        """
        
    def get_owner(ticket_id) -> Agent:
        """Always returns the original accepting agent."""
```

### EscalationService

```python
class EscalationService:
    def create_escalation(ticket_id, to_team, reason) -> Escalation:
        """
        Creates parallel assist thread.
        Does NOT change ticket owner.
        """
        
    def add_to_escalation(escalation_id, content) -> TimelineEntry:
        """Expert adds to escalation thread."""
        
    def complete_escalation(escalation_id, summary) -> Escalation:
        """
        Expert marks their part done.
        Summary posted to main timeline (internal visibility).
        Owner continues with ticket.
        """
```

### SLAService

```python
class SLAService:
    def calculate_breach_time(ticket) -> datetime:
        """Based on priority, type, customer tier."""
        
    def pause_sla(ticket_id, reason) -> None:
        """Waiting on customer, approved pause."""
        
    def check_approaching_breach(ticket_id) -> SLAWarning?:
        """Returns warning if within threshold."""
```

## Rules Engine (Orchestra Pattern)

```yaml
# Example rule: Auto-route high priority
- name: route_critical_to_senior
  trigger:
    event: ticket.created
    conditions:
      - priority: critical
      - type: incident
  action:
    type: assign
    to: team:senior-support
    
# Example rule: Escalation timeout
- name: escalation_timeout_warning
  trigger:
    event: escalation.age_exceeded
    conditions:
      - age_hours: 4
      - status: pending
  action:
    type: notify
    to: team:escalation-managers
    message: "Escalation {escalation.id} waiting 4+ hours"
```

## Additional Models

### Priority & Urgency System

```
┌─────────────────────────────────────────────────────────────────┐
│   PRIORITY_SCORE                                                 │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID                                           │
│   ├── base_priority: enum (critical=100, high=70, med=40, low=10)│
│   ├── urgency_multipliers: JSON                                 │
│   │   ├── sla_factor: float (1.0 - 3.0)                        │
│   │   ├── vip_factor: float (1.0 or 1.5)                       │
│   │   ├── escalation_factor: float                             │
│   │   └── staleness_factor: float                              │
│   ├── calculated_score: float (auto-computed)                   │
│   └── last_calculated: datetime                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Reminder System

```
┌─────────────────────────────────────────────────────────────────┐
│   REMINDER                                                       │
│   ├── id: UUID                                                  │
│   ├── ticket_id: UUID                                           │
│   ├── agent_id: UUID                                            │
│   ├── type: enum (follow_up, check_in, custom, sla_warning)     │
│   ├── trigger_at: datetime                                      │
│   ├── message: string                                           │
│   ├── status: enum (pending, triggered, snoozed, completed)     │
│   ├── snooze_until: datetime?                                   │
│   └── recurring: RecurringConfig?                               │
│                                                                  │
│   RECURRING_CONFIG                                               │
│   ├── frequency: enum (daily, weekly, monthly)                  │
│   ├── interval: int (every N frequency)                         │
│   └── end_date: datetime?                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Notification Preferences

```
┌─────────────────────────────────────────────────────────────────┐
│   NOTIFICATION_PREFERENCE                                        │
│   ├── agent_id: UUID                                            │
│   ├── event_type: enum (assigned, escalation, sla_warn, etc.)   │
│   ├── channel: enum (email, teams, in_app, push, digest)        │
│   ├── timing: enum (immediate, hourly_digest, daily_digest)     │
│   └── quiet_hours: { start: time, end: time }?                  │
│                                                                  │
│   NOTIFICATION_QUEUE                                             │
│   ├── id: UUID                                                  │
│   ├── agent_id: UUID                                            │
│   ├── event_type: enum                                          │
│   ├── ticket_id: UUID                                           │
│   ├── channel: enum                                             │
│   ├── payload: JSON                                             │
│   ├── scheduled_for: datetime                                   │
│   ├── sent_at: datetime?                                        │
│   └── batch_id: UUID? (for digest grouping)                     │
└─────────────────────────────────────────────────────────────────┘
```

### Kanban Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│   KANBAN_VIEW                                                    │
│   ├── id: UUID                                                  │
│   ├── name: string                                              │
│   ├── owner_id: UUID? (null = team view)                        │
│   ├── team_id: UUID?                                            │
│   ├── column_field: enum (status, priority, team, agent)        │
│   ├── swimlane_field: enum? (optional second dimension)         │
│   ├── filters: JSON (saved filter criteria)                     │
│   ├── wip_limits: { column_value: max_count }                   │
│   └── sort_by: enum (priority_score, created_at, sla_breach)    │
└─────────────────────────────────────────────────────────────────┘
```

## Key Services (Extended)

### PriorityService

```python
class PriorityService:
    def calculate_score(ticket) -> float:
        """
        Dynamic priority calculation:
        score = base_priority × Π(urgency_multipliers)
        """
        base = ticket.priority.value  # 10-100
        
        multipliers = [
            self.sla_multiplier(ticket),      # 1.0 - 3.0
            self.vip_multiplier(ticket),       # 1.0 or 1.5
            self.escalation_multiplier(ticket),# 1.0 - 1.3
            self.staleness_multiplier(ticket), # 1.0 - 1.4
        ]
        
        return base * reduce(lambda a, b: a * b, multipliers)
    
    def get_work_queue(agent_id) -> List[Ticket]:
        """Returns tickets sorted by calculated priority score."""
```

### ReminderService

```python
class ReminderService:
    async def create_reminder(ticket_id, agent_id, trigger_at, message) -> Reminder:
        """Agent schedules a follow-up."""
        
    async def create_sla_warning(ticket) -> Reminder:
        """System auto-creates SLA approach warning."""
        
    async def snooze(reminder_id, duration_minutes) -> Reminder:
        """Snooze reminder for later."""
        
    async def get_due_reminders(agent_id) -> List[Reminder]:
        """Get overdue + upcoming reminders for dashboard."""
```

### NotificationService

```python
class NotificationService:
    async def notify(agent_id, event_type, ticket_id, payload):
        """
        Routes notification based on agent preferences.
        Handles: email, teams, in_app, push, digest batching.
        """
        prefs = await self.get_preferences(agent_id, event_type)
        
        if prefs.timing == "immediate":
            await self.send_immediate(prefs.channel, payload)
        else:
            await self.queue_for_digest(agent_id, prefs.timing, payload)
    
    async def send_teams_message(agent_id, message):
        """Send via MS Teams webhook/bot."""
        
    async def send_digest(agent_id, period: "hourly" | "daily"):
        """Bundle queued notifications into single message."""
```

### KanbanService

```python
class KanbanService:
    async def get_board(view_id) -> KanbanBoard:
        """Load board with all columns and cards."""
        
    async def move_card(ticket_id, from_column, to_column) -> Ticket:
        """
        Move ticket between columns.
        Validates: permissions, WIP limits, valid transitions.
        """
        
    async def save_view(agent_id, config) -> KanbanView:
        """Save personal or team view configuration."""
```

### ResolutionService (Sony Empowerment Pattern)

```python
class ResolutionService:
    async def create_resolution(
        ticket_id, 
        what_went_wrong, 
        why_eligible, 
        resolution_type, 
        amount=None
    ) -> Resolution:
        """
        Create resolution with empowerment check.
        Auto-determines tier based on amount vs team limits.
        Routes for approval if needed.
        """
        tier = self.determine_tier(agent, amount)
        
        if tier == EmpowermentTier.AGENT:
            # Agent discretion - just document
            return await self.save_resolution(...)
        elif tier == EmpowermentTier.TEAM_LEAD:
            # Create approval request
            return await self.request_approval(...)
        else:
            # Tier 3 - auto-flagged for calibration
            resolution = await self.save_resolution(...)
            await self.create_calibration_item(resolution)
            return resolution
    
    async def approve_resolution(resolution_id, approver_id) -> Resolution:
        """Team lead approves tier 2 resolution."""
```

### CalibrationService

```python
class CalibrationService:
    async def generate_weekly_queue() -> List[CalibrationItem]:
        """
        Auto-generates calibration queue:
        - All tier 3 resolutions
        - All flagged cases (physical_damage, social_media)
        - Random sample from tier 1-2
        - Cases with customer complaints
        """
        
    async def review_item(item_id, outcome, notes) -> CalibrationItem:
        """Record calibration review outcome."""
        
    async def get_calibration_report(period) -> CalibrationReport:
        """
        Returns:
        - Decisions upheld %
        - Compensation by agent/team/reason
        - Trend analysis
        """
```

### CaseFlagService

```python
class CaseFlagService:
    async def add_flag(ticket_id, flag_type, reason) -> CaseFlag:
        """Add special handling flag to ticket."""
        
        # Some flags have side effects
        if flag_type == FlagType.SOCIAL_MEDIA:
            await self.notify_manager(ticket_id)
            await self.upgrade_sla(ticket_id)
        elif flag_type == FlagType.LEGAL:
            await self.create_legal_envelope(ticket_id)
    
    async def detect_repeat_contact(ticket_id) -> bool:
        """Auto-flag if 3+ contacts on same issue."""
```

## Session State

```yaml
session_id: "engine-bootstrap"
phase: "modeling"
progress: 0.3

current_focus: "Extended feature set"

decisions_made:
  - Owner is immutable after accept()
  - Escalation creates parallel thread (envelope pattern)
  - Timeline entries have visibility scoping
  - Priority is dynamically calculated (base × multipliers)
  - Notifications route to Teams by default (not email spam)
  - Reminders are first-class entities
  
open_questions:
  - How to handle owner termination mid-ticket?
  - SLA pause rules during escalation?
  - Escalation to external (vendor)?
  - Teams bot vs webhook for notifications?
  - Kanban WIP limit enforcement (soft vs hard)?

next_steps:
  - [ ] Define API contracts
  - [ ] Implement Ticket aggregate root
  - [ ] Implement EscalationService
  - [ ] Implement PriorityService
  - [ ] Implement ReminderService
  - [ ] Implement NotificationService (Teams connector)
  - [ ] Rules engine scaffold
```

## Tech Stack (Proposed)

```
Language: Python 3.11+ or Go 1.21+
Framework: FastAPI or Gin
Database: PostgreSQL 15+
Queue: Redis (Upstash) for events
Cache: Redis (Upstash)
Search: PostgreSQL full-text (start simple)
```

## Integration Points

- **itil-next-connectors/msgraph**: Email sync via MS Graph
- **itil-next-connectors/hubspot**: Contact/Company enrichment
- **itil-next (orchestrator)**: Event hooks for meta-agi capture
