# Implementation Plan: Automatic AI Bot Generator from Visual Artifacts

## 1. High-Level Architecture

The system is split into **two fully decoupled FastAPI services**, each with its own PostgreSQL database, communicating via **Redis Streams** (event bus):

- **Main API** — owns users, bots, scenarios, corrections, deployments, chat. Serves the frontend.
- **Processing Service** — owns documents, knowledge chunks, processing jobs. Handles file upload and the full extraction/embedding pipeline.

Data that crosses service boundaries (knowledge chunks, scenarios, document metadata) is replicated via events. Each service is independently deployable and scalable.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           CLIENT (React SPA)                             │
│  ┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Upload │ │ Preview  │ │ Scenario  │ │ Sandbox  │ │  Deploy Panel │  │
│  │ Wizard │ │ Dashboard│ │  Editor   │ │ Chat UI  │ │  & Analytics  │  │
│  └────────┘ └──────────┘ └───────────┘ └──────────┘ └───────────────┘  │
└──────────┬─────────────────────────────────────────┬─────────────────────┘
           │  REST / WebSocket                       │  REST (upload)
           ▼                                        ▼
┌────────────────────────────┐             ┌──────────────────────────────┐
│    MAIN API (FastAPI)      │             │  PROCESSING SERVICE (FastAPI)│
│    Port 8000               │             │  Port 8001                   │
│                            │             │                              │
│  ┌──────────┐ ┌─────────┐ │             │  ┌──────────┐ ┌───────────┐  │
│  │ Auth     │ │Bot CRUD │ │             │  │ Upload   │ │ Processing│  │
│  │ Router   │ │Router   │ │             │  │ Router   │ │ Pipeline  │  │
│  ├──────────┤ ├─────────┤ │             │  ├──────────┤ ├───────────┤  │
│  │ Chat     │ │Scenarios│ │             │  │ Status   │ │ Scenario  │  │
│  │ Router   │ │Router   │ │             │  │ Router   │ │ Generator │  │
│  ├──────────┤ ├─────────┤ │             │  └──────────┘ └───────────┘  │
│  │ Deploy   │ │Correct. │ │             │                              │
│  │ Router   │ │Router   │ │             │  Uses BackgroundTasks for    │
│  └──────────┘ └─────────┘ │             │  heavy async processing      │
└─────────────┬──────────────┘             └──────────────┬───────────────┘
              │                                           │
              ▼                                           ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Main API DB     │  │  Processor DB    │  │  Object Storage  │
│  (PostgreSQL)    │  │  (PostgreSQL     │  │  (S3 / MinIO)    │
│                  │  │   + pgvector)    │  │  Uploaded files   │
│  • Users         │  │                  │  └──────────────────┘
│  • Bots          │  │  • Documents     │
│  • Scenarios     │  │  • KnowledgeChunk│  ┌──────────────────┐
│  • Corrections   │  │  • ProcessingJob │  │  Redis 7         │
│  • Deployments   │  │                  │  │                  │
│  • ChatSessions  │  └──────────────────┘  │  • Event Bus     │
│  • ChatMessages  │                        │    (Streams)     │
│  • KnowledgeChunk│  ◄── replicated        │  • Cache         │
│    (replicated)  │      via events        └──────────────────┘
└──────────────────┘
```

### Inter-Service Communication (Redis Streams)

Services communicate exclusively via **Redis Streams** — a persistent, ordered event log with consumer group support. No direct HTTP calls between services.

```mermaid
sequenceDiagram
    participant FE as React Frontend
    participant API as Main API :8000
    participant RS as Redis Streams (Event Bus)
    participant PS as Processing Service :8001
    participant PDB as Processor DB
    participant ADB as Main API DB
    participant S3 as MinIO/S3

    FE->>PS: POST /process/bots/{bot_id}/documents (upload files)
    PS->>S3: Store files
    PS->>PDB: Create Document records (status=pending)
    PS-->>FE: 202 Accepted {task_id, document_ids}

    PS->>PS: BackgroundTask: run_pipeline()
    Note right of PS: OCR / PDF parse / chunk / embed
    PS->>PDB: Store KnowledgeChunks with embeddings
    PS->>PDB: Update Document.status = completed

    PS->>RS: XADD documents.processed {bot_id, doc_id, metadata}
    PS->>RS: XADD knowledge.chunks_created {bot_id, chunks: [...]}

    PS->>PS: Generate scenarios via LLM
    PS->>RS: XADD scenarios.generated {bot_id, scenarios: [...]}
    PS->>RS: XADD processing.completed {bot_id}

    Note over RS: Events are persistent — survives crashes

    RS-->>API: Consumer group reads events
    API->>ADB: Replicate document metadata
    API->>ADB: Store knowledge chunks (with embeddings)
    API->>ADB: Store generated scenarios
    API->>ADB: Update Bot.status = ready
    API->>FE: Notify via WebSocket/SSE
```

### Event Contracts

| Stream Name                | Publisher  | Consumer   | Payload                                                               |
| -------------------------- | ---------- | ---------- | --------------------------------------------------------------------- |
| `documents.processed`      | Processing | Main API   | `{bot_id, doc_id, filename, file_type, extracted_metadata, raw_text}` |
| `knowledge.chunks_created` | Processing | Main API   | `{bot_id, doc_id, chunks: [{content, embedding, metadata, index}]}`   |
| `scenarios.generated`      | Processing | Main API   | `{bot_id, scenarios: [{title, question, answer, tags}]}`              |
| `processing.completed`     | Processing | Main API   | `{bot_id, status, document_count, chunk_count}`                       |
| `processing.failed`        | Processing | Main API   | `{bot_id, error, failed_doc_id}`                                      |
| `bot.created`              | Main API   | Processing | `{bot_id, name, description, settings}`                               |
| `bot.deleted`              | Main API   | Processing | `{bot_id}`                                                            |

---

## 2. Technology Stack

### Backend

| Component     | Technology                                  | Purpose                             |
| ------------- | ------------------------------------------- | ----------------------------------- |
| Web Framework | **FastAPI** (0.115+)                        | Async REST API + WebSocket support  |
| ORM           | **SQLAlchemy 2.0** (async)                  | Database models & queries           |
| Migrations    | **Alembic**                                 | Schema versioning (per service)     |
| Database      | **PostgreSQL 16** + **pgvector**            | Separate DB per service             |
| Event Bus     | **Redis Streams**                           | Inter-service pub/sub (persistent)  |
| Cache         | **Redis**                                   | Session cache, rate limiting        |
| File Storage  | **MinIO** (S3-compatible)                   | Uploaded artifacts storage          |
| Auth          | **JWT** (python-jose) + **bcrypt**          | Token-based authentication          |
| AI / LLM      | **OpenAI API** (GPT-4o / GPT-4o-mini)       | Vision, text generation, embeddings |
| OCR Fallback  | **Tesseract** via pytesseract               | Offline OCR for images              |
| PDF Parsing   | **PyMuPDF** (fitz) + **pdfplumber**         | Text/table extraction from PDFs     |
| Validation    | **Pydantic v2**                             | Request/response schemas            |
| Testing       | **pytest** + **pytest-asyncio** + **httpx** | Unit & integration tests            |

### Frontend

| Component   | Technology                             | Purpose                             |
| ----------- | -------------------------------------- | ----------------------------------- |
| Framework   | **React 18** (Vite)                    | SPA with fast HMR                   |
| Language    | **TypeScript**                         | Type safety                         |
| Routing     | **React Router v6**                    | Client-side routing                 |
| State       | **Zustand**                            | Lightweight global state            |
| HTTP Client | **Axios** + **React Query (TanStack)** | API calls + caching                 |
| WebSocket   | **socket.io-client**                   | Real-time chat & processing updates |
| UI Library  | **Ant Design** or **Shadcn/ui**        | Polished component library          |
| File Upload | **react-dropzone**                     | Drag & drop multimodal upload       |
| Rich Text   | **TipTap**                             | Scenario/answer editing             |
| Chat UI     | Custom component                       | Sandbox chat interface              |
| Code Embed  | **react-syntax-highlighter**           | Widget embed code display           |
| Charts      | **Recharts**                           | Analytics dashboard                 |

### Infrastructure (Docker Compose for dev)

| Service      | Image                  | Ports      | Description                            |
| ------------ | ---------------------- | ---------- | -------------------------------------- |
| api          | Custom (FastAPI)       | 8000       | Main API — auth, bots, chat, deploy    |
| processor    | Custom (FastAPI)       | 8001       | Processing Service — upload & pipeline |
| frontend     | Custom (Vite/Nginx)    | 3000       | React SPA                              |
| api-db       | postgres:16            | 5432       | Main API database                      |
| processor-db | postgres:16 + pgvector | 5433       | Processing Service database            |
| redis        | redis:7-alpine         | 6379       | Event bus (Streams) + cache            |
| minio        | minio/minio            | 9000, 9001 | Object storage for uploads             |

---

## 3. Project Structure

### Events Contract (`/events`)

Since there is no shared database, services share only **event schemas** — a lightweight package defining the Pydantic models for Redis Stream messages:

```
events/
├── __init__.py
├── streams.py                  # Stream name constants
├── processing.py               # Events published by Processing Service
│   # DocumentProcessed, ChunksCreated, ScenariosGenerated,
│   # ProcessingCompleted, ProcessingFailed
├── api.py                      # Events published by Main API
│   # BotCreated, BotDeleted
└── pyproject.toml              # Installable as: pip install -e ./events
```

### Main API Service (`/services/api`)

```
services/api/
├── alembic/                    # Main API migrations (its own DB)
│   ├── versions/
│   └── env.py
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory & lifespan (starts event consumer)
│   ├── config.py               # Settings (API DB URL, Redis, JWT, etc.)
│   ├── database.py             # Async engine & session factory
│   │
│   ├── models/                 # SQLAlchemy models (Main API DB only)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── bot.py
│   │   ├── scenario.py
│   │   ├── correction.py
│   │   ├── deployment.py
│   │   ├── chat_session.py
│   │   ├── document_ref.py     # Lightweight replica of Processing's document metadata
│   │   └── knowledge_chunk.py  # Replicated from Processing via events (with embeddings)
│   │
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── bot.py
│   │   ├── scenario.py
│   │   ├── chat.py
│   │   └── deployment.py
│   │
│   ├── api/                    # Route handlers
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependency injection (get_db, get_current_user)
│   │   ├── auth.py
│   │   ├── bots.py
│   │   ├── documents.py        # Read-only: queries replicated document_ref table
│   │   ├── scenarios.py
│   │   ├── chat.py             # WebSocket /bots/{id}/chat
│   │   ├── corrections.py
│   │   └── deployments.py
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── bot_service.py
│   │   ├── chat_service.py     # RAG engine (queries local knowledge_chunk table)
│   │   ├── correction_service.py
│   │   └── deployment_service.py
│   │
│   ├── consumers/              # Redis Streams event consumers
│   │   ├── __init__.py
│   │   ├── consumer.py         # Base consumer with consumer group logic
│   │   └── processing_consumer.py  # Handles events from Processing Service
│   │
│   ├── publishers/             # Redis Streams event publishers
│   │   ├── __init__.py
│   │   └── bot_publisher.py    # Publishes bot.created, bot.deleted
│   │
│   └── utils/
│       ├── security.py
│       ├── storage.py          # S3 client (read-only, for widget assets)
│       └── llm.py              # OpenAI client (for chat)
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_bots.py
│   ├── test_chat.py
│   └── test_consumers.py
│
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### Processing Service (`/services/processor`)

```
services/processor/
├── alembic/                    # Processing Service migrations (its own DB)
│   ├── versions/
│   └── env.py
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory & lifespan (starts event consumer)
│   ├── config.py               # Settings (Processor DB URL, Redis, S3, OpenAI)
│   ├── database.py             # Async engine & session factory
│   │
│   ├── models/                 # SQLAlchemy models (Processor DB only)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── document.py
│   │   ├── knowledge_chunk.py  # Source of truth — with pgvector embeddings
│   │   └── processing_job.py   # Tracks pipeline execution per bot
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── upload.py
│   │   └── status.py
│   │
│   ├── api/                    # Route handlers
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── upload.py           # POST /process/bots/{id}/documents
│   │   └── status.py           # GET /process/bots/{id}/status (SSE)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Orchestrator — runs full processing flow
│   │   ├── processors/
│   │   │   ├── __init__.py
│   │   │   ├── image_processor.py
│   │   │   ├── pdf_processor.py
│   │   │   ├── text_processor.py
│   │   │   └── presentation_processor.py
│   │   ├── embedder.py
│   │   └── scenario_generator.py
│   │
│   ├── consumers/              # Listens for events from Main API
│   │   ├── __init__.py
│   │   └── bot_consumer.py     # Handles bot.created, bot.deleted
│   │
│   ├── publishers/             # Publishes processing events
│   │   ├── __init__.py
│   │   └── processing_publisher.py
│   │
│   └── utils/
│       ├── storage.py          # S3 client (upload & download)
│       ├── llm.py              # OpenAI client (Vision, embeddings, generation)
│       └── file_detection.py
│
├── tests/
│   ├── conftest.py
│   ├── test_upload.py
│   ├── test_processing.py
│   └── test_pipeline.py
│
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### Root project structure

```
chatbot/
├── docs/
│   ├── idea.md
│   └── implementation_plan.md
├── events/                     # Shared event schemas (Pydantic models only)
├── services/
│   ├── api/                    # Main API service (own DB, own Alembic)
│   └── processor/              # Processing service (own DB, own Alembic)
├── frontend/                   # React SPA
├── docker-compose.yml
├── .env.example
└── README.md
```

### Frontend (`/frontend`)

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── router.tsx              # React Router config
│   │
│   ├── api/                    # API client layer
│   │   ├── client.ts           # Axios instance + interceptors
│   │   ├── auth.ts
│   │   ├── bots.ts
│   │   ├── documents.ts
│   │   ├── scenarios.ts
│   │   ├── chat.ts
│   │   └── deployments.ts
│   │
│   ├── stores/                 # Zustand stores
│   │   ├── authStore.ts
│   │   ├── botStore.ts
│   │   └── chatStore.ts
│   │
│   ├── hooks/                  # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useBot.ts
│   │   ├── useChat.ts
│   │   └── useWebSocket.ts
│   │
│   ├── components/             # Reusable components
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx
│   │   ├── Upload/
│   │   │   ├── DropZone.tsx
│   │   │   ├── FilePreview.tsx
│   │   │   └── ProcessingProgress.tsx
│   │   ├── Scenarios/
│   │   │   ├── ScenarioCard.tsx
│   │   │   ├── ScenarioEditor.tsx
│   │   │   └── ScenarioList.tsx
│   │   ├── Chat/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── ChatInput.tsx
│   │   ├── Deploy/
│   │   │   ├── DeployPanel.tsx
│   │   │   ├── EmbedCodeBlock.tsx
│   │   │   └── IntegrationCard.tsx
│   │   └── Common/
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   │
│   ├── pages/                  # Page-level components
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── BotCreatePage.tsx
│   │   ├── BotDetailPage.tsx
│   │   ├── ScenariosPage.tsx
│   │   ├── SandboxPage.tsx
│   │   ├── DeployPage.tsx
│   │   └── AnalyticsPage.tsx
│   │
│   ├── types/                  # TypeScript interfaces
│   │   ├── auth.ts
│   │   ├── bot.ts
│   │   ├── document.ts
│   │   ├── scenario.ts
│   │   └── chat.ts
│   │
│   └── styles/
│       ├── global.css
│       └── variables.css
│
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

---

## 4. Database Schema (Split by Service)

Each service owns its own database with its own Alembic migrations. IDs are UUIDs to enable cross-service references without foreign keys.

### Main API Database (`api_db`)

```mermaid
erDiagram
    USER ||--o{ BOT : owns
    BOT ||--o{ DOCUMENT_REF : has
    BOT ||--o{ KNOWLEDGE_CHUNK : has
    BOT ||--o{ SCENARIO : has
    SCENARIO ||--o{ CORRECTION : refined_by
    BOT ||--o{ DEPLOYMENT : deployed_as
    BOT ||--o{ CHAT_SESSION : interacts
    CHAT_SESSION ||--o{ CHAT_MESSAGE : contains

    USER {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        datetime created_at
        datetime updated_at
    }

    BOT {
        uuid id PK
        uuid user_id FK
        string name
        string description
        text system_prompt
        json settings
        enum status "draft|processing|ready|deployed"
        datetime created_at
        datetime updated_at
    }

    DOCUMENT_REF {
        uuid id PK "same ID as in Processor DB"
        uuid bot_id FK
        string original_filename
        enum file_type "image|pdf|text|csv|presentation"
        enum processing_status "pending|processing|completed|failed"
        json extracted_metadata
        datetime created_at
        datetime synced_at
    }

    KNOWLEDGE_CHUNK {
        uuid id PK "replicated from Processor"
        uuid document_ref_id
        uuid bot_id FK
        text content
        vector embedding "1536 dim - pgvector"
        json metadata
        int chunk_index
        datetime created_at
    }

    SCENARIO {
        uuid id PK
        uuid bot_id FK
        string title
        text customer_question
        text bot_answer
        json tags
        bool is_approved
        int sort_order
        enum source "generated|manual"
        datetime created_at
        datetime updated_at
    }

    CORRECTION {
        uuid id PK
        uuid scenario_id FK
        uuid bot_id FK
        text original_answer
        text corrected_answer
        text user_instruction
        datetime created_at
    }

    DEPLOYMENT {
        uuid id PK
        uuid bot_id FK
        enum channel "web_widget|telegram|whatsapp|api"
        json config
        string api_key UK
        bool is_active
        datetime created_at
        datetime updated_at
    }

    CHAT_SESSION {
        uuid id PK
        uuid bot_id FK
        uuid deployment_id FK
        string visitor_id
        datetime started_at
        datetime ended_at
    }

    CHAT_MESSAGE {
        uuid id PK
        uuid session_id FK
        enum role "user|assistant"
        text content
        json metadata
        float response_time_ms
        datetime created_at
    }
```

> **Note**: `DOCUMENT_REF` and `KNOWLEDGE_CHUNK` in the Main API DB are **replicas** — populated by consuming events from the Processing Service. The Main API never writes to these directly; it only reads them for chat (RAG) and displaying document lists. The Main API DB also needs `pgvector` extension for the replicated knowledge chunk embeddings.

### Processing Service Database (`processor_db`)

```mermaid
erDiagram
    DOCUMENT ||--o{ KNOWLEDGE_CHUNK : produces
    PROCESSING_JOB ||--o{ DOCUMENT : tracks

    DOCUMENT {
        uuid id PK
        uuid bot_id "references Main API bot - no FK"
        string original_filename
        string storage_key "S3 path"
        enum file_type "image|pdf|text|csv|presentation"
        enum processing_status "pending|processing|completed|failed"
        json extracted_metadata
        text raw_extracted_text
        datetime created_at
    }

    KNOWLEDGE_CHUNK {
        uuid id PK
        uuid document_id FK
        uuid bot_id
        text content
        vector embedding "1536 dim - pgvector"
        json metadata
        int chunk_index
        datetime created_at
    }

    PROCESSING_JOB {
        uuid id PK
        uuid bot_id
        enum status "pending|processing|completed|failed"
        int total_documents
        int processed_documents
        text error_message
        datetime started_at
        datetime completed_at
    }
```

> **Note**: `bot_id` in the Processor DB is a plain UUID — not a foreign key. The Processing Service trusts that the bot exists because it received the ID from the frontend (which got it from the Main API). If a bot is deleted, the Main API publishes `bot.deleted` and the Processing Service cleans up.

### Model Examples

#### Main API: Bot model (services/api)

```python
# services/api/app/models/bot.py

class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict | None] = mapped_column(JSON, default=dict)
    status: Mapped[BotStatus] = mapped_column(Enum(BotStatus), default=BotStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships (all within Main API DB)
    owner = relationship("User", back_populates="bots")
    document_refs = relationship("DocumentRef", back_populates="bot", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="bot", cascade="all, delete-orphan")
    knowledge_chunks = relationship("KnowledgeChunk", back_populates="bot", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="bot", cascade="all, delete-orphan")
```

#### Main API: Replicated KnowledgeChunk (for RAG queries)

```python
# services/api/app/models/knowledge_chunk.py

class KnowledgeChunk(Base):
    """Replicated from Processing Service via events. Read-only in Main API."""
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)  # Same ID as in Processor DB
    document_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict)
    chunk_index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bot = relationship("Bot", back_populates="knowledge_chunks")
```

#### Processing Service: Source-of-truth KnowledgeChunk

```python
# services/processor/app/models/knowledge_chunk.py

class KnowledgeChunk(Base):
    """Source of truth. Created during processing pipeline."""
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)  # No FK — bot lives in another DB
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict)
    chunk_index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
```

---

## 5. API Endpoints (Detailed)

### Authentication

| Method | Endpoint                | Description             | Auth          |
| ------ | ----------------------- | ----------------------- | ------------- |
| POST   | `/api/v1/auth/register` | Register new user       | No            |
| POST   | `/api/v1/auth/login`    | Login, returns JWT pair | No            |
| POST   | `/api/v1/auth/refresh`  | Refresh access token    | Refresh Token |
| GET    | `/api/v1/auth/me`       | Current user profile    | Yes           |

### Bots

| Method | Endpoint                | Description                  | Auth |
| ------ | ----------------------- | ---------------------------- | ---- |
| POST   | `/api/v1/bots`          | Create new bot               | Yes  |
| GET    | `/api/v1/bots`          | List user's bots (paginated) | Yes  |
| GET    | `/api/v1/bots/{bot_id}` | Get bot details              | Yes  |
| PATCH  | `/api/v1/bots/{bot_id}` | Update bot settings          | Yes  |
| DELETE | `/api/v1/bots/{bot_id}` | Delete bot and all data      | Yes  |

### Documents (Upload & Processing)

| Method | Endpoint                                          | Description                       | Auth |
| ------ | ------------------------------------------------- | --------------------------------- | ---- |
| POST   | `/api/v1/bots/{bot_id}/documents`                 | Upload files (multipart, batch)   | Yes  |
| GET    | `/api/v1/bots/{bot_id}/documents`                 | List uploaded documents           | Yes  |
| GET    | `/api/v1/bots/{bot_id}/documents/{doc_id}`        | Document details + extracted text | Yes  |
| DELETE | `/api/v1/bots/{bot_id}/documents/{doc_id}`        | Remove document                   | Yes  |
| GET    | `/api/v1/bots/{bot_id}/documents/{doc_id}/status` | Processing status (SSE)           | Yes  |

### Scenarios

| Method | Endpoint                                                | Description                      | Auth |
| ------ | ------------------------------------------------------- | -------------------------------- | ---- |
| GET    | `/api/v1/bots/{bot_id}/scenarios`                       | List generated scenarios         | Yes  |
| POST   | `/api/v1/bots/{bot_id}/scenarios/generate`              | Trigger scenario regeneration    | Yes  |
| PUT    | `/api/v1/bots/{bot_id}/scenarios/{scenario_id}`         | Edit scenario (human correction) | Yes  |
| PATCH  | `/api/v1/bots/{bot_id}/scenarios/{scenario_id}/approve` | Approve scenario                 | Yes  |
| DELETE | `/api/v1/bots/{bot_id}/scenarios/{scenario_id}`         | Remove scenario                  | Yes  |
| POST   | `/api/v1/bots/{bot_id}/scenarios/bulk-approve`          | Approve all scenarios            | Yes  |

### Corrections (Human-in-the-Loop)

| Method | Endpoint                            | Description                                 | Auth |
| ------ | ----------------------------------- | ------------------------------------------- | ---- |
| POST   | `/api/v1/bots/{bot_id}/corrections` | Submit a correction + free-form instruction | Yes  |
| GET    | `/api/v1/bots/{bot_id}/corrections` | List all corrections made                   | Yes  |

### Chat (Sandbox & Production)

| Method | Endpoint                              | Description                    | Auth |
| ------ | ------------------------------------- | ------------------------------ | ---- |
| WS     | `/api/v1/bots/{bot_id}/chat/ws`       | Sandbox WebSocket chat (owner) | Yes  |
| POST   | `/api/v1/bots/{bot_id}/chat/message`  | REST fallback for chat         | Yes  |
| GET    | `/api/v1/bots/{bot_id}/chat/sessions` | List sandbox chat sessions     | Yes  |

### Deployments

| Method | Endpoint                                   | Description                             | Auth |
| ------ | ------------------------------------------ | --------------------------------------- | ---- |
| POST   | `/api/v1/bots/{bot_id}/deploy`             | Deploy bot (generates widget / API key) | Yes  |
| GET    | `/api/v1/bots/{bot_id}/deploy`             | Get deployment status                   | Yes  |
| PATCH  | `/api/v1/bots/{bot_id}/deploy/{deploy_id}` | Update deployment config                | Yes  |
| DELETE | `/api/v1/bots/{bot_id}/deploy/{deploy_id}` | Deactivate deployment                   | Yes  |
| GET    | `/api/v1/widget/{api_key}`                 | Serve widget JS/HTML (public)           | No   |
| POST   | `/api/v1/widget/{api_key}/chat`            | Public chat endpoint for widget         | No   |

### Analytics

| Method | Endpoint                          | Description                                    | Auth |
| ------ | --------------------------------- | ---------------------------------------------- | ---- |
| GET    | `/api/v1/bots/{bot_id}/analytics` | Usage stats, message counts, avg response time | Yes  |

---

## 6. Core Processing Pipeline (Processing Service)

All processing runs inside the **Processing Service** using FastAPI `BackgroundTasks`. Results are published to Redis Streams for the Main API to consume.

### Pipeline Flow

```mermaid
flowchart TD
    A[User Uploads Files] --> B[Processing Service receives files]
    B --> C[Store in MinIO/S3]
    C --> D[Create Document + ProcessingJob in Processor DB]
    D --> E[Return 202 Accepted to frontend]
    E --> F[BackgroundTask: run_pipeline]

    F --> G{Detect File Type per document}
    G -->|Image| H[Image Processor]
    G -->|PDF| I[PDF Processor]
    G -->|Text/CSV| J[Text Processor]
    G -->|Presentation| K[Presentation Processor]

    H --> H1[OpenAI Vision API]
    H --> H2[Fallback: Tesseract OCR]
    H1 --> L[Raw Extracted Text + Metadata]
    H2 --> L

    I --> I1[PyMuPDF text] --> L
    I --> I2[pdfplumber tables] --> L

    J --> J1[Parse chat logs] --> L
    J --> J2[Parse plain text / CSV] --> L

    K --> K1[python-pptx slides] --> L

    L --> M[Text Chunking]
    M --> N[Generate Embeddings]
    N --> O[Store KnowledgeChunks in Processor DB]
    O --> P[Update Document status = completed]
    P --> PA[Publish: documents.processed]
    PA --> PB[Publish: knowledge.chunks_created]

    PB --> Q{All documents processed?}
    Q -->|Yes| R[Generate Scenarios via LLM]
    Q -->|No| S[Continue next document]

    R --> T[LLM generates Q&A pairs]
    T --> U[Publish: scenarios.generated]
    U --> V[Publish: processing.completed]
    V --> W[Main API consumer picks up events]
    W --> X[Main API replicates data to its DB]
    X --> Y[Main API notifies frontend via WebSocket]
```

### Pipeline Orchestrator

```python
# services/processor/app/services/pipeline.py

class ProcessingPipeline:
    """Runs as a FastAPI BackgroundTask. Publishes events to Redis Streams."""

    def __init__(self, db: AsyncSession, storage: S3Client, llm: OpenAIClient, publisher: ProcessingPublisher):
        self.db = db
        self.storage = storage
        self.llm = llm
        self.publisher = publisher  # Redis Streams publisher
        self.processors = {
            FileType.IMAGE: ImageProcessor(llm),
            FileType.PDF: PDFProcessor(),
            FileType.TEXT: TextProcessor(),
            FileType.CSV: TextProcessor(),
            FileType.PRESENTATION: PresentationProcessor(),
        }
        self.embedder = Embedder(llm)
        self.scenario_gen = ScenarioGenerator(llm)

    async def run(self, bot_id: str, document_ids: list[str]):
        try:
            # 1. Process each document + publish events
            for doc_id in document_ids:
                chunks = await self._process_single_document(doc_id, bot_id)

                # Publish document processed event
                await self.publisher.document_processed(doc_id, bot_id)
                # Publish chunks in batches
                await self.publisher.chunks_created(bot_id, doc_id, chunks)

            # 2. Generate scenarios
            scenarios = await self.scenario_gen.generate(bot_id, self.db)
            await self.publisher.scenarios_generated(bot_id, scenarios)

            # 3. Mark job complete
            await self._update_job_status(bot_id, JobStatus.COMPLETED)
            await self.publisher.processing_completed(bot_id)

        except Exception as e:
            logger.error(f"Pipeline failed for bot {bot_id}: {e}")
            await self._update_job_status(bot_id, JobStatus.FAILED, str(e))
            await self.publisher.processing_failed(bot_id, str(e))

    async def _process_single_document(self, doc_id: str, bot_id: str) -> list[dict]:
        doc = await self._get_document(doc_id)
        await self._update_doc_status(doc, ProcessingStatus.PROCESSING)

        # 1. Download from S3
        file_bytes = await self.storage.download(doc.storage_key)

        # 2. Route to processor
        result = await self.processors[doc.file_type].process(file_bytes, doc.original_filename)
        doc.raw_extracted_text = result.text
        doc.extracted_metadata = result.metadata

        # 3. Chunk + embed
        text_chunks = self.embedder.chunk(result.text, chunk_size=800, overlap=100)
        embeddings = await self.embedder.embed_batch([c.text for c in text_chunks])

        # 4. Store in Processor DB
        chunk_records = []
        for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
            kc = KnowledgeChunk(
                document_id=doc.id, bot_id=bot_id,
                content=chunk.text, embedding=embedding,
                metadata_=chunk.metadata, chunk_index=i,
            )
            self.db.add(kc)
            chunk_records.append({
                "id": str(kc.id), "content": chunk.text,
                "embedding": embedding.tolist(), "metadata": chunk.metadata,
                "chunk_index": i,
            })

        await self._update_doc_status(doc, ProcessingStatus.COMPLETED)
        await self.db.commit()
        return chunk_records
```

### Event Publisher (Processing Service)

```python
# services/processor/app/publishers/processing_publisher.py

import redis.asyncio as redis
from events.processing import DocumentProcessed, ChunksCreated, ScenariosGenerated

class ProcessingPublisher:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def document_processed(self, doc_id: str, bot_id: str):
        await self.redis.xadd("documents.processed", {
            "bot_id": bot_id, "doc_id": doc_id,
        })

    async def chunks_created(self, bot_id: str, doc_id: str, chunks: list[dict]):
        # For large payloads, store in S3 and send a reference
        import json
        payload = json.dumps(chunks)
        if len(payload) > 500_000:  # > 500KB → store in S3, send ref
            key = f"events/{bot_id}/{doc_id}/chunks.json"
            await self.storage.upload_bytes(payload.encode(), key)
            await self.redis.xadd("knowledge.chunks_created", {
                "bot_id": bot_id, "doc_id": doc_id,
                "s3_ref": key, "chunk_count": str(len(chunks)),
            })
        else:
            await self.redis.xadd("knowledge.chunks_created", {
                "bot_id": bot_id, "doc_id": doc_id,
                "chunks": payload,
            })

    async def scenarios_generated(self, bot_id: str, scenarios: list[dict]):
        import json
        await self.redis.xadd("scenarios.generated", {
            "bot_id": bot_id, "scenarios": json.dumps(scenarios),
        })

    async def processing_completed(self, bot_id: str):
        await self.redis.xadd("processing.completed", {"bot_id": bot_id})

    async def processing_failed(self, bot_id: str, error: str):
        await self.redis.xadd("processing.failed", {"bot_id": bot_id, "error": error})
```

### Event Consumer (Main API side)

```python
# services/api/app/consumers/processing_consumer.py

class ProcessingConsumer:
    """Runs as a background task during app lifespan. Reads Redis Streams."""

    STREAMS = ["documents.processed", "knowledge.chunks_created",
               "scenarios.generated", "processing.completed", "processing.failed"]
    GROUP = "main-api"  # Consumer group name

    def __init__(self, redis_client, db_session_factory, ws_manager):
        self.redis = redis_client
        self.db_factory = db_session_factory
        self.ws = ws_manager

    async def start(self):
        """Create consumer groups (idempotent) and start reading."""
        for stream in self.STREAMS:
            try:
                await self.redis.xgroup_create(stream, self.GROUP, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # Group already exists

        while True:
            entries = await self.redis.xreadgroup(
                groupname=self.GROUP, consumername="api-1",
                streams={s: ">" for s in self.STREAMS},
                count=10, block=5000,  # Block 5s waiting for new events
            )
            for stream, messages in entries:
                for msg_id, data in messages:
                    await self._handle(stream, msg_id, data)

    async def _handle(self, stream: str, msg_id: str, data: dict):
        async with self.db_factory() as db:
            try:
                if stream == b"knowledge.chunks_created":
                    await self._replicate_chunks(db, data)
                elif stream == b"scenarios.generated":
                    await self._store_scenarios(db, data)
                elif stream == b"processing.completed":
                    await self._mark_bot_ready(db, data)
                elif stream == b"processing.failed":
                    await self._handle_failure(db, data)
                elif stream == b"documents.processed":
                    await self._replicate_document(db, data)

                await self.redis.xack(stream, self.GROUP, msg_id)
            except Exception as e:
                logger.error(f"Failed to handle {stream} {msg_id}: {e}")
                # Message stays pending — will be retried on next read

    async def _replicate_chunks(self, db: AsyncSession, data: dict):
        """Store knowledge chunks in Main API DB for RAG queries."""
        import json
        bot_id = data[b"bot_id"].decode()
        if b"s3_ref" in data:  # Large payload stored in S3
            chunks = json.loads(await self.storage.download(data[b"s3_ref"].decode()))
        else:
            chunks = json.loads(data[b"chunks"].decode())

        for chunk in chunks:
            kc = KnowledgeChunk(
                id=uuid.UUID(chunk["id"]),
                document_ref_id=uuid.UUID(data[b"doc_id"].decode()),
                bot_id=uuid.UUID(bot_id),
                content=chunk["content"],
                embedding=chunk["embedding"],
                metadata_=chunk.get("metadata"),
                chunk_index=chunk["chunk_index"],
            )
            db.add(kc)
        await db.commit()

    async def _mark_bot_ready(self, db: AsyncSession, data: dict):
        bot_id = data[b"bot_id"].decode()
        bot = await db.get(Bot, uuid.UUID(bot_id))
        if bot:
            bot.status = BotStatus.READY
            await db.commit()
        # Notify frontend
        await self.ws.broadcast(bot_id, {"event": "processing_complete"})
```

---

## 7. Chat Engine (RAG Architecture)

### How the Sandbox/Production Chat Works

```mermaid
sequenceDiagram
    participant U as User/Visitor
    participant API as FastAPI
    participant CE as Chat Engine
    participant VS as Vector Store (pgvector)
    participant LLM as OpenAI GPT-4o

    U->>API: Send message via WebSocket
    API->>CE: route_message(bot_id, message)

    CE->>CE: Generate embedding for user message
    CE->>VS: Similarity search (cosine, top-k=5)
    VS-->>CE: Relevant knowledge chunks

    CE->>CE: Build prompt with:
    Note right of CE: 1. System prompt (bot.system_prompt)<br/>2. Approved scenarios as few-shot examples<br/>3. Retrieved knowledge chunks as context<br/>4. Applied corrections as behavioral rules<br/>5. Conversation history (last 10 messages)

    CE->>LLM: Chat completion request
    LLM-->>CE: Generated response
    CE->>CE: Store ChatMessage in DB
    CE-->>API: Return response
    API-->>U: Stream response via WebSocket
```

### System Prompt Construction

```python
# app/services/chat_service.py

class ChatEngine:
    def build_system_prompt(self, bot: Bot, corrections: list[Correction]) -> str:
        base = bot.system_prompt or "You are a helpful business assistant."

        # Inject correction-based rules
        if corrections:
            rules = "\n".join([
                f"- When asked about '{c.original_context}': {c.user_instruction}"
                for c in corrections
            ])
            base += f"\n\nBEHAVIORAL RULES (always follow these):\n{rules}"

        return base

    async def get_response(
        self, bot_id: str, user_message: str, session_id: str
    ) -> str:
        # 1. Embed user message
        query_embedding = await self.embedder.embed(user_message)

        # 2. Vector search
        chunks = await self.vector_store.similarity_search(
            bot_id=bot_id,
            embedding=query_embedding,
            top_k=5,
            threshold=0.7
        )

        # 3. Get approved scenarios as few-shot examples
        scenarios = await self.scenario_repo.get_approved(bot_id, limit=5)

        # 4. Get conversation history
        history = await self.chat_repo.get_recent_messages(session_id, limit=10)

        # 5. Build messages array
        messages = [
            {"role": "system", "content": self.build_system_prompt(bot, corrections)},
            # Few-shot from scenarios
            *[msg for s in scenarios for msg in [
                {"role": "user", "content": s.customer_question},
                {"role": "assistant", "content": s.bot_answer},
            ]],
            # Context injection
            {"role": "system", "content": f"Relevant context:\n{self._format_chunks(chunks)}"},
            # Conversation history
            *[{"role": m.role, "content": m.content} for m in history],
            {"role": "user", "content": user_message},
        ]

        # 6. Call LLM
        response = await self.llm.chat_completion(messages, stream=True)
        return response
```

---

## 8. Human-in-the-Loop Correction Flow

```mermaid
flowchart LR
    A[User sees scenario] --> B{Satisfied?}
    B -->|Yes| C[Approve scenario]
    B -->|No| D[Edit answer directly<br/>OR write instruction]

    D --> E[Create Correction record]
    E --> F[Re-generate bot answer<br/>with correction applied]
    F --> G[Update Scenario with<br/>new answer]
    G --> H[Correction stored as<br/>behavioral rule]
    H --> I[Future chat responses<br/>follow the rule]
```

### Correction Types

1. **Direct Edit**: User modifies the bot's answer text → stored as the new `bot_answer` in the Scenario.
2. **Free-form Instruction**: User writes something like "Be more formal" or "Don't mention competitor prices" → stored as a `Correction` record that's injected into the system prompt for all future interactions.
3. **Scenario-specific Instruction**: "For this specific question, always offer a 10% discount" → stored as a correction linked to a specific scenario.

---

## 9. Deployment & Widget System

### Web Widget Architecture

When a user clicks "Deploy as Web Widget":

1. **Backend** generates a unique `api_key` for the deployment
2. **Backend** returns an embed script:

```html
<!-- Embed code given to the user -->
<script
  src="https://your-domain.com/api/v1/widget/UNIQUE_API_KEY/loader.js"
  async
></script>
```

3. **`loader.js`** dynamically injects a chat bubble iframe into the host page
4. The iframe communicates with the backend via the public `/api/v1/widget/{api_key}/chat` endpoint
5. No authentication required for end visitors — rate limited by IP

### Widget Customization Options (stored in `Deployment.config`)

```json
{
  "theme": {
    "primary_color": "#4F46E5",
    "bubble_position": "bottom-right",
    "welcome_message": "Hi! How can I help you today?",
    "bot_avatar_url": "https://...",
    "font_family": "Inter"
  },
  "behavior": {
    "auto_open_delay_seconds": 5,
    "show_typing_indicator": true,
    "collect_email_before_chat": false
  }
}
```

---

## 10. Implementation Phases

### Phase 1: Foundation (Week 1–2)

- [ ] Project scaffolding (`events/`, `services/api/`, `services/processor/`, `frontend/`)
- [ ] Docker Compose with two Postgres instances, Redis, MinIO
- [ ] Events contract package (Pydantic models for Redis Streams)
- [ ] Main API: DB models + Alembic migrations (api_db)
- [ ] Processing Service: DB models + Alembic migrations (processor_db)
- [ ] Redis Streams infrastructure: publisher/consumer base classes
- [ ] Main API: User authentication (register, login, JWT)
- [ ] Main API: Bot CRUD + publish `bot.created` / `bot.deleted` events
- [ ] Processing Service: skeleton with health check + `bot.created` consumer
- [ ] React app setup with routing, auth pages, dashboard skeleton

### Phase 2: Upload & Processing Pipeline (Week 3–4)

- [ ] Processing Service: File upload endpoint (multipart, validation, S3 storage)
- [ ] Processing Service: Image processor (OpenAI Vision + Tesseract fallback)
- [ ] Processing Service: PDF processor (PyMuPDF + pdfplumber)
- [ ] Processing Service: Text/CSV processor
- [ ] Processing Service: Text chunking + embedding pipeline
- [ ] Processing Service: Event publisher (documents.processed, knowledge.chunks_created)
- [ ] Main API: Event consumer — replicate document refs + knowledge chunks
- [ ] Main API: WebSocket notifications on processing events
- [ ] React: Upload wizard with drag-and-drop, progress tracking via SSE

### Phase 3: Scenario Generation & Correction (Week 5–6)

- [ ] Processing Service: LLM-based scenario generation, publish `scenarios.generated`
- [ ] Main API: Consumer — store replicated scenarios
- [ ] Main API: Scenario list/edit/approve endpoints
- [ ] Main API: Correction submission API + system prompt injection
- [ ] React: Scenario preview cards, inline editing, approval flow
- [ ] React: Free-form instruction input for corrections

### Phase 4: Sandbox Chat (Week 7)

- [ ] Main API: RAG chat engine (vector search on local replicated chunks + LLM)
- [ ] Main API: WebSocket chat endpoint
- [ ] Main API: Conversation history storage
- [ ] React: Chat sandbox UI with streaming responses
- [ ] Processing Service: SSE status endpoint for real-time progress

### Phase 5: Deployment & Widget (Week 8–9)

- [ ] Main API: Deployment endpoints (generate API key, embed code)
- [ ] Widget loader.js + chat iframe
- [ ] Main API: Public chat endpoint (rate limited)
- [ ] Widget customization options
- [ ] React: Deploy panel with embed code, channel selection

### Phase 6: Polish & Analytics (Week 10)

- [ ] Main API: Analytics endpoints (message counts, response times, popular questions)
- [ ] React: Analytics dashboard with charts
- [ ] Dead letter queue handling for failed events
- [ ] Event replay tooling (re-process events from a given offset)
- [ ] Error handling, logging, monitoring
- [ ] Performance optimization (caching, connection pooling)
- [ ] Security audit (input sanitization, rate limiting, CORS)
- [ ] Documentation (API docs via Swagger, user guide)

---

## 11. Configuration & Environment Variables

```bash
# ========================================
# services/api/.env.example
# ========================================

APP_NAME=BotGenerator-API
APP_ENV=development
DEBUG=true

# Main API Database
DATABASE_URL=postgresql+asyncpg://api:api@localhost:5432/api_db

# Redis (event bus + cache)
REDIS_URL=redis://localhost:6379/0

# OpenAI (for chat/RAG)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# JWT
SECRET_KEY=your-secret-key-here
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_ALGORITHM=HS256

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Event consumer config
REDIS_CONSUMER_GROUP=main-api
REDIS_CONSUMER_NAME=api-1
```

```bash
# ========================================
# services/processor/.env.example
# ========================================

APP_NAME=BotGenerator-Processor
APP_ENV=development
DEBUG=true

# Processing Service Database
DATABASE_URL=postgresql+asyncpg://processor:processor@localhost:5433/processor_db

# Redis (event bus)
REDIS_URL=redis://localhost:6379/0

# Storage (MinIO/S3)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=bot-uploads
S3_REGION=us-east-1

# OpenAI (for Vision, embeddings, scenario generation)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Event consumer config
REDIS_CONSUMER_GROUP=processor
REDIS_CONSUMER_NAME=processor-1
```

---

## 12. Key Design Decisions & Trade-offs

| Decision                               | Rationale                                                                                             | Alternative Considered                      |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| **Separate databases** per service     | True decoupling — independent schemas, deploys, scaling; no shared state bottleneck                   | Shared DB (simpler, but couples services)   |
| **Redis Streams** for event bus        | Persistent, ordered, consumer groups with ack/retry; already have Redis; lighter than Kafka           | Kafka (overkill at this scale), RabbitMQ    |
| **Data replication** via events        | Each service has the data it needs locally; no cross-service queries; chat RAG is fast on local data  | API calls for cross-service reads (latency) |
| **BackgroundTasks** over Celery        | Processing Service is its own process; no need for extra worker infra; retries handled at event level | Celery for complex task orchestration       |
| **Large event payloads via S3 ref**    | Redis Streams has per-message limits; embeddings are large; S3 ref keeps events lightweight           | Chunking events into smaller messages       |
| **pgvector in both DBs**               | Main API needs vector search for RAG; Processing needs it for storage; same extension, no extra infra | External vector DB (Pinecone, Weaviate)     |
| **OpenAI Vision** over self-hosted OCR | Superior accuracy on screenshots, menus, price lists; structured JSON output                          | Self-hosted multimodal model (cost)         |
| **WebSocket** for chat over SSE        | Bidirectional — need typing indicators, connection management                                         | SSE for simpler one-way streaming           |
| **Zustand** over Redux                 | Less boilerplate for a mid-size app; sufficient for our state needs                                   | Redux Toolkit if state grows complex        |
| **Async SQLAlchemy**                   | Matches FastAPI's async nature; better throughput under concurrent load                               | Sync SQLAlchemy (simpler, but blocks)       |

---

## 13. Security Considerations

- **Authentication**: JWT with short-lived access tokens (30 min) + refresh tokens (7 days)
- **Authorization**: Every bot/document/scenario endpoint validates `bot.user_id == current_user.id`
- **File Upload**: Validate MIME types server-side, scan for malicious files, limit file size (50MB per file, 200MB per bot)
- **Rate Limiting**: `slowapi` middleware — 100 req/min for authenticated, 20 req/min for widget
- **Input Sanitization**: Strip HTML from user inputs, prevent prompt injection by sandboxing user content in delimiters
- **CORS**: Strict origin whitelist in production
- **API Keys**: Widget API keys are UUID v4, hashed in DB, rotatable
- **Secrets**: Each service has its own `.env` — never committed to git
- **Inter-service**: Events are internal — no auth on Redis Streams. In production, use Redis ACLs and TLS.

---

## 14. Monitoring & Observability

- **Logging**: `structlog` with JSON output → ELK or Loki
- **APM**: OpenTelemetry traces for both API + Processing Service
- **Health Checks**: `GET /health` on both services (own DB + Redis + S3 connectivity)
- **Event Lag**: Monitor Redis Streams pending entry count per consumer group (`XPENDING`)
- **Dead Letters**: Track events that fail after N retries — alert on dead letter threshold
- **Processing Status**: SSE endpoint on Processing Service for real-time progress
- **Error Tracking**: Sentry integration for both services and frontend

---

## 15. Local Development Quick Start

```bash
# 1. Clone & setup
git clone <repo> && cd chatbot

# 2. Start infrastructure (two Postgres instances, Redis, MinIO)
docker compose up -d api-db processor-db redis minio

# 3. Install events contract package
pip install -e ./events

# 4. Run migrations for each service
cd services/api && alembic upgrade head && cd ../..
cd services/processor && alembic upgrade head && cd ../..

# 5. Main API (terminal 1)
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" -e ../../events
uvicorn app.main:app --reload --port 8000

# 6. Processing Service (terminal 2)
cd services/processor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" -e ../../events
uvicorn app.main:app --reload --port 8001

# 7. Frontend (terminal 3)
cd frontend
npm install
npm run dev  # http://localhost:3000
```

### Docker Compose (all-in-one)

```bash
# Or run everything with Docker:
docker compose up --build
# Main API:           http://localhost:8000
# Processing Service: http://localhost:8001
# Frontend:           http://localhost:3000
# MinIO Console:      http://localhost:9001
# Redis Insight:      http://localhost:8001 (optional, for debugging streams)
```
