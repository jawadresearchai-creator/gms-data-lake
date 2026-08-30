# Setup — one pass, about 30 minutes

You do this once. After that the lake refreshes itself every Sunday with your
laptop closed, and nothing lands on your local disk at any point.

---

## 0. What you are building

```
  GitHub Actions runner (free, ephemeral, 14 GB scratch)
        │
        │  1. fetch one file, streaming, never held in memory
        │  2. rclone copy it straight to your Drive
        │  3. delete the local copy
        │  4. next file
        ▼
  Google Drive  →  GLOBAL_MULTIDISCIPLINARY_MANAGEMENT_SCIENCE_DATA_LAKE/
                     01_RAW_IMMUTABLE/<domain>/<source>/<file>
                     00_CONTROL/manifests/manifest_<domain>.sqlite
                     00_CONTROL/reports/run_<id>.md
```

Peak local disk on the runner is one file. Peak local disk on **your laptop is
zero** — your laptop is not involved.

---

## 1. Put the code on GitHub

```bash
cd gms-data-lake
git init && git add -A
git commit -m "Management science data lake ingestion engine"
gh repo create gms-data-lake --private --source=. --push
```

> **Minutes budget.** A private repo gets 2,000 free Actions minutes a month.
> A full weekly cycle across all domains costs roughly 150–250 minutes, so you
> have ample room. A **public** repo gets unlimited minutes — the registry is
> only a list of public URLs, so publishing it is safe and it makes the project
> citable. Secrets stay secret either way.

---

## 2. Create your own Google OAuth client

Do not skip this. rclone ships with a shared client ID that thousands of people
hit at once; using it gets you throttled to unusable speeds.

1. <https://console.cloud.google.com/> → create a project (any name).
2. **APIs & Services → Library** → enable **Google Drive API**.
3. **OAuth consent screen** (now branded *Google Auth Platform*) → audience
   **External** → app name and your support email → add the scope
   `https://www.googleapis.com/auth/drive` → **Add yourself as a Test user**.
4. **Overview → Create OAuth client** (or *Credentials → Create credentials →
   OAuth client ID*) → application type **Desktop app**.
5. Copy the **Client ID** and **Client secret**.

> Testing-mode refresh tokens expire after 7 days. Once you have confirmed it
> works, go back to the consent screen and press **Publish app**. You do not
> need Google's verification review for your own account, and the token then
> stops expiring. This is the single most common reason a setup like this
> works for a week and then quietly stops.

---

## 3. Mint a refresh token (on your laptop, once)

Install rclone:

```powershell
winget install Rclone.Rclone      # Windows
# brew install rclone             # macOS
# curl https://rclone.org/install.sh | sudo bash   # Linux
```

Then authorize. The client id and secret are **positional arguments** — rclone
does not prompt for them:

```powershell
rclone authorize "drive" "YOUR_CLIENT_ID" "YOUR_CLIENT_SECRET"
```

A browser opens; sign in as jawadresearch.ai@gmail.com and approve. Back in the
terminal rclone prints:

```
Paste the following into your remote machine --->
{"access_token":"ya29...","token_type":"Bearer","refresh_token":"1//0g...","expiry":"..."}
<---End paste
```

Copy the **whole blob including the braces**, and nothing else — not the
`Paste the following` lines. That is your `GDRIVE_TOKEN`.

## 4. Get your lake folder ID

Open the lake folder in Drive. The URL ends in the ID:

```
https://drive.google.com/drive/folders/1z_47NQlOLY1L0zB-AXb-_3lwON0m2hJE
                                       └──────── this ────────┘
```

For your existing lake that is `1z_47NQlOLY1L0zB-AXb-_3lwON0m2hJE`.

---

## 5. Add the secrets

**Repo → Settings → Secrets and variables → Actions → New repository secret.**

| Secret | Value | Required |
|---|---|---|
| `GDRIVE_CLIENT_ID` | from step 2 | yes |
| `GDRIVE_CLIENT_SECRET` | from step 2 | yes |
| `GDRIVE_TOKEN` | the whole JSON blob from step 3 | yes |
| `GDRIVE_ROOT_FOLDER_ID` | `1z_47NQlOLY1L0zB-AXb-_3lwON0m2hJE` | yes |
| `CONTACT_EMAIL` | `jawadresearch.ai@gmail.com` | yes — SEC requires a contact address in the User-Agent |
| `EIA_API_KEY` | free from eia.gov | optional |
| `CENSUS_API_KEY` | free from census.gov | optional |
| `COMTRADE_API_KEY` | free tier from comtradeplus.un.org | optional |
| `WTO_API_KEY` | free from apiportal.wto.org | optional |
| `ACLED_API_KEY` | registration | optional |

Sources whose key is absent are **skipped cleanly**, not failed. You can add
keys later without touching anything else.

---

## 6. Verify before you trust it

Run these in order from the repo's **Actions** tab.

**a. Registry health** — `Registry health` → *Run workflow*.
Takes ~3 minutes, touches no credentials, downloads nothing. It probes every
URL and writes a table of what is reachable. Read it. This tells you the true
state of the registry today rather than what it was when I wrote it.

**b. A dry run** — `Ingest` → *Run workflow* → domain `02_MACRO`, dry run
**true**. Confirms the matrix, the registry and the secrets resolve.

**c. One real domain** — `Ingest` → *Run workflow* → domain
`00_CONTROL_AND_CATALOG`, dry run **false**. Small, fast, and it proves the
whole Drive path end to end. Then look in Drive:
`01_RAW_IMMUTABLE/00_CONTROL_AND_CATALOG/…` should contain real files, and
`00_CONTROL/reports/` a run report.

**d. Everything** — `Ingest` → *Run workflow*, blank domain. Then leave it
alone; the Sunday cron takes over.

---

## 7. Reading what happened

Every run writes a summary onto the workflow page itself — new, unchanged,
failed, bytes moved, a per-domain table, and every failure with a diagnosis.
You do not need to open a log.

To query the lake state from anywhere:

```bash
rclone copy gdrive:00_CONTROL/manifests ./manifests
python -m gmsdl.cli status
```

---

## Running it somewhere else

The engine does not care where it runs. Same code, three hosts.

**Your laptop, minimal footprint.** Peak disk is one file; nothing accumulates.

```bash
export GDRIVE_CLIENT_ID=... GDRIVE_CLIENT_SECRET=... GDRIVE_TOKEN='{...}'
export RCLONE_CONFIG_GDRIVE_TYPE=drive
export RCLONE_CONFIG_GDRIVE_CLIENT_ID=$GDRIVE_CLIENT_ID
export RCLONE_CONFIG_GDRIVE_CLIENT_SECRET=$GDRIVE_CLIENT_SECRET
export RCLONE_CONFIG_GDRIVE_TOKEN=$GDRIVE_TOKEN
export RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID=1z_47NQlOLY1L0zB-AXb-_3lwON0m2hJE
export GMSDL_REMOTE_ROOT="" GMSDL_CONTACT_EMAIL=jawadresearch.ai@gmail.com
export GMSDL_MAX_WORKDIR_BYTES=2147483648        # cap at 2 GB

python -m gmsdl.cli run --tier core
```

Do **not** point this at your `G:` Drive letter. Writing through Drive for
Desktop means every byte lands in the local cache first — that is the disk
problem you started with. rclone uploads over the network and touches nothing.

**Colab, for a heavy backfill.** Colab is the right tool for the tier-`bulk`
and tier-`massive` sources (SEC bulk, PatentsView, OpenAlex) because it has
~100 GB of scratch and a long session. It is the wrong tool for the routine
refresh, because it needs you sitting there with a tab open.

```python
!git clone https://github.com/<you>/gms-data-lake && cd gms-data-lake && pip install -q -r requirements.txt
!curl -fsSL https://rclone.org/install.sh | sudo bash
import os
os.environ.update({
    "RCLONE_CONFIG_GDRIVE_TYPE": "drive",
    "RCLONE_CONFIG_GDRIVE_CLIENT_ID": "...",
    "RCLONE_CONFIG_GDRIVE_CLIENT_SECRET": "...",
    "RCLONE_CONFIG_GDRIVE_TOKEN": '{"access_token":...}',
    "RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID": "1z_47NQlOLY1L0zB-AXb-_3lwON0m2hJE",
    "GMSDL_REMOTE_ROOT": "",
    "GMSDL_CONTACT_EMAIL": "jawadresearch.ai@gmail.com",
    "GMSDL_MAX_WORKDIR_BYTES": str(60 * 1024**3),
})
!cd gms-data-lake && python -m gmsdl.cli run --tier bulk --domain 01_FINANCE
```

Note what is **not** here: no `drive.mount()`, no SQLite on a FUSE mount, no
`auth.authenticate_user()`. Those are what made the old notebooks corrupt their
own registry.

---

## When something breaks

| Symptom | Cause | Fix |
|---|---|---|
| `couldn't fetch token: invalid_grant` | OAuth consent screen still in Testing; token expired after 7 days | Publish the app (step 2), re-run `rclone authorize`, update `GDRIVE_TOKEN` |
| `storageQuotaExceeded` | You used a service account | Service accounts have no Drive quota. Use the OAuth token flow above |
| A source reports `403 … refusing the client` | Bot filtering | Add a `Referer` header in that source's registry entry, or switch it to the host's API |
| A source reports `response is an HTML page` | The URL is a web page, not a file | The host moved to a SPA. Find its API and write a small adapter |
| Many `404 … the URL is stale` at once | The host reorganised | Run `Registry health`, then fix those YAML entries |
| Ingest job cancelled at 6 h | GitHub's hard job limit | Already handled: `GMSDL_RUN_BUDGET_SECONDS=18000` stops cleanly at 5 h and the next run resumes |
