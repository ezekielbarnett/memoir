# Memoir - Remaining Tasks

## 🔴 Launch Blockers

- [ ] **Frontend** - Scaffold created, needs:
  - [ ] Project detail page (view/edit document)
  - [ ] Voice recording interface
  - [ ] Question flow UI
  - [ ] Document viewer/editor
  - [ ] Settings/profile page
- [ ] **Payments** - Stripe subscriptions for tiers
- [ ] **PDF Export** - Beautiful print-ready documents
- [ ] **File Uploads** - Audio/photo upload to S3 with signed URLs

## 🟡 Pre-Scale

- [ ] **DB Migrations** - Alembic setup
- [ ] **Admin Dashboard** - User/project management
- [ ] **Rate Limiting** - Protect AI endpoints

## 🟢 Business

- [ ] **Legal** - ToS, Privacy Policy
- [ ] **GDPR** - Data export/deletion endpoints
- [ ] **Analytics** - Usage tracking
- [ ] **Landing Page** - Marketing site

## ⚙️ Requires Configuration

These are implemented but need credentials/config to work:

| Feature | Env Vars Needed | Status |
|---------|----------------|--------|
| Google OAuth | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Code ready |
| Facebook OAuth | `FACEBOOK_OAUTH_CLIENT_ID`, `FACEBOOK_OAUTH_CLIENT_SECRET` | Code ready |
| Email (AWS SES) | `AWS_SES_FROM_EMAIL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Code ready |
| Error Tracking | `SENTRY_DSN` | Code ready |

See `DEPLOY.md` for setup instructions.

## ✅ Done

- [x] Core domain (content pool, projections, versioning)
- [x] AI integration (DSPy + Gemini)
- [x] Multi-contributor support
- [x] Authorization model (roles, tiers, capabilities)
- [x] Multilingual support (translation + caching)
- [x] API (FastAPI)
- [x] Infrastructure (Terraform)
- [x] CI/CD (GitHub Actions)
- [x] Deployment docs
- [x] JWT Authentication (email/password)
- [x] OAuth integration (Google, Facebook)
- [x] Email delivery (AWS SES)
- [x] Error tracking (Sentry)
- [x] Frontend scaffold (Next.js 14 + shadcn/ui)
  - Landing page
  - Auth pages (login, register, OAuth)
  - Dashboard
  - API client with token management
  - Theme system (light/dark)

