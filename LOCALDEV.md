# Local Development

Quick guide to run Memoir locally.

## Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (Python package manager)

## 1. Clone & Setup

```bash
git clone https://github.com/ezekielbarnett/memoir.git
cd memoir
```

## 2. Backend

```bash
# Install Python dependencies
uv sync

# Create .env file
cp env.example .env

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your-key-here

# Run the API
.venv/bin/uvicorn memoir.api.app:app --reload
```

API runs at: http://localhost:8000

Test it:
```bash
curl http://localhost:8000/health
```

Swagger docs: http://localhost:8000/docs

## 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Frontend runs at: http://localhost:3000

The frontend proxies `/api/*` to the backend automatically.

## 4. Both Together

Open two terminals:

**Terminal 1 (Backend):**
```bash
cd memoir
.venv/bin/uvicorn memoir.api.app:app --reload
```

**Terminal 2 (Frontend):**
```bash
cd memoir/frontend
npm run dev
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Required
GEMINI_API_KEY=your-gemini-api-key

# Optional - for full features
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
AWS_SES_FROM_EMAIL=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SENTRY_DSN=
```

See `env.example` for all options.

## Running Tests

```bash
# Backend tests
.venv/bin/pytest tests/ -v

# Frontend type check
cd frontend && npm run type-check
```

## Common Tasks

### Reset the database

Currently using in-memory storage. Just restart the backend.

### Add a new API endpoint

1. Add route in `memoir/api/app.py`
2. Restart backend (auto-reloads with `--reload`)

### Add a new frontend page

1. Create file in `frontend/src/app/your-page/page.tsx`
2. Frontend auto-reloads

### Add a shadcn/ui component

```bash
cd frontend
npx shadcn-ui@latest add button  # or dialog, dropdown-menu, etc.
```

## Project Structure

```
memoir/
├── memoir/              # Python backend
│   ├── api/             # FastAPI routes
│   ├── auth/            # Authentication
│   ├── core/            # Domain models
│   ├── services/        # Business logic
│   └── integrations/    # External services
├── frontend/            # Next.js frontend
│   └── src/
│       ├── app/         # Pages (App Router)
│       ├── components/  # React components
│       └── lib/         # Utilities, API client
├── config/              # YAML product configs
├── infrastructure/      # Terraform (not needed locally)
└── tests/               # Python tests
```

## Troubleshooting

### "GEMINI_API_KEY not set"

Add it to your `.env` file:
```bash
GEMINI_API_KEY=your-key
```

### Port already in use

Kill existing processes:
```bash
# Backend
pkill -f uvicorn

# Frontend  
pkill -f "next dev"
```

### Frontend can't reach backend

Make sure backend is running on port 8000. Check `frontend/next.config.js` for proxy settings.

## CI/CD

**Currently disabled.** The GitHub Actions workflow only runs manually.

When ready to enable:
1. Set GitHub Secrets (AWS credentials)
2. Edit `.github/workflows/deploy.yml` - uncomment triggers
3. See `DEPLOY.md` for full deployment guide

