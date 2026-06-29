# Deploying to PythonAnywhere

This app is **Flask + SQLite**. PythonAnywhere is a good fit because its
filesystem is **persistent** (your SQLite data survives restarts) — so no
database migration is needed. The free "Beginner" tier is enough to launch; the
~$5/mo Developer tier adds a custom domain, a reliable scheduler, and no
3-month expiry (see [Limitations](#limitations)).

These steps assume the repo is pushed to GitHub.

---

## 1. Clone the repo

Open a **Bash console** on PythonAnywhere (Dashboard → "New console" → Bash):

```bash
git clone https://github.com/NvyGreen/academic-success-planner.git
cd academic-success-planner
```

## 2. Install runtime dependencies

```bash
pip install --user -r requirements.txt
```

Only `requirements.txt` (runtime) is needed — not the test/load-test tiers.

## 3. Create your `.env`

Create `.env` in the **repo root** (the WSGI file loads it by absolute path):

```bash
nano .env
```

Fill in (copy the shape from `.env.example`):

```
SQLITE3_DB=/home/USERNAME/academic-success-planner/prod.db
SECRET_KEY=<paste a generated key>
```

- **`SQLITE3_DB`** must be an **absolute path** (relative paths break under WSGI).
- **`SECRET_KEY`** must be **at least 32 characters** and not a common word —
  `create_app()` refuses to start otherwise. Generate one:

  ```bash
  python -c "import secrets;print(secrets.token_hex(32))"
  ```

Leave `SEED_EMAIL` / `SEED_PWD` for the next step.

## 4. Build the database

```bash
python build_prod_db.py
```

This creates the schema, loads the full **303-course** catalog, and seeds a demo
login. It will **prompt you for a demo password** (never stored in `.env`, the
command line, or shell history), then print two lines:

```
SEED_EMAIL=demo@example.com
SEED_PWD=$pbkdf2-sha256$...
```

Paste **both** into your `.env` (`create_app()` requires them to boot). Your
login is `demo@example.com` + the password you just entered.

> Use `--email you@example.com` to pick a different demo login, or `--force` to
> rebuild an existing database from scratch.

## 5. Create the web app

Web tab → **Add a new web app**:

1. Choose **Manual configuration** — *not* the "Flask" preset. This app is a
   package (`course_reg/`) with an application factory, not a single `app.py`.
2. Choose **Python 3.13**. If it isn't in the dropdown, upgrade your system
   image first (Account → **System Image**), then come back.

## 6. Configure the WSGI file

On the Web tab, click the **WSGI configuration file** link. **Delete its
contents and paste the contents of [`deploy/pythonanywhere_wsgi.py`](deploy/pythonanywhere_wsgi.py)**
from this repo.

> ⚠️ PythonAnywhere does **not** read that file from your cloned folder — you
> must paste it into the WSGI editor.

Then edit the two placeholders:
- replace `USERNAME` with your PythonAnywhere username,
- confirm `project_path` matches where you cloned the repo.

Save.

## 7. Reload and log in

Click the green **Reload** button on the Web tab, then visit
`https://USERNAME.pythonanywhere.com` and log in with the demo account.

---

## Troubleshooting

Check the **Error log** link on the Web tab first. Common cases:

| Symptom | Likely cause | Fix |
|---|---|---|
| `ValueError: SECRET_KEY is too weak` | Key under 32 chars / placeholder | Regenerate with `token_hex(32)` (step 3) |
| `ValueError: Environment variables ... not configured` | A var missing from `.env` | Ensure all of `SQLITE3_DB`, `SECRET_KEY`, `SEED_EMAIL`, `SEED_PWD` are set |
| `no such table: course` | DB not built | Run `python build_prod_db.py` (step 4) |
| `ModuleNotFoundError: course_reg` | Wrong `project_path` in WSGI | Fix the path in the WSGI editor |
| `unable to open database file` | Bad `SQLITE3_DB` path | Use an absolute path that exists |
| Login always fails | `SEED_PWD` set to plaintext | It must be the pbkdf2 hash printed by the build script |

## Security

- **Rotate `SECRET_KEY`** for production — generate a fresh one; do not reuse a
  key that has ever been shared or committed.
- `.env` and `*.db` are gitignored; keep real secrets out of the repo.

## Limitations (free tier)

- **Background scheduler** (nightly waitlist promotion in `scheduler.py`) runs in
  the web worker, which the free tier recycles — so that job may not fire
  reliably. The site itself is unaffected. The Developer tier can run it as a
  proper **always-on task**.
- **The app sleeps** after ~3 months of inactivity; log in and hit **Reload** to
  wake it. The Developer tier removes this.
