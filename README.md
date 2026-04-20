# Excel Reconciliation Engine Lite — Shinylive

This is a **Shinylive** version of the Excel Reconciliation Engine Lite.
It is designed for **GitHub Pages** deployment, so the app runs fully in the browser without a Python server.

## What this Lite version does

- Upload **2 files** (`.xlsx` or `.csv`)
- Choose worksheet and header row for Excel files
- Map one match key
- Optionally compare:
  - description
  - code
  - value
- Return basic statuses:
  - `MATCH`
  - `MISSING_IN_FILE_2`
  - `MISSING_IN_FILE_1`
  - `FIELD_MISMATCH`
- Download result as CSV or Excel

## Important note

This is a **browser-side** app.
That means:

- best for **demo / light use / small files**
- large Excel files may feel slow
- `.xlsx` parsing depends on browser-side Python support and can be less stable than normal Streamlit
- if needed, you can later make the public Lite version **CSV-only** for more stability

## Repo structure

```text
.
├─ shinylive-app/
│  └─ app.py
├─ .github/
│  └─ workflows/
│     └─ deploy-pages.yml
└─ requirements.txt
```

## Deploy to GitHub Pages

1. Create a new GitHub repo.
2. Upload these files to the repo root.
3. Go to **Settings → Pages**.
4. Under **Build and deployment**, choose **GitHub Actions**.
5. Push to `main`.
6. GitHub Actions will:
   - install dependencies
   - run `shinylive export shinylive-app docs`
   - publish the `docs` output to GitHub Pages

## Local test

If you want to test locally:

```bash
pip install -r requirements.txt
shinylive export shinylive-app docs
python -m http.server --directory docs 8008
```

Then open:

```text
http://localhost:8008/
```

## Next upgrade ideas

- add Lite → Pro CTA lock
- hide full auditor-ready explanation behind Pro
- add grouped asset logic
- add explanation templates by mismatch type
