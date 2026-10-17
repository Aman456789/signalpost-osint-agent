# Signalpost OSINT Agent

Takes Norwegian organisation numbers and builds a source-linked company profile.
Pass 1 uses the official registry (Brreg) with no AI. Pass 2 reads the company
website and publishes only facts that code can check against an exact quote.

This is the foundation segment: configuration, models, input checking and a
stub command. The registry, website and AI steps are added in later segments.

## Quick start

    python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pytest -q
    make run

## Dashboard (frontend/)

Next.js (App Router) in plain JavaScript. Needs Node 20.9 or newer.

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm test
npm run build
npm run dev          # http://localhost:3000
```

Start the API from the repository root in a second terminal with `make api`.
CORS allows `http://localhost:3000` only.
