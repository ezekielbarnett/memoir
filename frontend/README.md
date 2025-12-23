# Memoir Frontend

Next.js 14 + React + Tailwind CSS + shadcn/ui

## Quick Start

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Open http://localhost:3000

## Environment Variables

Create `.env.local`:

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# App URL (for OAuth redirects)
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── page.tsx            # Landing page
│   ├── auth/
│   │   ├── login/          # Login page
│   │   ├── register/       # Registration page
│   │   └── callback/       # OAuth callback
│   └── dashboard/          # Main dashboard
├── components/
│   ├── ui/                 # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── card.tsx
│   │   └── ...
│   └── theme-provider.tsx  # Dark/light mode
├── lib/
│   ├── api.ts              # Backend API client
│   └── utils.ts            # Utility functions
└── hooks/                  # React hooks (TODO)
```

## Adding Components

This uses [shadcn/ui](https://ui.shadcn.com/) - components are copied into your codebase.

To add more components:

```bash
# If you have shadcn CLI installed:
npx shadcn-ui@latest add dialog
npx shadcn-ui@latest add dropdown-menu
npx shadcn-ui@latest add tabs

# Or just copy from: https://ui.shadcn.com/docs/components
```

## Scripts

```bash
npm run dev       # Development server
npm run build     # Production build
npm run start     # Start production server
npm run lint      # Run ESLint
npm run type-check # TypeScript check
```

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first CSS
- **shadcn/ui** - Accessible component primitives
- **Radix UI** - Headless UI components
- **Lucide** - Icon library
- **Sonner** - Toast notifications
- **Zustand** - State management (when needed)

