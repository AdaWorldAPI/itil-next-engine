# ITIL-NEXT Engine

Core ticket system engine with patterns from:
- **Amdocs Ensemble** (KIAS/Vodafone) - Sub-case/envelope pattern
- **Sony/Sykes** - Empowerment tiers, tab UI, calibration
- **HubSpot** - Timeline engagements, associations
- **Anti-Valuemation** - Everything Valuemation does wrong, we do right

## Core Innovations

### 1. Sacred Ownership
```
Owner is IMMUTABLE after accept.
No ping-pong. No junkyard 2nd level.
Agent who accepts OWNS the outcome.
```

### 2. Envelope Pattern (Parallel Escalation)
```
Owner creates envelope → Expert works in envelope → Owner closes
Customer sees: One agent handling their issue
Reality: Multiple experts contributed via envelopes
```

### 3. Empowerment Tiers (Sony)
```
Tier 1 (Agent):     Up to €100, just document
Tier 2 (Team Lead): €100-500, quick approval  
Tier 3 (Manager):   >€500, calibration review
```

### 4. Dynamic Priority Scoring
```
calculated_score = base_priority × urgency_multipliers

Medium (40) × SLA<4h (2.0) × VIP (1.5) = 120
This ranks HIGHER than High base (70)
```

## Structure

```
src/
├── models/
│   └── ticket.py      # Core data models
├── services/
│   ├── ownership.py   # Immutable ownership enforcement
│   ├── envelope.py    # Parallel escalation
│   ├── resolution.py  # Empowerment + calibration
│   ├── priority.py    # Dynamic scoring
│   └── timeline.py    # HubSpot-style activity feed
└── api/
    └── app.py         # FastAPI endpoints
```

## Quick Start

```bash
# Install
pip install -e .

# Run
uvicorn src.api.app:app --reload

# API docs
open http://localhost:8000/docs
```

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /tickets` | Create ticket |
| `POST /tickets/{id}/accept` | Accept ownership (SACRED) |
| `POST /tickets/{id}/envelopes` | Create envelope (1-click!) |
| `POST /envelopes/{id}/complete` | Complete envelope |
| `POST /tickets/{id}/resolutions` | Create resolution with empowerment |
| `GET /agents/{id}/work-queue` | Get prioritized work queue |
| `GET /calibration/queue` | Weekly calibration items |

## Philosophy

```
VALUEMATION: "Escalate" = "Get rid of this problem"
ITIL-NEXT:   "Escalate" = "Help me WITH this problem"

2nd level is not a junkyard.
2nd level is focused expertise.
```
