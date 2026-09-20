# PLiZ Public

A separate mobile web app for passengers to photograph and report issues. The public app lives at **`/public/`**; the existing operations workspace stays at **`/`**.

## Run and preview

Use the repository's existing setup from [README.md](../README.md), then run:

```powershell
./start.ps1
```

- Public app: <http://127.0.0.1:5173/public/>
- Operations workspace: <http://127.0.0.1:5173/>

Restart the Python service after adding these backend files: the existing development launcher does not enable automatic Python reload. Vite reloads frontend edits automatically.

To serve the production build using the existing backend:

```powershell
npm run build
./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/public/>. Only start this command if that port is free. No second frontend deployment or new domain is required. On the existing host, the public URL will be `https://pliz.4bytedigi.com/public/` **after deploying this version** using [DEPLOYMENT.md](DEPLOYMENT.md).

For testing from an actual phone, use an HTTPS deployment. Camera behavior depends on the phone/browser: “Take a photo” requests the rear camera through a file input; “Choose from gallery” is the alternative. GPS and browser-generated access keys require a secure context (HTTPS or localhost). A phone's `localhost` refers to the phone, not the development computer.

## Public flow

1. Take or select up to three photos, or continue without one.
2. Select cleanliness, facilities, accessibility, safety concern or another issue.
3. Enter a station/landmark and description; optionally attach GPS after browser permission.
4. Review the details and send the report.
5. Receive a reference number and revisit the saved report under **My reports**.

Reports are saved locally and delivered to DBStudios when configured. The main PLiZ workspace includes **Public's report**, where operators can search, filter and open reports and photographs. A receipt distinguishes delivered reports from reports saved for retry. Reports do not create jobs, affect schedules or dispatch crews.

## File organisation

```text
src/
  main.tsx                         Route selection and separate bundle loading
  public-app/
    PublicApp.tsx                  Public navigation, form steps and confirmation
    api.ts                         Requests, browser access key and image resizing
    constants.ts                   Issue categories, status labels and dates
    types.ts                       Shared public-app TypeScript types
    public-app.css                 Independent, responsive public-app styles
    components/
      PhotoPicker.tsx              Camera/gallery, previews and photo removal
      MyReports.tsx                Saved reports and authenticated photo loading
backend/
  public_reports/
    __init__.py                    Router export
    models.py                      Report, photo and delivery queue database models
    router.py                      Validation, submission, own reports and photo access
    operator.py                    Authenticated inbox and operator photo access
    storage.py                     Local database sessions and table initialisation
    dbstudios.py                    Server-only DBStudios API adapter
    delivery.py                     Durable delivery and background retries
src/public-reports/
  PublicReportsWorkspace.tsx       Searchable operations inbox and sign-in
  ReportDetails.tsx                Details and private photo previews
  api.ts                          Inbox API and in-memory operator credentials
  public-reports.css              Scoped responsive inbox styles
tests/
  test_public_reports.py           Workflow, privacy, limits and retry tests
docs/
  PUBLIC_APP.md                    This guide
```

The public bundle does not import the operations dashboard or its CSS. Public reporting tables are initialised separately in the existing database, without altering planning records. The main app imports the inbox from its own feature folder.

## API and storage

All public endpoints require an **`X-Report-Key`** header (32–128 characters). The app generates a random key and keeps it in this browser's local storage. The server stores only its SHA-256 hash. The key is a bearer credential: keep it private. It is never put into a URL.

| Endpoint                                         | Purpose                                                         |
| ------------------------------------------------ | --------------------------------------------------------------- |
| `POST /api/public/reports`                       | Multipart `report` JSON plus zero to three `photos` files       |
| `GET /api/public/reports`                        | Up to 100 most recent reports owned by the supplied browser key |
| `GET /api/public/reports/{id}/photos/{photo_id}` | Read a photograph belonging to that browser's report            |

The inbox endpoints are `GET /api/operator/reports?q=&category=&page=1` and `GET /api/operator/reports/{id}/photos/{photo_id}`. With `PLIZ_PUBLIC_DEMO=true`, anyone with the demo link can view reports, attached locations and photos without signing in. Private production deployments require the configured operator credentials, including when `PLIZ_PUBLIC_READONLY=true`. The inbox keeps entered credentials in memory only.

The `report` JSON contains `request_id` (UUID), `category`, `location`, `description`, and optional paired `latitude`/`longitude`. The client reuses its request ID when retrying a failed submission. Identical retries return the original receipt; attempts to reuse it with different content or ownership are rejected.

Reports and JPEG image bytes are saved in `pliz_public_reports` and `pliz_public_report_photos` in the existing application database. `pliz_public_report_deliveries` tracks delivery attempts. With DBStudios configured, report text, category, location, reference, optional GPS and inbox photo paths are delivered to its `public_reports` table. These photo endpoints follow the configured inbox access mode. Photo bytes remain on PLiZ. Back up SQLite to retain photographs and the delivery queue; DBStudios alone cannot restore them. See [DBStudios reports](DBSTUDIOS_REPORTS.md).

No uploaded photographs are placed in the repository or a public asset folder. The report reference is a display identifier, not an access credential; clearing browser storage or changing devices loses access. Cross-device recovery and accounts are not implemented.

## Validation and demo boundaries

- Location: 3–160 characters; description: 10–2,000 characters, with surrounding whitespace trimmed.
- Up to 3 images, 8 MB per input image; request bodies are bounded before multipart parsing.
- Browser resizing produces JPEG images with a maximum dimension of 1,600 pixels. HEIC works only if the browser can decode it; otherwise the UI requests JPG, PNG or WebP.
- The backend independently decodes JPEG/PNG/WebP, rejects invalid files and inputs over 24 megapixels, resizes, and re-encodes without EXIF/GPS metadata.
- Submitted GPS is stored only when explicitly attached. Text entered by the user is not automatically anonymised.
- The same-browser daily submission limit is 20. This is a demo guard, not comprehensive abuse protection: rotating browser keys bypasses it. Internet-scale rollout needs stronger rate limits, storage quotas, individual operator accounts and retention controls.
- Existing deployment authentication and origin rules still apply; this feature does not bypass private deployment settings.
- New reports start at `received`. The inbox reflects statuses stored in DBStudios, including `in_review` and `resolved`. There is no staff status-edit or dispatch endpoint. My reports shows the local receipt and delivery state; it does not sync later status edits from DBStudios.
- Unsubmitted forms remain in memory while switching public tabs. Refreshing the page discards an unsent form. There is no offline browser submission queue. Once the server saves a report, its durable queue retries DBStudios delivery after outages.

## Verification

```powershell
npm run build
./.venv/Scripts/python.exe -m pytest tests -q -k "not export"
```

The existing GitHub Actions workflow already runs the build and discovers the public API tests. Tests use a temporary database with cloud credentials disabled. They cover photographs, metadata stripping, cross-browser isolation, idempotent retries, validation, upload limits, origin checks, daily limits, DBStudios outages/retries, long text/GPS preservation and production operator authentication.

Browser verification: mobile layout, photo upload, category/details, review, successful save, and report/photo retrieval after reload. Physical camera hardware and GPS permissions need testing on an actual phone.

## GitHub handoff

Commit both feature folders, the backend module, tests, documentation, `.env.example`, deployment tooling, and the integration changes to `src/main.tsx`, `src/App.tsx`, `backend/main.py` and `requirements.txt`. The current `.gitignore` excludes `storage/`, `.env`, `dist/`, `node_modules/`, `deploy/private/`, local logs and test artifacts. Do not include databases, browser access keys, complaint photos or environment secrets.
