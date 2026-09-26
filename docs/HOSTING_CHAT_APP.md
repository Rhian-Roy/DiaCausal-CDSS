# Putting the full chat app online (later)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

The website at <https://diacausal.netlify.app> is the **causal engine + evidence search**, running
on the phone, with Supabase accounts. The **full chat app** (`frontend/` + `backend/`: the chat
pipeline, voice typing with Whisper, the patient panel, its own sign-in with CAPTCHA, password and
authenticator code, and its SQLite database) is different: it needs a **computer that is always on**.
This page says how to put it online when the team is ready. [DEPLOY.md](DEPLOY.md) has every
command; this is the plain-English route through it.

## Which computer?

| Option | Cost | Good for | Watch out |
|---|---|---|---|
| **Your laptop, same Wi-Fi** ([DEPLOY.md step 5b](DEPLOY.md#5b-use-it-on-your-phone-on-the-same-wi-fi-no-internet-needed)) | free | the viva room, a lab demo | only while the laptop is on and on that Wi-Fi |
| **A free cloud VM** (e.g. Oracle Cloud "Always Free" Ampere VM) | free | an always-on demo | sign-up needs a card for identity; pick the Mumbai or Hyderabad region |
| **A small paid VPS** (2 CPUs, 4 GB memory — DEPLOY.md "Sizing") | a few hundred rupees a month | the October clinician evaluation | someone must keep it updated |

"Serverless" hosts with free tiers that sleep and forget their disk (they reset the SQLite
database and reload the 150 MB speech model on every wake-up) are **not** suitable.

## The steps on a cloud VM (about one hour, once)

1. **Make the VM:** Ubuntu 24.04, 2+ CPUs, 4+ GB memory, 30 GB disk. In its firewall ("security
   list" / "security group") open ports **80** and **443**; keep **22** (SSH) open only to your IP.
2. **Log in and install Docker:**
   ```bash
   ssh ubuntu@YOUR_VM_IP
   curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER && exit   # log in again after this
   ```
3. **Get a name for it.** A free DuckDNS name (`diacausal-g28.duckdns.org`) pointed at the VM's IP
   is enough; a college subdomain is better if the IT team agrees.
4. **Follow [DEPLOY.md](DEPLOY.md) steps 2–4** on the VM (clone, make the secret key, `.env`,
   `docker compose up --build -d`, create the first admin), then **step 6** with
   `SITE_ADDRESS=` your name and ports 80/443 — Caddy gets a free HTTPS certificate by itself.
5. **Check it** ([DEPLOY.md step 5](DEPLOY.md#5-check-it-works)) from your iPhone over mobile data.
6. **Backups** ([DEPLOY.md step 7](DEPLOY.md#7-backups)): the database and the secret key, weekly.

## Before real clinicians use it

- Run the deploy checklist at the end of [DEPLOY.md](DEPLOY.md#deploy-checklist).
- Synthetic vignettes only (`eval/`); never real patient details.
- The chat app keeps its own accounts (admin-created, `scripts/admin.py`); the website's Supabase
  accounts are separate. Joining them is a later decision, not needed for the evaluation.
