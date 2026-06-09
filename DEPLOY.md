# Deploying EverNorthstar (Tier A: ~$0–3/mo)

Step-by-step. No jargon. You'll need ~45 minutes of clicking + waiting.

**Stack:**
- **Frontend** → Vercel (free Hobby tier, $0/mo)
- **Backend** → Fly.io (~$0–3/mo with auto-stop machines)
- **Cron** → GitHub Actions (free, public repo = unlimited minutes)
- **Data** → DuckDB + SQLite on a 1GB Fly persistent volume

---

## 0. Before you start — accounts you'll need

You'll create accounts at three places. **Use the same email everywhere** to keep things simple.

| Service | Why | Cost |
|---|---|---|
| [GitHub](https://github.com/signup) | hosts the code, runs the cron | free |
| [Fly.io](https://fly.io/app/sign-up) | runs the FastAPI backend | $0–3/mo |
| [Vercel](https://vercel.com/signup) | runs the Next.js frontend | free |

Sign up for all three first. Fly will ask for a credit card — they require it even though usage is tiny.

---

## 1. Push the code to GitHub (5 min)

### Why
GitHub stores the code and runs the hourly data refresh.

### Steps

1. **Make a new repo on GitHub.**
   - Go to https://github.com/new
   - Repository name: `evernorthstar`
   - Visibility: **Public** (so GitHub Actions cron stays free with unlimited minutes)
   - **Don't** initialize with README, .gitignore, or license — we already have files
   - Click **Create repository**

2. **Copy the SSH URL.** On the next page, copy the line that looks like:
   ```
   git@github.com:YOUR_USERNAME/evernorthstar.git
   ```

3. **In your terminal**, from `~/Desktop/crypto-trends`:
   ```bash
   cd ~/Desktop/crypto-trends
   git add .
   git commit -m "Initial commit — EverNorthstar"
   git branch -M main
   git remote add origin git@github.com:YOUR_USERNAME/evernorthstar.git
   git push -u origin main
   ```

   If git asks about credentials, you may need to set up an SSH key first. Easiest path: run `gh auth login` (after installing the GitHub CLI with `brew install gh`), follow prompts, then re-try `git push`.

4. **Verify.** Refresh your GitHub repo page in the browser — you should see all your files.

---

## 2. Deploy the backend to Fly.io (15 min)

### Why
This is what runs your FastAPI endpoints (`/rankings`, `/auth/*`, `/billing/*`, etc.).

### Step-by-step

1. **Install the Fly CLI.** In your terminal:
   ```bash
   brew install flyctl
   ```

2. **Sign in.**
   ```bash
   fly auth login
   ```
   This opens a browser tab — log in / sign up there, then return to the terminal.

3. **Create the Fly app.** This claims the name `evernorthstar` and links the directory to Fly's records:
   ```bash
   cd ~/Desktop/crypto-trends
   fly apps create evernorthstar --org personal
   ```
   If `evernorthstar` is taken, pick another name and **update the `app = ` line in `fly.toml`** to match.

4. **Create the persistent volume.** This is where your DuckDB lives:
   ```bash
   fly volumes create signal_data --region iad --size 1 --app evernorthstar
   ```
   Confirm "yes" when it warns about single-region storage. 1 GB is plenty for now.

5. **Set Fly secrets.** These are env vars that aren't in the code. Run **all** of these (paste them one at a time, replacing the `...` with your real values):

   ```bash
   # Generated production SECRET_KEY (cryptographically strong, 64 bytes)
   fly secrets set SECRET_KEY="REPLACE_WITH_THE_KEY_AT_BOTTOM_OF_THIS_FILE" --app evernorthstar

   # Disables dev-mode fail-fast bypass
   fly secrets set DEV_MODE=false --app evernorthstar

   # Your live Vercel URL (we'll get the real one in section 3 — for now use the predicted one)
   fly secrets set APP_BASE_URL=https://evernorthstar.vercel.app --app evernorthstar

   # Stripe keys (test mode for now — switch to live later)
   fly secrets set STRIPE_SECRET_KEY=sk_test_... --app evernorthstar
   fly secrets set STRIPE_WEBHOOK_SECRET=whsec_... --app evernorthstar
   fly secrets set STRIPE_PRICE_PRO_MONTHLY=price_... --app evernorthstar
   fly secrets set STRIPE_PRICE_PRO_ANNUAL=price_... --app evernorthstar

   # FMP for Congress + earnings (optional — leave blank if you don't have it)
   fly secrets set FMP_API_KEY=... --app evernorthstar

   # NOWPayments (only if you've signed up — see project_crypto_trends.md)
   fly secrets set NOWPAYMENTS_API_KEY=... --app evernorthstar
   fly secrets set NOWPAYMENTS_IPN_SECRET=... --app evernorthstar
   ```

   To check what's set: `fly secrets list --app evernorthstar`

6. **Deploy.** First-time deploy will take 3–6 minutes (building the Docker image):
   ```bash
   fly deploy --app evernorthstar
   ```

7. **Smoke test.** When deploy finishes, you'll see a URL like `https://evernorthstar.fly.dev`. Test it:
   ```bash
   curl https://evernorthstar.fly.dev/health
   # Should print: {"status":"ok"}
   ```
   If you get `503` or `502`, run `fly logs --app evernorthstar` to see what crashed.

---

## 3. Deploy the frontend to Vercel (10 min)

### Why
This is the public-facing dashboard at https://evernorthstar.vercel.app

### Steps

1. **Go to https://vercel.com/new** and sign in with GitHub.

2. **Import your repo.** Find `evernorthstar` in the list and click **Import**.

3. **Configure the project:**
   - Framework Preset: **Next.js** (should auto-detect)
   - **Root Directory: click "Edit" → select `web`** ⚠️ This is critical. The Next app lives in `web/`, not the repo root.
   - Build & Output Settings: leave defaults
   - **Environment Variables:** click "Add" and add:
     - Name: `NEXT_PUBLIC_API_BASE`
     - Value: `https://evernorthstar.fly.dev`  *(your Fly app URL from section 2)*

4. **Click Deploy.** Takes 2–4 minutes.

5. **Find your URL.** When done, Vercel shows it — something like `https://evernorthstar.vercel.app`.

6. **Update the backend CORS** to allow the Vercel URL (if different from default):
   ```bash
   fly secrets set CORS_ORIGINS="https://evernorthstar.vercel.app,http://localhost:3000" --app evernorthstar
   ```
   This triggers an automatic redeploy of the backend.

---

## 4. Wire up GitHub Actions cron (5 min)

### Why
This runs `refresh_all.py` hourly so prices, signals, and Congress trades stay fresh.

### Steps

1. **Get a Fly deploy token:**
   ```bash
   fly auth token
   ```
   Copy the long string that prints.

2. **Add it as a GitHub repo secret:**
   - Browser → your repo → **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `FLY_API_TOKEN`
   - Value: paste the token from step 1
   - Click **Add secret**

3. **Verify.** Push any small change to `main` (e.g. edit this file and commit). Check the **Actions** tab on your repo — you should see "Deploy backend to Fly" running.

4. **Trigger the data refresh manually** to confirm it works:
   - GitHub → Actions tab → **Hourly data refresh** workflow → click **Run workflow** → branch `main` → **Run workflow**
   - It should finish in ~2–5 min. Check the logs.

From now on, refresh runs every hour at `:15` past automatically.

---

## 5. Update Stripe + NOWPayments webhooks (5 min)

### Why
Right now your webhooks point at `localhost`. Need to point them at the live Fly URL.

### Stripe

1. Go to https://dashboard.stripe.com/test/webhooks
2. Click your existing webhook endpoint (or create new if none exists)
3. Set URL to: `https://evernorthstar.fly.dev/webhooks/stripe`
4. Events to listen for (if not already): `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
5. **Copy the webhook signing secret** (`whsec_...`) and update Fly:
   ```bash
   fly secrets set STRIPE_WEBHOOK_SECRET=whsec_... --app evernorthstar
   ```

### NOWPayments (only if you set it up)

1. Go to https://account.nowpayments.io/store/integrations
2. Set IPN Callback URL: `https://evernorthstar.fly.dev/webhooks/nowpayments`
3. Save. The IPN secret you already have in Fly secrets stays the same.

---

## 6. Final test (5 min)

1. Open `https://evernorthstar.vercel.app` in a private window.
2. Sign up with a test email + password.
3. Confirm you can log in, see rankings, and add items to your watchlist.
4. Go to /pricing → click Subscribe Monthly → use test card `4242 4242 4242 4242` → confirm `/billing/success` flips you to Pro.
5. Sign out → sign back in → confirm Pro status persists.

If anything breaks: `fly logs --app evernorthstar` is your friend.

---

## Generating SECRET_KEY for step 2.5

Run this in your terminal — copy the output and use it as `SECRET_KEY` when setting Fly secrets:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Then:
```bash
fly secrets set SECRET_KEY="paste-the-output-here" --app evernorthstar
```

**Do NOT paste the key into this file or any committed file.** It stays only on Fly (and optionally in your password manager).

---

## Future improvements (not blocking launch)

- **Custom domain** (`signalsync.5royals.com`): add via Vercel + Fly Certificates; ~30 min, $0 if you already own the domain
- **Move data refresh from GitHub Actions → local launchd**: already configured locally; would need `flyctl ssh sftp` to push DuckDB up after local refresh
- **Beefier Fly machine** (2GB RAM, ~$5/mo): would let FinBERT run on Fly directly, eliminate `--skip-news` flag, fold news rescore into hourly cron
- **Sentry or BetterStack** for error tracking — free tiers cover hobby usage
