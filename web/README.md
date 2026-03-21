# Oasis Web UI

Next.js front end for the Oasis reel pipeline. The UI triggers the **Python** pipeline (`main.py`) in the **parent directory**, so API keys and FFmpeg behave the same as the CLI.

## Requirements

- Repository root must contain `main.py`, `.env`, and a working Python venv with dependencies installed (see root [README.md](../README.md)).

## Run (from repo root)

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy note

A full reel run is **long** (minutes) and needs **FFmpeg** and **Python**. Standard serverless hosts (short timeouts) are a poor fit for the whole pipeline. See [../DEPLOY_AND_REPOS.md](../DEPLOY_AND_REPOS.md) for hosting options.

## Stack

- [Next.js](https://nextjs.org/) App Router
- Calls into the Oasis Python orchestrator on the same machine
