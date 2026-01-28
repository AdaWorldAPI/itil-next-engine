# ITIL-NEXT Engine: Claude Code Guide

## This Repository

Core business logic for ITIL-NEXT ticket management. Pure Python, no framework dependencies in core.

## Architecture

```
src/
├── models/           # Pydantic data models
│   └── ticket.py     # Ticket, Envelope, Task, Timeline, etc.
│
├── services/         # Business logic (the brain)
│   ├── ownership.py  # THE CORE: Immutable ownership
│   ├── envelope.py   # Parallel assist (Amdocs pattern)
│   ├── alert.py      # Escalation matrix (SolarWinds)
│   ├── resolution.py # Empowerment tiers (Sony)
│   ├── priority.py   # Dynamic scoring
│   └── timeline.py   # Activity feed (HubSpot)
│
├── repositories/     # Data access (to implement)
│   └── ...           # Abstract repos, implementations
│
└── events/           # Domain events (to implement)
    └── ...           # For event sourcing/CQRS
```

## Key Services

### OwnershipService (THE INNOVATION)

```python
class OwnershipService:
    async def accept_ticket(ticket_id, agent_id) -> Ticket:
        """
        THE SACRED MOMENT: Set owner.
        After this, owner_id is IMMUTABLE.
        """
        
    async def validate_ownership(ticket_id, agent_id) -> bool:
        """Check if agent owns ticket."""
        
    async def transfer_ownership(...):
        """
        EXCEPTIONAL only: termination, extended leave.
        NOT for normal escalation.
        """
```

### EnvelopeService (Amdocs Pattern)

```python
class EnvelopeService:
    async def create_envelope(ticket_id, requested_by, reason, team_id=None):
        """
        1-click envelope creation.
        Owner stays owner, expert joins to help.
        """
        
    async def get_expert_view(agent_id, ticket_id) -> dict:
        """
        Sony tab pattern:
        - Main ticket (read-only)
        - My envelope (work here)
        - Can add next-level envelope
        """
```

### AlertService (SolarWinds Pattern)

```python
class AlertService:
    async def check_ticket_alerts(ticket_id) -> List[Alert]:
        """
        3 conditions × 3 levels:
        - NOT_ASSIGNED, NOT_UPDATED, NOT_COMPLETED
        - Progressive recipients: Tech → Super → Manager
        """
```

### ResolutionService (Sony Pattern)

```python
class ResolutionService:
    async def create_resolution(
        ticket_id,
        what_went_wrong,    # Documentation
        why_eligible,       # Justification
        resolution_type,
        amount=None         # Auto-routes by empowerment tier
    ):
        """
        Empowerment with accountability:
        - Agent: €100 discretion
        - Team Lead: €100-500
        - Manager: >€500 + calibration
        """
```

## Model Overview

```python
# Core entities
Ticket          # Customer request (HubSpot object)
Envelope        # Parallel assist (Amdocs sub-case)
Task            # Work item under ticket or envelope
TimelineEntry   # Activity (HubSpot engagement)

# Support entities
Contact         # Customer (HubSpot contact)
Company         # Organization (HubSpot company)
Agent           # Support agent
Team            # Agent group

# Enhancement entities
CaseFlag        # Special handling (Sony flags)
Resolution      # Compensation tracking (Sony)
```

## Adding New Features

1. **Model first**: Add to `src/models/`
2. **Service second**: Add to `src/services/`
3. **Repository if needed**: Abstract in `src/repositories/`
4. **Tests**: Mirror structure in `tests/`

## Business Rules (Enforce These)

1. **Ownership is sacred**
   - `owner_id` set once on accept
   - Cannot be changed except exceptional transfer
   - Escalation = envelope, NOT ownership transfer

2. **Envelopes are parallel, not serial**
   - Multiple envelopes can be active
   - Owner sees status, expert sees content
   - Expert can add next-level envelope

3. **Alerts escalate progressively**
   - Level 1: Nudge the tech
   - Level 2: Include supervisor
   - Level 3: Everyone (breach imminent)

4. **Empowerment has accountability**
   - Agents can resolve (within limits)
   - Document what/why/when/where
   - Calibration ensures consistency

## Testing

```bash
# Run all tests
pytest

# Run specific service tests
pytest tests/services/test_ownership.py -v

# With coverage
pytest --cov=src --cov-report=html
```

## Dependencies

```
pydantic>=2.0
python-dateutil
# Add as needed, keep minimal
```

## Related Repos

- `itil-next` - Orchestrator, documentation
- `itil-next-connectors` - External integrations
