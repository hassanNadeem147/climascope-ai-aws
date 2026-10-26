# ClimaScope AI

ClimaScope AI is a climate-research question-answering application. It combines a
responsive browser interface, account registration and sign-in, semantic search
over PDF research documents, and a Self-RAG workflow that checks answer relevance,
grounding, and usefulness before returning a response.

The application is designed to answer from its indexed climate sources. If the
retrieved evidence does not support an answer, the workflow is instructed to say
so rather than fill gaps with outside knowledge.

## Features

- Responsive ClimaScope AI sign-in, account registration, and chat interface.
- FastAPI backend serving both the frontend and JSON/SSE API on the same origin.
- User registration with password hashing and signed bearer-token authentication.
- Streaming answers over Server-Sent Events (SSE).
- Per-user conversation checkpointing in PostgreSQL.
- Semantic retrieval from Qdrant Cloud with a local Hugging Face embedding model.
- Relevance grading, answer-grounding and usefulness checks, one revision attempt,
  and a safe fallback when an answer cannot be verified.
- PDF loading from an AWS S3 bucket for offline indexing.
- Security response headers, a restrictive Content Security Policy, and
  no-store caching for API responses.

## How it works

### Indexing climate documents

The indexing pipeline reads `.pdf` objects from the configured S3 bucket, extracts
text page by page, splits the text into chunks of 1,000 characters with a
100-character overlap, embeds each chunk, and writes the vectors to the Qdrant
collection named `self rag`.

The embedding model is configured in code as
`sentence-transformers/all-mpnet-base-v2` and runs on CPU by default. The model
may need to be downloaded from Hugging Face on the first indexing or retrieval
run.

Indexing is a separate, manual operation:

```powershell
python -m app.rag.vector_store
```

The application does not expose an endpoint for uploading or indexing documents.
The RAG chat searches documents that have already been indexed into Qdrant.

> **Indexing implementation note:** `app.rag.splitter` currently calls
> `split_docs()` when the module is imported, and `store_docs()` calls
> `split_docs()` again. As a result, running the indexing command can load and
> process the S3 documents twice. Review this behavior before running a large or
> costly indexing job.

### Asking a question

For an authenticated question, the API retrieves up to four candidate chunks,
grades document relevance, generates an answer with the configured Groq chat
model, and independently checks whether the answer is grounded and useful. It
may revise an answer once. If it cannot produce a verifiable answer, it returns
a fallback response.

The graph uses PostgreSQL checkpoints. Each checkpoint thread ID is scoped with
the authenticated user's ID so separate users do not share the same conversation
thread.

## Architecture

```text
.
├── app/
│   ├── api/                 # Authentication, chat streaming, API dependencies
│   ├── core/                # Settings and password/JWT security helpers
│   ├── database/            # SQLAlchemy async engine and database sessions
│   ├── graph/               # Self-RAG state, workflow, nodes, and routing
│   ├── logging/             # Console and rotating file logs
│   ├── models/              # SQLAlchemy user model
│   ├── rag/                 # S3 PDF ingestion, splitting, embeddings, Qdrant
│   └── schemas/             # Request and response validation
├── frontend/
│   ├── index.html           # Sign-in, registration, and chat views
│   ├── index.js             # API requests, SSE streaming, safe Markdown display
│   └── styles.css           # Responsive application styling
├── logs/                    # Runtime logs (ignored by Git and Docker)
├── requirements.txt         # Pinned Python dependencies
└── run.py                   # Windows-compatible local server launcher
```

## Requirements

- Python 3.10 or newer. Python 3.12 or newer is recommended.
- Network access to the configured PostgreSQL database, Qdrant instance, S3
  bucket, and Groq API.
- AWS credentials with permission to list and download the source PDFs when
  indexing documents.
- A populated Qdrant collection before asking questions.
- Enough disk space for the Python dependencies and the embedding model.

## Configuration

Settings are loaded from a `.env` file in the project working directory. Create
that file locally and provide the values for the settings used by
`app/core/config.py`. Never commit it or include it in a container image.

| Variable | Required | Purpose |
| --- | --- | --- |
| `AWS_ACCESS_KEY_ID` | Yes | AWS credential used by the S3 document loader. |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS credential used by the S3 document loader. |
| `AWS_REGION` | Yes | AWS region for the configured bucket. |
| `BUCKET_NAME` | Yes | S3 bucket containing source PDF documents. |
| `GROQ_API_KEY` | Yes | Credential for the Groq chat model. |
| `GROQ_MODEL` | Yes | Groq chat model identifier. |
| `QDRANT_API_KEY` | Yes | Credential for Qdrant Cloud. |
| `QDRANT_URL` | Yes | Qdrant Cloud endpoint. |
| `DATABASE_NAME` | Yes | PostgreSQL database name. |
| `DATABASE_USERNAME` | Yes | PostgreSQL username. |
| `DATABASE_HOST` | Yes | PostgreSQL server hostname. |
| `DATABASE_PORT` | No | PostgreSQL port; defaults to `5432`. |
| `DATABASE_PASSWORD` | Yes | PostgreSQL password. |
| `DATABASE_SSLMODE` | No | PostgreSQL SSL mode; defaults to `require`. |
| `JWT_SECRET_KEY` | Required for authentication | Secret used to sign and verify bearer tokens. It must contain at least 32 UTF-8 bytes. |
| `JWT_ACCESS_TOKEN_EXPIRE_SECONDS` | No | Token lifetime in seconds; defaults to `1800`, with a maximum of `86400`. |

The settings class ignores unknown environment variables. The `.env.example`
file also contains `EMBEDDING_MODEL_API_KEY` and `EMBEDDING_MODEL_NAME`; the
current application does not read those settings. The embedding model is
hard-coded in `app/rag/embedding.py`.

Set `JWT_SECRET_KEY` before using registration, sign-in, or authenticated chat.
Although the settings model allows this value to be omitted, the authentication
API returns a service-unavailable response when it is missing or shorter than
32 bytes.

## Local setup

Run commands from the project root so that the `.env` file and application
packages resolve correctly.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create and populate `.env` with the configuration listed above. Do not copy
placeholder values into a production environment.

### Start the application

On Windows, use the provided launcher:

```powershell
python run.py
```

The launcher binds to `127.0.0.1:5555` and uses a selector event loop for the
asynchronous PostgreSQL checkpoint connection. Open:

```text
http://127.0.0.1:5555/
```

The server initializes the application database, sets up the PostgreSQL graph
checkpointer, and builds the RAG workflow during startup. Startup fails if those
dependencies cannot be initialized.

For development environments where the standard Uvicorn event loop is
compatible with the PostgreSQL driver, the app can also be started with:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The frontend is served by FastAPI at `/`, so the browser uses same-origin API
requests; no separate frontend server or permissive CORS configuration is
required.

## API

The API is prefixed with `/api/v1`. Interactive API documentation is available
at `/docs`, and the OpenAPI schema is available at `/openapi.json`.

### Health check

```http
GET /health
```

Returns `{"status":"ok"}` when the PostgreSQL database can be reached.

### Register

```http
POST /api/v1/auth/register
Content-Type: application/json
```

```json
{
  "email": "researcher@example.com",
  "full_name": "Climate Researcher",
  "password": "a-long-unique-password"
}
```

Registration creates the account and returns the public user profile. Sign in
after registration to receive an access token.

### Sign in

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "email": "researcher@example.com",
  "password": "a-long-unique-password"
}
```

The response contains a bearer `access_token`, its `expires_in` duration, and
the public user profile.

### Stream an answer

```http
POST /api/v1/model/stream
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "query": "What do the indexed sources say about sea-level rise?",
  "thread_id": "optional-thread-id"
}
```

`query` must contain 1–4,000 non-whitespace characters. `thread_id` is optional
and, when supplied, must contain 1–128 letters, numbers, underscores, or
hyphens. The server streams named SSE events:

| Event | Data |
| --- | --- |
| `thread` | The client-visible thread ID for this conversation. |
| `token` | A generated answer text fragment. |
| `done` | Indicates the answer stream completed. |
| `error` | A safe error detail when generation fails. |

The browser keeps the access token in memory only; it is not persisted in
`localStorage` or `sessionStorage`. Refreshing the page requires signing in
again. Signing out clears the in-memory token and current conversation from the
page.

## Security considerations

- Keep `.env` out of source control. Do not place secrets in frontend code,
  browser storage, logs, screenshots, or the Docker build context.
- Use a unique, randomly generated `JWT_SECRET_KEY` of at least 32 bytes.
- Passwords are stored as scrypt hashes, not plaintext.
- Authenticated API access uses signed bearer tokens and checks that the user
  still exists and is active.
- API responses receive `Cache-Control: no-store`. The server also sends
  Content Security Policy, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and `Permissions-Policy` headers.
- Chat output is rendered with DOM text nodes and a limited Markdown renderer;
  model output is not inserted as raw HTML. External Markdown links are limited
  to HTTP and HTTPS URLs and use `noopener noreferrer`.
- The supplied server launchers bind to loopback for local development. For
  deployment, use HTTPS behind a correctly configured reverse proxy, protect
  secrets with the deployment platform's secret manager, and review the
  production host, TLS, network, and database access controls.
- The browser client does not receive AWS, Groq, Qdrant, or database
  credentials. Those credentials belong only in the server environment.

Security headers are configured for the current frontend dependencies: Google
Fonts and the specified CloudFront background video. If these dependencies or
origins change, update and review the policy in `app/main.py`.

## Logging and data handling

Application logs are written to the console and to rotating files under
`logs/`. The configured file handlers rotate at 10 MB and retain logs for seven
days. The `logs/` directory is excluded from Git and Docker build contexts.

The database stores user records and LangGraph checkpoints. PDF source files are
read from S3 by the indexing pipeline and vector chunks are stored in Qdrant.
The frontend does not upload files or persist chat transcripts in browser
storage.

## Docker status

The repository includes a `.dockerignore` that omits secrets, local
environments, logs, caches, databases, and downloaded models from a Docker build
context. A `Dockerfile` and Compose configuration are not currently included;
container image build and deployment instructions will require those files.

## Troubleshooting

- **Startup fails before the server is ready:** verify PostgreSQL connectivity
  and configuration. The app also needs to establish its PostgreSQL graph
  checkpointer during startup.
- **Authentication returns `503`:** configure a `JWT_SECRET_KEY` containing at
  least 32 UTF-8 bytes.
- **Chat returns `401`:** sign in again and retry with a valid access token.
  Tokens expire, and the browser intentionally does not persist them.
- **Chat cannot find answers:** verify that the `self rag` Qdrant collection
  exists and contains the relevant indexed documents.
- **Indexing fails:** verify AWS access to the PDF bucket and Qdrant access. The
  indexing command may download the embedding model the first time it runs.
- **Model requests fail:** verify the Groq API key and model name, then inspect
  the server logs for the detailed error.
- **The page or assets do not load:** start the server from the project root and
  open the same host and port where Uvicorn is listening.

## Current scope

The application currently supports account registration, sign-in, sign-out,
and RAG question answering over pre-indexed climate PDFs. It does not currently
provide document upload, password reset, token refresh, or a document-management
interface.
