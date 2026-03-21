# Oasis — Private vs public repos and deployment

Step-by-step process for backing up to **oasis_ai_private**, keeping **oasis_ai** public-ready, and choosing a hosting strategy.

---

## Part A — Push everything to the private repo first

**What you are doing:** Creating a full backup of the project (including your local workflow) before you polish the public tree.

1. **Confirm secrets are not tracked**

   ```powershell
   cd D:\Oasis
   git ls-files .env
   ```

   Expected: *(no output)*. If `.env` appears, stop and remove it from Git history before pushing anywhere public.

2. **Confirm `.env` is only on your machine**

   - Keys live in `.env` (copied from `.env.example`).
   - Never commit `.env`; it is listed in `.gitignore`.

3. **Create the private repo on GitHub** (if it does not exist yet)

   - Name: e.g. `oasis_ai_private`
   - Visibility: **Private**

4. **Add the private remote and push**

   If this folder currently has only `origin` → public `oasis_ai`, add a second remote for private:

   ```powershell
   cd D:\Oasis
   git remote add private https://github.com/YOUR_USER/oasis_ai_private.git
   git push -u private main
   ```

   If you prefer **private as the only remote** for daily work, you can instead rename remotes:

   ```powershell
   git remote rename origin public
   git remote add origin https://github.com/YOUR_USER/oasis_ai_private.git
   git push -u origin main
   ```

   Pick one convention and stay consistent; the doc below assumes **`private`** = backup/private, **`origin`** = public `oasis_ai`.

5. **Tag the snapshot (optional)**

   ```powershell
   git tag v0.1.0-private
   git push private v0.1.0-private
   ```

**Done when:** `oasis_ai_private` on GitHub shows the same commits/branches you care about.

---

## Part B — Keep `oasis_ai` (public) clean

**What you are doing:** The public repo should be clone-and-run friendly, with no secrets and no generated media.

| OK in public | Avoid in public |
|----------------|-----------------|
| `.env.example` | `.env`, `.env.local` |
| Source + `requirements.txt` + `web/package.json` | `output/`, `*.mp4`, local test blobs |
| Docs (`README`, `PIPELINE_AND_TECH`, etc.) | Hard-coded API keys, personal absolute paths |

Before pushing to **public**:

1. Search the repo for accidental keys (strings like `AIza`, `sk_`, long bearer tokens).
2. Replace machine-specific paths (`d:\Oasis`) with neutral instructions (see `README.md`).
3. Run tests / one full local pipeline if you can.

**Push public:**

```powershell
git push origin main
```

If you use two remotes:

```powershell
git push origin main
git push private main
```

---

## Part C — Deploy MVP 0.1 “for free” (what actually works)

**What you are doing:** Matching the host to what the app does.

Oasis is **long-running**: Python, optional Next.js, **FFmpeg**, API calls, large files. Cheap serverless hosts (short timeouts, no FFmpeg) usually **cannot** run the **entire** pipeline reliably.

### Option 1 — Recommended for 0.1: run locally or on your machine

- **CLI:** `python main.py ...` after venv + FFmpeg (see `README.md`).
- **Web UI:** `npm run dev` in `web/` with repo root available for `main.py` (see `README.md`).

Cost: **$0** (your electricity). Most reliable for MVP.

### Option 2 — Docker on a small VPS or free-tier container host

- Package Python + FFmpeg + app in one image; set `GEMINI_API_KEY` and `POLLINATIONS_API_KEY` in the host’s environment.
- **Fly.io / Render / Railway / Cloud Run:** may fit within free credits or trials; check **RAM**, **disk**, and **request timeout** for a full reel.

**What you are doing:** Trading “fully free forever” for “one container that can finish a 30s reel.”

### Option 3 — GitHub Actions (batch builds)

- Workflow installs Python + FFmpeg, runs `main.py`, uploads `final.mp4` as an **artifact**.
- Good for **occasional** reels; not a polished product UI without extra work.

### Option 4 — Next.js on Vercel **only**

- **Frontend** deploys easily.
- **Not sufficient alone** for the full pipeline unless you add a **separate long-running worker** (see Option 2) or trigger Actions.

---

## Part D — Suggested workflow summary

1. Push **`main`** to **private** → backup secured.  
2. Polish **README**, paths, and ignore rules → push **`main`** to **public** `oasis_ai`.  
3. Choose **one** deployment story for 0.1: **local + docs**, or **Docker + one host**, or **Actions for artifacts**.  
4. Build MVP 0.2 features in **private** first; merge to **public** when stable.

---

## Security reminder

If `.env` was ever committed, pasted in an issue, or shared: **revoke and rotate** `GEMINI_API_KEY` and `POLLINATIONS_API_KEY` in the provider dashboards, then update your local `.env` only.
