# Memoir Platform

A modular, event-driven platform for collecting life stories and creating personalized documents.

**Core Philosophy: Content is primary, documents are projections.**

## The Problem

People want to create autobiographies, biographies, birthday tributes, retirement gifts, and more. These all follow the same pattern:

1. **Collect** content from contributors (voice, forms, photos)
2. **Generate** documents as computed views of that content
3. **Evolve** documents as more content arrives
4. **Export** to various formats

## The Key Insight

**Content is the source of truth. Documents are projections.**

```
┌───────────────────────────────────────────────────────────────┐
│                      CONTENT POOL                              │
│  All collected content: voice recordings, form answers, etc.   │
│  Source of truth. Append-only. Fully tracked by contributor.  │
└───────────────────────────────────────────────────────────────┘
                              │
                              │ generate / update / evolve
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DOCUMENT PROJECTIONS                          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Full Memoir  │  │   Summary    │  │  Print-Ready Book    │   │
│  │  (thematic)  │  │(chronological)│  │   (comprehensive)    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  • Each projection is a computed view with version history       │
│  • Sections can be LOCKED to preserve manual edits               │
│  • Multiple UPDATE MODES: evolve, regenerate, refresh, append    │
│  • Multiple projections from same content                        │
└─────────────────────────────────────────────────────────────────┘
```

## Update Modes

When new content arrives, you can update projections in different ways:

| Mode | Description | Use Case |
|------|-------------|----------|
| **evolve** | Integrate new content while preserving structure | Default mode - graceful updates |
| **regenerate** | Fully regenerate unlocked sections | Major content overhaul |
| **refresh** | Only update sections with new relevant content | Minimal changes |
| **append** | Add new content to existing sections | Preserve everything, just add |

## Section Locking

Users can **lock sections** they've approved or edited:

```
📄 Grandma's Life Story

  🔒 Family (locked)       ← Won't change even if content changes
  🔒 Education (locked)    ← User manually edited this one
  🔄 Career (v3)           ← Will update with new content
```

This gives users control while keeping AI capabilities available.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRODUCT DEFINITION (YAML)                    │
│    resources, phases, projections, services, notifications       │
└─────────────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ↓                     ↓                     ↓
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │ RESOURCES │        │ SERVICES  │        │INTERFACES │
   │ questions │        │ projection│        │ voice_rec │
   │ prompts   │        │ phase_mgr │        │ web_form  │
   │ templates │        │ q_select  │        │ pdf_export│
   └───────────┘        │ notifier  │        └───────────┘
                        └───────────┘
                               │
                        ┌──────┴──────┐
                        │  EVENT BUS  │
                        └─────────────┘
```

## Project Structure

```
memoir/
├── core/
│   ├── models.py         # Project, Contributor, ContentItem
│   ├── projections.py    # DocumentProjection, NarrativeContext
│   ├── events.py         # EventBus
│   ├── registry.py       # Service/Resource registry
│   └── utils.py          # Shared utilities
├── services/
│   ├── projection.py     # Generate/update/evolve documents
│   ├── phase_manager.py  # Phase unlocking and progression
│   ├── question_selector.py
│   └── notification.py
├── products/
│   ├── config.py         # Configuration dataclasses
│   ├── loader.py         # Load YAML product definitions
│   └── executor.py       # Orchestrate product execution
└── config/
    └── products/         # monthly_life_story.yaml, etc.
```

## Quick Start

```bash
pip install -e .

# See the projections model in action
python -m memoir.demo_projections

# See phased product flow
python -m memoir.demo_phased
```

## API Server

Start the API:

```bash
uv sync
.venv/bin/uvicorn memoir.api.app:app --reload
```

Then visit http://localhost:8000/docs for Swagger UI.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/projects` | POST | Create a project |
| `/content` | POST | Add content to a project |
| `/transcribe` | POST | Upload audio → Whisper transcription |
| `/form/answer` | POST | Submit single Q&A |
| `/form/batch` | POST | Submit multiple Q&A pairs |
| `/projections` | POST | Generate a projection |
| `/projections/{id}` | GET | Get a projection |
| `/projections/{id}/update-options` | GET | Get available update options |
| `/projections/{id}/update` | POST | Update with specified mode |
| `/projections/{id}/regenerate` | POST | Full regeneration |
| `/projections/lock-section` | POST | Lock a section |
| `/projections/edit-section` | POST | Edit + optionally lock |
| `/projections/revert-section` | POST | Revert to previous version |
| `/projections/{id}/section/{sid}/history` | GET | Section version history |

### Example: Update a Projection

```bash
# Evolve: integrate new content gracefully
curl -X POST http://localhost:8000/projections/doc_123/update \
  -H "Content-Type: application/json" \
  -d '{"mode": "evolve"}'

# Regenerate: full regeneration of unlocked sections
curl -X POST http://localhost:8000/projections/doc_123/update \
  -H "Content-Type: application/json" \
  -d '{"mode": "regenerate"}'

# Refresh: only update stale sections
curl -X POST http://localhost:8000/projections/doc_123/update \
  -H "Content-Type: application/json" \
  -d '{"mode": "refresh"}'

# Update specific sections only
curl -X POST http://localhost:8000/projections/doc_123/update \
  -H "Content-Type: application/json" \
  -d '{"mode": "evolve", "section_ids": ["sec_abc123"]}'
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Content Pool** | All collected content – the source of truth |
| **Projection** | A document view computed from content (versionable, evolvable) |
| **Section Lock** | Freeze a section to preserve approved/edited content |
| **Update Mode** | How to integrate new content (evolve, regenerate, refresh, append) |
| **Narrative Context** | AI's understanding of themes, facts, and story so far |
| **Product** | YAML config wiring resources, services, interfaces |
| **Phase** | Stage in a multi-part journey with unlock conditions |

## Product Definition

```yaml
product: monthly_life_story
name: "Your Life Story - A Year-Long Journey"

# Content collection phases
phases:
  - id: early_years
    name: "The Early Years"
    questions_filter:
      categories: [early_childhood, family]
    unlock: immediate

  - id: school_days
    name: "School Days"
    unlock:
      type: scheduled
      delay_days: 30
      requires: early_years

# Document outputs (projections)
output:
  allow_section_locking: true
  allow_manual_edits: true
  show_update_options: true
  
  projections:
    - id: full_memoir
      name: "Complete Life Story"
      style: thematic
      length: comprehensive
      is_default: true
      default_update_mode: evolve
      suggested_sections:
        - Early Roots
        - Growing Up
        - Building a Life
      
    - id: summary
      name: "Story Summary"
      style: chronological
      length: summary
      auto_update: true
      default_update_mode: refresh

# How to collect content
collection:
  interfaces:
    - voice_recorder
    - web_form
```

## Projection Styles

| Style | Description |
|-------|-------------|
| `thematic` | Sections grouped by theme (AI discovers themes) |
| `chronological` | Time-ordered narrative |
| `by_contributor` | Each contributor gets a section |
| `questions` | Organized by questions asked |
| `freeform` | AI decides structure |

## AI Integration (DSPy + Gemini)

Uses [DSPy](https://dspy.ai/) for structured AI calls with Gemini 2.5 models.

```python
from memoir.services.ai import MemoirAI, configure_lm

configure_lm()  # Uses GOOGLE_API_KEY from env
ai = MemoirAI()

# Generate a memoir section
result = ai.generate_section(
    title="Early Childhood",
    content="I grew up on a farm in Iowa...",
    style="warm and nostalgic",
)

# Extract themes from content
themes = ai.extract_themes(content)

# Evolve a section with new content
updated = ai.regenerate_section(
    title="Family",
    existing_content="The original section...",
    new_content="New memories shared...",
)
```

## What's Implemented

- ✅ **Content Pool** – source of truth model
- ✅ **Document Projections** – computed views with version history
- ✅ **Section Locking** – preserve approved content
- ✅ **Multiple Update Modes** – evolve, regenerate, refresh, append
- ✅ **Section Version History** – track changes, revert if needed
- ✅ **Narrative Context** – AI memory for coherent storytelling
- ✅ **Multiple Projections** – summary, full, print-ready from same content
- ✅ **AI generation** – DSPy + Gemini for real prose
- ✅ **Event-driven architecture** – pub/sub event bus
- ✅ **Phased journeys** – time-gated content collection
- ✅ **YAML product definitions**
- ✅ **Contributor tracking** – full provenance
- ✅ **Multi-contributor merging** – weave perspectives from subject, family, friends
- ✅ **Authorization system** – role + tier based capability checking
- ✅ **Multilingual support** – LLM-powered translation with caching

## Authorization

Clean, minimal-overhead auth using a single dependency:

```python
from memoir.auth import require, AuthContext

@app.get("/projects/{project_id}/content")
async def get_content(
    project_id: str,
    ctx: AuthContext = Depends(require("content.read")),  # ← One line!
):
    items = await get_items(project_id)
    return {
        "items": items,
        "can_edit": ctx.can("content.edit"),  # Check permissions in logic
    }
```

**Project Roles**: `owner` → `admin` → `editor` → `contributor` → `viewer`

**User Tiers**: `free` → `pro` → `enterprise` (for paid features)

**Capabilities** are derived from role + tier automatically.

## Translation

LLM-powered translation with hash-based caching:

```python
from memoir.i18n import translate, translate_projection

# Simple text
spanish = await translate("Hello world", target="es")

# With context (better quality)
french = await translate(
    "She passed away in 2010",
    target="fr",
    context="life story memoir"
)

# Entire document
translated_doc = await translate_projection(projection, target="de")
```

**API endpoints:**
- `GET /languages` – list supported languages
- `POST /translate` – translate text
- `GET /projections/{id}/translate/{lang}` – get translated document

**50+ languages supported** (all major LTR languages):
- **Tier 1 (warm-up):** ES, FR, DE, PT, ZH, JA, KO, IT, RU, NL, PL, VI
- **European:** SV, NO, DA, FI, EL, CS, HU, RO, UK, and more
- **Asian:** ZH-TW, TH, ID, MS, TL, and Indian languages
- **RTL supported:** AR, HE, FA, UR (not in warm-up)

**Cache warm-up** (run on deploy):
```bash
python -m memoir.i18n.warmup           # Priority languages
python -m memoir.i18n.warmup --all     # All languages
```

## Infrastructure & Deployment

Full AWS infrastructure as code using Terraform.

👉 **See [DEPLOY.md](DEPLOY.md) for the complete deployment guide.**

Quick overview:

| Service | Purpose |
|---------|---------|
| App Runner | FastAPI hosting (auto-scaling) |
| RDS PostgreSQL | Database |
| S3 | Content storage |
| DynamoDB | Caching |
| CloudFront | CDN |

**Cost**: ~$50-75/month (dev), ~$150-300/month (prod)

## What's Next

- [ ] Output interfaces (PDF, web viewer)
- [ ] JWT token validation
- [ ] Real-time collaboration
- [ ] Frontend application
