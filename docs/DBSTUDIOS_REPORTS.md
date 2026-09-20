# Public reports in DBStudios

The public app at `/public/` delivers reports to **NightShift AI → public_reports** in [DBStudios](https://dbstudios.pyiesone.dev/). The PLiZ workspace's **Public's report** section reads those rows back, with search, category filtering, pagination and report/photo details.

## Configuration

Set both server-side environment values in `.env` locally or `/etc/pliz.env` on the host:

```dotenv
DBSTUDIOS_API_URL=https://dbstudios.pyiesone.dev/api/v1/projects/0fb8c8f6273da9002cd6ebcec5a5b3f5e355345472fc129e
DBSTUDIOS_API_KEY=your-project-read-write-key
PLIZ_AUTH_USERNAME=your-operator-username
PLIZ_AUTH_PASSWORD=your-long-operator-password
```

Never put the key in a `VITE_` variable or commit it. Both DBStudios values may be blank for local-only development. If configured, a cloud read failure is shown as an error; the inbox does not silently substitute local records.

The current service key is named **PLiZ public reports service**, created on 19 September 2026 with a 90-day lifetime. Renew it before expiry around 18 December 2026, update the private server environment and restart PLiZ. Project keys require read/write access. They do not manage schema or project sharing.

With `PLIZ_PUBLIC_DEMO=true`, submissions, the inbox and its photographs are accessible without signing in: anyone with the demo link can view submitted reports and locations. With `PLIZ_PUBLIC_DEMO=false`, production requires operator authentication for the inbox and photos, even when `PLIZ_PUBLIC_READONLY=true`. Local development follows the existing localhost access policy.

## Table schema

DBStudios adds `id`, `_version` and `created_at` automatically. The adapter uses these custom fields:

| Field | DBStudios type | Content |
| --- | --- | --- |
| `report_id` | text | Report UUID; used to recognise retries |
| `reference` | text | Human-readable PLZ reference |
| `category` | text | cleanliness, facilities, accessibility, safety or other |
| `location` | text | User-entered station or landmark |
| `description`, `description_2`, `description_3`, `description_4` | text | Consecutive 500-character chunks, reassembled by the inbox |
| `status` | text | Initially received |
| `submitted_at` | text | UTC ISO timestamp from PLiZ |
| `photo_count` | integer | Number of attached photos |
| `photo_paths` | text | JSON array of relative PLiZ photo endpoints, following the inbox access mode |
| `latitude`, `longitude` | decimal | Approximate coordinates, limited by DBStudios to two decimal places |
| `gps_coordinates` | text | JSON pair preserving the submitted coordinate precision; nulls when absent |

The table was created through DBStudios because project API keys cannot create schema. Its text columns allow 500 characters each. Do not remove the continuation fields or precision-preserving GPS field.

## Delivery and storage

1. Validate the report and re-encode uploaded images without EXIF metadata.
2. Save the report, JPEG bytes and delivery record atomically in PLiZ's persistent SQLite database.
3. Check DBStudios for the report UUID, then insert a row if missing.
4. Mark delivery complete locally. A successful receipt returns HTTP 201; a saved report awaiting cloud delivery returns HTTP 202.
5. Retry pending reports in the background every 30 seconds, up to five per pass, stopping that pass after an upstream failure.

Run **one Uvicorn worker**. The process lock serialises deliveries and the UUID check handles retries after a lost response. This is not a multi-host exactly-once guarantee: the DBStudios table currently has no custom unique constraint. Add a database uniqueness constraint and coordinated workers before scaling to multiple instances.

The inbox caches cloud rows for up to 25 seconds and refreshes its visible page every 30 seconds. It loads DBStudios pages before filtering and supports up to 2,000 reports in this demo. Above that limit it shows an explicit error rather than silently hiding rows; use DBStudios directly until server-side paginated filtering is implemented.

**Photo bytes remain on PLiZ**. The submitting browser can view its own photos; the inbox photo endpoints are public in public-demo mode and require operator authentication in private production mode. DBStudios stores these paths. Back up `/var/lib/pliz/pliz.db` with SQLite's online backup API: it holds reports, photographs and pending deliveries. The DBStudios table alone is not a complete backup. Submitted reports do not automatically create jobs or dispatch crews.

## Deployment and checks

Build and test using the commands in [PUBLIC_APP.md](PUBLIC_APP.md). Stage the release and a private file containing only the two DBStudios environment values. `deploy/enable-public-reports.sh` merges them into `/etc/pliz.env`, preserves existing planner credentials/settings, creates operator credentials only if missing, then installs and checks the release. It backs up the environment and restores the previous release and environment if activation fails.

After activation, verify:

- `/public/` loads over HTTPS and a clearly fictional report receives a delivered receipt.
- NightShift AI's `public_reports` table contains the same reference exactly once.
- In public-demo mode, **Public's report** opens directly, displays that reference and opens its photos without signing in. Anonymous `/api/operator/reports` requests return 200.
- In private production mode, anonymous inbox and photo requests return 401, and valid operator credentials grant access. Existing planning health remains good.

Keep configuration patches and operator credentials in ignored `deploy/private/` or a private server directory, never in GitHub. A text-only fictional integration record may remain in the table as evidence of the test.
