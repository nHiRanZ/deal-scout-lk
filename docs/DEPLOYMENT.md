# Deployment Guide

Target state:
- **Frontend** → `nimila.online/deal-scout-lk` (GitHub Pages, same workflow as the personal site)
- **Backend** → free cloud host, always-on FastAPI with Playwright

---

## Part 1 — Backend (Render.com)

Render's free tier is the lowest-friction option that supports Playwright + Chromium.
Free limitations: 512 MB RAM, sleeps after 15 min of inactivity (mitigated below).

### 1.1 Create a Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Chromium system dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tell Playwright to use the system Chromium (avoids ~300 MB download)
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
```

> **Why system Chromium?** The `playwright install chromium` download is ~300 MB and exceeds
> Render's build cache. Using the distro's `chromium` package keeps the image lean.

### 1.2 Update CORS to allow your live domain

In `backend/main.py`, add `nimila.online` to the allowed origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nimila.online",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    ...
)
```

### 1.3 Make the server bind correctly

`main.py` already runs `uvicorn` on `0.0.0.0:8000`.
Render expects the app to read the port from `$PORT`. Update the bottom of `main.py`:

```python
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
```

### 1.4 Deploy on Render

1. Push the `deal-scout-lk` repo to GitHub (e.g. `github.com/nHiRanZ/deal-scout-lk`).
2. Go to [render.com](https://render.com) → **New Web Service**.
3. Connect the repo. Set:
   - **Root Directory**: `backend`
   - **Runtime**: Docker
   - **Instance Type**: Free
4. Add these environment variables in the Render dashboard:
   | Key | Value |
   |---|---|
   | `PORT` | `8000` |
   | `PYTHONUNBUFFERED` | `1` |
5. Click **Deploy**.

The service URL will be something like `https://deal-scout-lk.onrender.com`.

### 1.5 Prevent the free tier from sleeping

The backend runs scheduled scrapes at 06:00, 10:00, 14:00, 18:00, 22:00 (Asia/Colombo).
If the service is asleep it won't wake for its own scheduler. Use UptimeRobot (free) to ping it:

1. Create a free account at [uptimerobot.com](https://uptimerobot.com).
2. **New Monitor** → HTTP(S) → URL: `https://deal-scout-lk.onrender.com/api/status`
3. Set interval to **5 minutes**.

This keeps the service warm and also gives you uptime alerts for free.

---

## Part 2 — Frontend (nimila.online/deal-scout-lk)

The personal site (`nHiRanZ.github.io`) already exports a static build to `./out` and
deploys it with `actions/deploy-pages`. The plan is to build the Vite app in the same
workflow and copy its output into `out/deal-scout-lk/` before the upload step.

### 2.1 Update the Vite base path

In `frontend/vite.config.js`, add a `base` so all asset URLs are relative to the subpath:

```js
export default defineConfig({
  plugins: [react()],
  base: '/deal-scout-lk/',   // ← add this
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' }
  }
})
```

### 2.2 Point the API client at the live backend

The dev server uses a Vite proxy (`/api` → `localhost:8000`). In production there is no
proxy, so the frontend needs the real backend URL.

In `frontend/src/lib/api.js`, change the first line:

```js
// Before
const BASE = '/api'

// After
const BASE = import.meta.env.VITE_API_BASE ?? '/api'
```

`VITE_API_BASE` is injected at build time. For local dev it stays empty (proxy still works).
For the CI build you'll pass `VITE_API_BASE=https://deal-scout-lk.onrender.com/api`.

### 2.3 Extend the personal site's GitHub Actions workflow

Open `nHiRanZ.github.io/.github/workflows/nextjs.yml` and add two steps between
**"Build with Next.js"** and **"Upload artifact"**:

```yaml
      - name: Checkout Deal Scout LK
        uses: actions/checkout@v4
        with:
          repository: nHiRanZ/deal-scout-lk   # ← your GitHub repo
          path: deal-scout-lk

      - name: Build Deal Scout LK frontend
        working-directory: deal-scout-lk/frontend
        env:
          VITE_API_BASE: https://deal-scout-lk.onrender.com/api
        run: |
          npm ci
          npm run build

      - name: Copy Deal Scout LK into Pages output
        run: |
          mkdir -p ./out/deal-scout-lk
          cp -r deal-scout-lk/frontend/dist/. ./out/deal-scout-lk/
```

The full `build` job steps should look like:

```yaml
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      # ... (existing detect-package-manager, setup-node, setup-pages, restore-cache steps)

      - name: Install dependencies
        run: ${{ steps.detect-package-manager.outputs.manager }} ${{ steps.detect-package-manager.outputs.command }}

      - name: Build with Next.js
        run: ${{ steps.detect-package-manager.outputs.runner }} next build

      # ── Deal Scout LK ─────────────────────────────────────────────────────
      - name: Checkout Deal Scout LK
        uses: actions/checkout@v4
        with:
          repository: nHiRanZ/deal-scout-lk
          path: deal-scout-lk

      - name: Build Deal Scout LK frontend
        working-directory: deal-scout-lk/frontend
        env:
          VITE_API_BASE: https://deal-scout-lk.onrender.com/api
        run: |
          npm ci
          npm run build

      - name: Copy Deal Scout LK into Pages output
        run: |
          mkdir -p ./out/deal-scout-lk
          cp -r deal-scout-lk/frontend/dist/. ./out/deal-scout-lk/
      # ──────────────────────────────────────────────────────────────────────

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./out
```

### 2.4 Handle client-side routing (single-page app)

The Vite app is a single-page app — GitHub Pages will 404 on any direct URL under
`/deal-scout-lk/` other than `index.html`. Add a `404.html` workaround:

After the **"Copy Deal Scout LK"** step, add:

```yaml
      - name: Add SPA 404 fallback for Deal Scout LK
        run: cp ./out/deal-scout-lk/index.html ./out/deal-scout-lk/404.html
```

---

## Part 3 — Checklist

### One-time setup

- [ ] Create `backend/Dockerfile` (Section 1.1)
- [ ] Update CORS origins in `backend/main.py` (Section 1.2)
- [ ] Update `PORT` binding in `backend/main.py` (Section 1.3)
- [ ] Push `deal-scout-lk` to GitHub
- [ ] Deploy backend on Render (Section 1.4)
- [ ] Set up UptimeRobot keep-alive ping (Section 1.5)
- [ ] Update `frontend/vite.config.js` with `base` (Section 2.1)
- [ ] Update `frontend/src/lib/api.js` with env var (Section 2.2)
- [ ] Extend `nextjs.yml` in the personal site repo (Section 2.3 + 2.4)
- [ ] Push personal site repo → GitHub Actions deploys both sites

### Verify

- [ ] `https://deal-scout-lk.onrender.com/api/status` returns JSON
- [ ] `https://nimila.online/deal-scout-lk/` loads the app
- [ ] Offers load (status shows last synced time)
- [ ] Download .ics works
- [ ] Scheduled scrapes run (check Render logs at 06:00, 10:00... Asia/Colombo)

---

## Notes

**Cache file on Render**
Render's free tier has an ephemeral filesystem — the `.offers_cache.json` file is lost on
each deploy or dyno restart. The backend will simply trigger a fresh scrape on startup,
which is acceptable. If you later want persistence, Render Disks (paid) or an external
key-value store (Upstash Redis free tier) are the options.

**If the Render free tier is too slow**
The free instance has 0.1 CPU and 512 MB RAM. Playwright + Chromium for 8 banks
concurrently may occasionally be tight. If scrapes time out, consider:
1. Reducing concurrency (scrape banks in batches of 4)
2. Upgrading to Render's $7/month Starter plan

**Truly free alternative: GitHub Actions scraper**
If you want zero server costs, the scraper can be moved entirely to a GitHub Actions
cron job. The job commits the resulting JSON to a `data` branch, the frontend fetches
it from `raw.githubusercontent.com`, and all filtering moves client-side. This eliminates
the backend server entirely but requires more frontend refactoring.
