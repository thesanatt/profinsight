# Deployment

## Local / dev-like
```bash
./deploy.sh setup      # create venv, pip install, npm install
./deploy.sh analyze    # run bayesian_pipeline.py over every data/<school>.json
./deploy.sh dev        # API on :8000, vite on :5173 (ctrl-c stops both)
```

## Prod-style local
```bash
./deploy.sh deploy     # setup + analyze + build
./deploy.sh serve      # uvicorn api:app on :8000 (needs data/*_analyzed.json present)
```

## Adding a new school
```bash
./deploy.sh scrape harvard "Harvard University"
```
Writes `data/harvard.json` + `data/harvard_analyzed.json`. Restart the API and it auto-discovers.

## Refreshing every school
```bash
./deploy.sh refresh
```
Wraps `bulk_update.py --refresh`.

## Cloud deploy (matches what's already live)
- **Frontend** → Vercel. Build command `npm run build`, output `dist/`, root `frontend/`. Set `VITE_API_URL` to the Render URL.
- **API** → Render (web service). Build `pip install -r requirements.txt`, start `uvicorn api:app --host 0.0.0.0 --port $PORT`. Push data files in the repo so Render reads them from disk (no external DB).
- **Weekly refresh** → GitHub Action `.github/workflows/update-data.yml` (Sundays 03:00 UTC). It runs `bulk_update.py --refresh` and commits the new `data/*.json`.

## Sanity check
```bash
./deploy.sh status
```
Confirms venv, Node, and how many `*_analyzed.json` files exist.

## Known quirks
- `bulk_update.py` shells out to `bayesian_pipeline.py`, so any new CLI flag we add must be forwarded there too.
- `frontend/src/config.js` reads `VITE_API_URL` at build time. Changing the backend host requires a rebuild, not just an env change at serve time.
- The GitHub Action's `pip install requests` in `update-data.yml` doesn't install the rest of `requirements.txt`. That's intentional today (bulk_update only needs requests) but any new pipeline dep called during refresh has to be added to that workflow.
