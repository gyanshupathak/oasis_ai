# Free deployment ($0) — step by step with Oasis

**Reality check (plain words):** A full reel needs **RAM**, **time**, and **FFmpeg**. Many “free” cloud apps give **little RAM** or **short timeouts**, so the pipeline **often fails** there. Two approaches that cost **no money**:

| Approach | Cost | Works when | Trade-off |
|----------|------|------------|-----------|
| **A. Local + Cloudflare Tunnel** | $0 | Your PC is on and the app is running | URL is public only while the tunnel runs (quick tunnel) or you set up a free named tunnel |
| **B. Fly.io (or similar) free allowance** | $0 *if* you stay inside the provider’s free tier | Provider builds/runs the Docker image | May ask for a **card** for verification; free RAM/time limits can still break heavy reels |

Start with **Approach A** so you see a **live URL today** without paying. Add **B** later if you need 24/7 without your PC.

---

## Approach A — Local app + free Cloudflare Tunnel (recommended first)

### Step A1 — One-time: install `cloudflared` (Windows)

Pick one:

- **Winget:** open PowerShell (normal user is fine):

  ```powershell
  winget install --id Cloudflare.cloudflared -e
  ```

- **Or** download the Windows binary from [Cloudflare Zero Trust — Downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) and put it on your `PATH`.

Close and reopen the terminal, then check:

```powershell
cloudflared --version
```

**Windows: “cloudflared is not recognized”** — the EXE is often here (winget does not always add `PATH`):

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" --version
```

To fix permanently, add that folder to your **user** `PATH`, then open a **new** terminal:

1. Start menu → type **environment variables** → **Edit environment variables for your account**.
2. Under **User variables**, select **Path** → **Edit** → **New**.
3. Paste: `C:\Program Files (x86)\cloudflared`
4. OK → OK → **close all PowerShell windows** and open a new one → `cloudflared --version`.

### Step A2 — Run Oasis locally (same as always)

**Terminal 1 — Python venv (repo root `D:\Oasis`):**

```powershell
cd D:\Oasis
.\.venv\Scripts\Activate.ps1
# If you don't have a venv yet:
# python -m venv .venv
# .\.venv\Scripts\Activate.ps1
# pip install -r requirements.txt
```

**Terminal 2 — Next.js (must be able to see `main.py` one level up):**

```powershell
cd D:\Oasis\web
npm install
npm run dev
```

Open **http://localhost:3000** in your browser and confirm the UI loads.

> Ensure **`.env`** in `D:\Oasis` has `GEMINI_API_KEY` and `POLLINATIONS_API_KEY`.

### Step A3 — Start a free **quick tunnel**

**Terminal 3:**

```powershell
cloudflared tunnel --url http://localhost:3000
```

Cloudflare prints a **trycloudflare.com** URL. Open that URL on your phone or another network — it forwards to your PC.

**Caveats:**

- The URL **changes** each time you restart the quick tunnel (unless you later set up a **named tunnel** with a free Cloudflare account).
- Your PC must stay **awake**; closing the terminal stops the tunnel.
- First reel run can be **slow** (models, APIs).

### Step A4 — Stop safely

- Stop tunnel: **Ctrl+C** in Terminal 3.
- Stop Next: **Ctrl+C** in Terminal 2.

---

## Approach B — Fly.io with Dockerfile (no local Docker required)

Fly can **build your image on their side** once you install **only** the Fly CLI (you do **not** need Docker Desktop on your laptop for that).

### Step B1 — Install Fly CLI

Follow: [Install flyctl](https://fly.io/docs/hands-on/install-flyctl/) (Windows instructions included).

### Step B2 — Login

```powershell
fly auth login
```

### Step B3 — Launch app from your repo

```powershell
cd D:\Oasis
fly launch
```

- Use an app name you like.
- Region: pick something close to you.
- **Use the existing Dockerfile** at the repo root when asked.
- You can skip Postgres/Redis unless you add them later.

### Step B4 — Set secrets (keys never go in Git)

```powershell
fly secrets set GEMINI_API_KEY="paste_here" POLLINATIONS_API_KEY="paste_here"
```

### Step B5 — Deploy

```powershell
fly deploy
```

Open the `https://....fly.dev` URL Fly shows.

**If the app crashes or times out on free tier:** the instance may need **more RAM** or a **paid** plan — that’s a common limit of “free cloud,” not your code. See **[DEPLOY_PLATFORM.md](DEPLOY_PLATFORM.md)** for tuning ideas.

---

## Other free hosts (short notes)

- **Render (free web service):** Often **512 MB RAM** — Whisper + FFmpeg may **OOM**. Worth a try; if build or run fails with memory errors, use Approach A or Fly with more RAM.
- **Railway / others:** Free tiers change often; same RAM/timeout story.

---

## Checklist before you blame “deployment”

- [ ] `http://localhost:3000` works on the same PC.
- [ ] `.env` has valid keys (Gemini + Pollinations).
- [ ] For tunnels: firewall allows **localhost:3000** (local only is fine; tunnel reaches in).
- [ ] For Fly: `fly logs` right after a failed reel.

---

## What we are doing together (order)

1. Finish **A1–A3** → you get a **free public URL** with **$0** hosting fees (your machine is the server).
2. When you need **24/7** without your PC, do **B** or a free VPS (e.g. Oracle Always Free — separate signup).

If you tell me which step you are on (e.g. “A2 done, localhost works”), the next message can be **only** the next clicks/commands for that step.
