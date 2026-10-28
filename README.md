# ClimaScope AI — AWS-Deployed Climate Research Assistant

**Grounded climate research answers powered by Self-RAG, deployed on AWS EC2, with CI/CD automation using AWS CodeBuild and Systems Manager.**

ClimaScope AI is an AI-powered climate research assistant that answers questions using indexed climate research PDFs. It combines a FastAPI backend, a responsive web interface, Hugging Face embeddings, Qdrant vector search, Groq-powered answer generation, and Supabase PostgreSQL.

Its Self-RAG workflow evaluates retrieved evidence, checks answer grounding and usefulness, and attempts a revision when needed. When the available evidence cannot support an answer, the application is designed to acknowledge that limitation rather than invent information.

## Highlights

- **Climate-focused RAG:** Retrieve evidence from indexed climate research documents.
- **Self-RAG workflow:** Evaluate relevance, grounding, and answer usefulness.
- **FastAPI application:** Serve the frontend and API from the same application.
- **Streaming responses:** Deliver generated answers through Server-Sent Events (SSE).
- **User authentication:** Registration, password hashing, and signed bearer tokens.
- **Vector search:** Qdrant Cloud with a local Hugging Face embedding model.
- **Persistent conversations:** PostgreSQL-backed LangGraph checkpoints.
- **AWS integration:** Read source PDF documents from Amazon S3.
- **AWS EC2 deployment:** Host the application on an Ubuntu EC2 instance.
- **CI/CD target architecture:** GitHub source code, AWS CodeBuild, and Systems Manager Run Command for automated deployment.

## AWS and CI/CD Architecture

The planned deployment workflow is:

1. **GitHub** — stores the application source code.
2. **AWS CodeBuild** — runs the build and deployment workflow.
3. **AWS Systems Manager** — sends deployment commands to the EC2 instance without requiring the CodeDeploy agent.
4. **Amazon EC2** — runs the FastAPI application and serves the frontend.

The EC2 instance is registered as an online Systems Manager managed node. The CodeBuild pipeline and automated deployment steps are still being configured.

## Technology Stack

- **Backend:** Python, FastAPI, Uvicorn
- **AI workflow:** LangGraph, Self-RAG
- **LLM:** Groq
- **Embeddings:** Hugging Face `sentence-transformers/all-mpnet-base-v2`
- **Vector database:** Qdrant Cloud
- **Relational database and checkpoints:** Supabase PostgreSQL
- **Document storage:** Amazon S3
- **Cloud hosting:** AWS EC2 (Ubuntu)
- **CI/CD:** GitHub, AWS CodeBuild, AWS Systems Manager

## Security

Secrets belong in environment configuration or an appropriate secret manager, never in Git. The production deployment should use an EC2 IAM role for AWS access, least-privilege permissions, restricted network access, and HTTPS through a properly configured reverse proxy.

See the sections below for application architecture, local setup, configuration, API endpoints, indexing, and troubleshooting.
