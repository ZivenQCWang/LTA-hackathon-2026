# Deploy PLiZ

Live demo: **https://pliz.4bytedigi.com**, hosted on 4bytedigi.

Activated on 19 September 2026 (Singapore time). Public HTTPS, all three planning scenarios, and a read-only AI response were verified. The service is enabled to start at boot. Each scenario scheduled all 54 activities with no remaining workload and passed the app's local audit; this is not official judge validation.

The planning demo has no login and uses synthetic inputs and fictional crew. Visitors edit the same workspace. The public reporting app lives at `/public/`; its **Public's report** staff inbox and photos require operator authentication in production. Real operational use needs individual identities and permissions.

## Runtime

- Build the frontend using `npm ci` then `npm run build`.
- Run **one Uvicorn worker**; locks, caches and rate limits are per process.
- Bind **127.0.0.1:8016** behind the existing HTTPS tunnel/proxy.
- Persist SQLite outside releases; do not copy local chat history or the developer's database.
- Keep secrets in a private environment file.
- Route only `pliz.4bytedigi.com` to this service and preserve other hostnames.

## Environment

Create root-readable `/etc/pliz.env`:

```dotenv
PLIZ_ENV=production
PLIZ_PUBLIC_DEMO=true
PLIZ_ALLOWED_ORIGINS=https://pliz.4bytedigi.com
DATABASE_URL=sqlite:////var/lib/pliz/pliz.db
OPENAI_API_KEY=your-server-side-key
OPENAI_MODEL=gpt-5.6-luna
DBSTUDIOS_API_URL=your-https-project-api-url
DBSTUDIOS_API_KEY=your-server-side-project-key
PLIZ_AUTH_USERNAME=your-operator-username
PLIZ_AUTH_PASSWORD=your-long-operator-password
PLIZ_AI_REQUESTS_PER_MINUTE=8
PLIZ_AI_REQUESTS_PER_DAY=200
```

The minute limit is per connection address; the rolling daily limit is shared across the process. Both reset on restart. Behind a local tunnel visitors may share an address. These are demo safeguards, not provider spending limits.

Optional private mode: `PLIZ_PUBLIC_DEMO=false`, `PLIZ_AUTH_USERNAME`, and a `PLIZ_AUTH_PASSWORD` of at least 16 characters. `PLIZ_PUBLIC_READONLY=true` then allows public viewing while protecting writes and chat receipts with HTTP Basic authentication. Hosted origins require HTTPS.

For public reporting, both DBStudios values must be set together, and the operator password must have at least 16 characters. Existing public-demo mode keeps public submissions available while the report inbox checks operator credentials independently. See [DBStudios reports](DBSTUDIOS_REPORTS.md) for the table schema, queue, photo storage and update installer.

## Install on 4bytedigi

The systemd service runs as a dedicated `pliz` user, stores data under `/var/lib/pliz`, and serves `/opt/pliz/current`.

1. Stage `backend/`, `data/`, `dist/`, `requirements.txt` and `deploy/` in a release directory.
2. Create `/etc/pliz.env` and review/run `sudo bash deploy/install-server.sh /absolute/release/directory`.
3. Add a Cloudflare tunnel hostname route for `pliz.4bytedigi.com` to `http://127.0.0.1:8016` on the connector host. Preserve existing routes.
4. Create a proxied CNAME for `pliz` to that tunnel's `UUID.cfargotunnel.com` address.
5. Verify before sharing the URL.

For the staged 4bytedigi release, the combined command is `sudo bash /home/pyie/pliz-release/deploy/activate-4bytedigi.sh`. It installs missing Python venv support if needed, creates the isolated PLiZ service, waits for health, then inserts only the PLiZ route into the locally managed tunnel. The tunnel script keeps a backup and restores it if the connector restart fails. The DNS record is configured separately in Cloudflare.

The installer does not modify DNS or other services. Updates install a new release while preserving data and environment. For rollback, repoint `/opt/pliz/current` to the previous release and restart `pliz`; database migrations are not automated.

```bash
systemctl status pliz --no-pager
journalctl -u pliz -n 50 --no-pager
curl --fail http://127.0.0.1:8016/api/health
curl --fail https://pliz.4bytedigi.com/api/health
```

Check the public UI, A/B/C policies, a read-only AI question, phone navigation, and rejection of cross-origin writes. Do not generate submission ZIPs during verification.

## Optional Docker host

```bash
mkdir -p deploy/private
# Create deploy/private/production.env with the settings above,
# using DATABASE_URL=sqlite:////app/storage/pliz.db.
docker compose up -d --build
docker compose ps
```

Compose binds port 8016 to loopback and uses a named data volume. It does not install Docker, create DNS records or set up HTTPS. Update with `docker compose up -d --build`; preserve the data volume.

## Backup

Use SQLite's online backup API or stop the service briefly before copying its database. Keep backups private. A release rollback does not undo visitor data edits. Never commit environment files, API keys, database backups or chat logs.
