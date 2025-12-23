# Architecture Documentation

## Design Principles

1. **Configuration over Code** - New products should be creatable via YAML, not Python
2. **Event-Driven** - Components communicate via events, enabling loose coupling and scalability
3. **Contributor-Centric** - Every piece of content is traceable to a contributor
4. **Pluggable** - Services, interfaces, and resources can be swapped without affecting others
5. **Scalable** - Design for distributed deployment from day one

---

## Event System

The event bus is the nervous system of the platform. Components emit events and subscribe to events they care about.

### Event Types

```
content.created          # New content item added
content.updated          # Content item modified
content.deleted          # Content item removed

project.created          # New project started
project.updated          # Project settings changed
project.status_changed   # Project moved to new phase

contributor.joined       # New contributor added to project
contributor.submitted    # Contributor submitted content

question.requested       # System needs next question
question.selected        # Question was chosen
question.answered        # Question received an answer

processing.started       # Processing pipeline began
processing.step_complete # A pipeline step finished
processing.complete      # Full pipeline finished
processing.failed        # Pipeline encountered error

export.requested         # Export was requested
export.complete          # Export finished
export.failed            # Export failed
```

### Event Structure

```python
@dataclass
class Event:
    event_type: str           # e.g., "content.created"
    timestamp: datetime
    project_id: str
    contributor_id: str | None
    payload: dict             # Event-specific data
    correlation_id: str       # For tracing related events
    causation_id: str | None  # Event that caused this one
```

### Subscription Patterns

Services can subscribe to events with filters:

```python
# Subscribe to all content events for a specific project
event_bus.subscribe("content.*", handler, filter={"project_id": "proj_123"})

# Subscribe to question events
event_bus.subscribe("question.*", question_service.handle)
```

---

## Data Models

### Project

A project is the top-level container for a memoir/tribute/etc.

```python
@dataclass
class Project:
    id: str
    name: str
    product_id: str              # Which product definition
    owner_id: str                # User who created it
    subject: Subject             # Who/what the memoir is about
    status: ProjectStatus        # draft, collecting, processing, complete
    settings: dict               # Product-specific settings
    created_at: datetime
    updated_at: datetime
```

### Contributor

A contributor is someone providing content to a project.

```python
@dataclass
class Contributor:
    id: str
    project_id: str
    user_id: str | None          # None for anonymous contributors
    name: str
    email: str | None
    relationship: str | None     # "friend", "family", "colleague"
    permissions: list[str]       # What they can do
    invite_token: str | None     # For invite links
    status: ContributorStatus    # invited, active, completed
    created_at: datetime
```

### ContentItem

A single piece of content with full provenance.

```python
@dataclass
class ContentItem:
    id: str
    project_id: str
    contributor_id: str
    
    # Content
    content_type: ContentType    # text, image, audio, structured_qa
    content: dict                # Type-specific content
    
    # Provenance
    source_interface: str        # "voice_recorder", "web_form", etc.
    source_metadata: dict        # Interface-specific metadata
    
    # Organization
    tags: list[str]
    question_id: str | None      # If in response to a question
    
    # Versioning
    version: int
    previous_version_id: str | None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### Content Types

```python
# Text content
{
    "type": "text",
    "text": "When I was seven years old...",
    "language": "en"
}

# Structured Q&A
{
    "type": "structured_qa",
    "question_id": "q_first_memory",
    "question_text": "What's your earliest memory?",
    "answer_text": "I remember the smell of my grandmother's kitchen..."
}

# Image
{
    "type": "image",
    "url": "s3://bucket/images/photo_123.jpg",
    "description": "Family gathering, Christmas 1985",
    "ocr_text": null
}

# Audio (raw, pre-transcription)
{
    "type": "audio",
    "url": "s3://bucket/audio/recording_456.webm",
    "duration_seconds": 145,
    "transcription_id": "content_789"  # Link to transcribed version
}
```

---

## Services

### Service Interface

All services implement a common interface:

```python
class Service(ABC):
    service_id: str
    
    @abstractmethod
    async def handle(self, event: Event) -> list[Event]:
        """Process an event and return resulting events."""
        pass
    
    @property
    @abstractmethod
    def subscribes_to(self) -> list[str]:
        """Event patterns this service handles."""
        pass
```

### Service Registry

Services register themselves and their capabilities:

```python
registry.register_service(
    service_id="transcription",
    service_class=TranscriptionService,
    config_schema={...}
)
```

### Example: QuestionSelector Service

```python
class QuestionSelectorService(Service):
    service_id = "question_selector"
    subscribes_to = ["question.requested"]
    
    async def handle(self, event: Event) -> list[Event]:
        project_id = event.project_id
        contributor_id = event.contributor_id
        
        # Get strategy from project's product config
        strategy = self.get_strategy(project_id)
        
        # Get context
        previous_answers = await self.store.get_answers(project_id, contributor_id)
        question_bank = await self.resources.get_question_bank(project_id)
        
        # Select next question
        if strategy == "sequential":
            question = self.select_sequential(question_bank, previous_answers)
        elif strategy == "random":
            question = self.select_random(question_bank, previous_answers)
        elif strategy == "ai_adaptive":
            question = await self.select_ai_adaptive(question_bank, previous_answers)
        elif strategy == "ai_generative":
            question = await self.generate_question(previous_answers)
        
        return [Event(
            event_type="question.selected",
            project_id=project_id,
            contributor_id=contributor_id,
            payload={"question": question.to_dict()},
            correlation_id=event.correlation_id,
            causation_id=event.id
        )]
```

---

## Interfaces

### Input Interface

```python
class InputInterface(ABC):
    interface_id: str
    
    @abstractmethod
    async def receive(self, raw_input: Any, context: InputContext) -> list[Event]:
        """Receive input and emit content events."""
        pass
```

### Output Interface

```python
class OutputInterface(ABC):
    interface_id: str
    
    @abstractmethod
    async def export(self, content: list[ContentItem], config: dict) -> ExportResult:
        """Export content to target format."""
        pass
```

---

## Resources

Resources are loaded from YAML files and cached.

### Question Bank

```yaml
# config/questions/birthday_memories.yaml
id: birthday_memories
name: "Birthday Memories"
version: 2
tags: [birthday, celebration, memories]

questions:
  - id: first_memory
    text: "What's your earliest memory of {subject}?"
    tags: [childhood, formative]
    follow_ups:
      - "Can you describe that moment in more detail?"
      - "How did that memory shape your relationship?"
  
  - id: funny_story
    text: "Tell me about a time {subject} made you laugh"
    tags: [humor, personality]
    
  - id: proud_moment
    text: "What's a moment when you felt really proud of {subject}?"
    tags: [achievement, emotion]
```

### Prompt Template

```yaml
# config/prompts/warm_nostalgic.yaml
id: warm_nostalgic
name: "Warm & Nostalgic"
version: 1

system_prompt: |
  You are a thoughtful writer creating a heartfelt tribute.
  Write with warmth, gentle humor, and emotional depth.
  Avoid being overly sentimental or flowery.
  Honor the authentic voice of the contributors.

generation_prompts:
  memoir:
    prompt: |
      Using these memories shared by friends and family,
      write a birthday tribute for {subject.name}.
      
      Memories:
      {content}
      
      Create a cohesive narrative that captures who {subject.name}
      is through the eyes of those who love them.
    
    parameters:
      temperature: 0.8
      max_tokens: 2000
```

---

## Product Definition

Products wire everything together:

```yaml
# config/products/birthday_tribute.yaml
product: birthday_tribute
name: "Birthday Memory Book"
description: "Collect memories for a birthday celebration"
version: 1

# Subject configuration
subject:
  required_fields: [name]
  optional_fields: [birth_date, photo]

# Resource references
resources:
  questions: birthday_memories
  prompts: warm_nostalgic
  document_template: celebration_book

# Collection phase
collection:
  interfaces:
    - voice_recorder
    - web_form
    - photo_upload
  
  question_selection:
    strategy: random  # sequential, random, ai_adaptive, ai_generative
    min_questions: 3
    max_questions: 10
  
  contributor_settings:
    allow_anonymous: true
    max_contributors: 50
    require_relationship: true

# Processing pipeline
processing:
  trigger: manual  # manual, auto_on_deadline, auto_on_threshold
  
  pipeline:
    - service: content_merger
      config:
        dedupe: true
        merge_similar: true
    
    - service: ai_writer
      config:
        prompt_ref: warm_nostalgic
        output_type: memoir
    
    - service: structurer
      config:
        template_ref: celebration_book

# Delivery options
delivery:
  interfaces:
    - web_viewer
    - pdf_export
  
  sharing:
    public_link: true
    password_protection: optional
    
# UI customization
ui:
  theme: celebration
  colors:
    primary: "#FF6B6B"
    secondary: "#4ECDC4"
```

---

## Execution Flow

### 1. Project Creation

```
User creates project with product "birthday_tribute"
    → project.created event
    → Project stored with product config loaded
    → Owner becomes first contributor
```

### 2. Content Collection

```
Contributor opens collection interface
    → question.requested event
    → QuestionSelector handles, emits question.selected
    → Interface displays question
    
Contributor records answer
    → Interface captures audio
    → Calls Transcription service
    → content.created event with transcribed text
    → question.answered event
    → question.requested event (cycle continues)
```

### 3. Processing

```
Owner triggers processing
    → processing.started event
    → Pipeline executor runs each service in sequence
    → Each service emits processing.step_complete
    → Final processing.complete event
```

### 4. Export

```
User requests PDF export
    → export.requested event
    → PDFExport interface generates document
    → export.complete event with download URL
```

---

## Scaling Considerations

### Event Bus

For production, replace in-memory event bus with:
- **Redis Pub/Sub** for single-region
- **Apache Kafka** for multi-region
- **AWS EventBridge** for serverless

### Storage

- **Content Store**: PostgreSQL with JSONB for flexibility
- **File Storage**: S3 or equivalent
- **Cache**: Redis for hot data

### Services

Services are stateless and can be:
- Scaled horizontally
- Deployed as separate containers/functions
- Rate-limited independently

### API

- REST API for synchronous operations
- WebSocket for real-time updates
- Webhook support for integrations

