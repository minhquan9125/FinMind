# Company report documents

This pipeline keeps annual reports separate from the Vietcap financial-statement JSON pipeline.

## Vietstock annual reports

The page shown in the browser is [VietstockFinance — Báo cáo thường niên](https://finance.vietstock.vn/tai-lieu/bao-cao-thuong-nien.htm). The page loads its report list from Vietstock's website endpoints (`getrptdoctype`, `getrptterm`, `getrptfile`); this is an observed website interface, **not a documented partner API**. The collector uses the page's normal session and anti-forgery token, applies request pacing, follows only Vietstock-hosted file links, and does not bypass login, CAPTCHAs, or access restrictions.

Run from the repository root:

```powershell
# Save metadata and direct source URLs for the latest seven years
backend/.venv/Scripts/python.exe data_pipeline/annual_reports/vietstock_download_annual.py --catalog-only

# Download the latest two report years (2024–2025) for the default 10-company scope
backend/.venv/Scripts/python.exe data_pipeline/annual_reports/vietstock_download_annual.py --download

# Explicitly download the full catalog range only when needed
backend/.venv/Scripts/python.exe data_pipeline/annual_reports/vietstock_download_annual.py --years 2019,2020,2021,2022,2023,2024,2025 --download

# Limit symbols and years
backend/.venv/Scripts/python.exe data_pipeline/annual_reports/vietstock_download_annual.py --symbols BID,VCB --years 2024,2025 --download
```

The manifest is `data/references/vietstock/annual_reports/manifest.json`. Downloaded files are stored under `files/{SYMBOL}/{YEAR}/`; ZIPs are retained and PDF members are extracted with path traversal checks. The manifest records the title, year, direct source URL, provider document ID, source update time, file hash, local paths, and collection status. Generated binary files are ignored by Git; the manifest and scripts remain reviewable.

## Google Drive storage for PDFs

The configured destination is folder `1B-sy-qNIAJOJaQLYv84ezf5Zgp8EjTRA` from the supplied Drive link. PDFs are organized as `cào_PDF/{SYMBOL}/{YEAR}/{PDF}` for the 10 default symbols. Existing flat Drive PDFs are moved into these folders during sync. A folder link only identifies the destination; the scripts need OAuth authorization from the Google account that can edit it. Create a Google Cloud **Desktop app** OAuth client, enable the Drive API, download its client JSON, and keep it outside Git. Install the dependencies from `requirements-ocr.txt` and set `FINMIND_DRIVE_CLIENT_SECRET` to the JSON file path, or save it as the ignored repository-root `.drive-client-secret.json`. On the first Drive command, sign in through the browser; the refresh token is stored in the ignored repository-root `.drive-token.json` (override with `FINMIND_DRIVE_TOKEN_FILE`). Never paste either JSON file into chat or commit it.

```powershell
# Example: point to the Desktop app OAuth client JSON saved on your machine.
$env:FINMIND_DRIVE_CLIENT_SECRET = "D:\private\finmind-drive-oauth.json"
python -m pip install -r data_pipeline/annual_reports/requirements-ocr.txt

# First upload the PDFs already in the manifest. This does not contact Vietstock or delete local PDFs.
python data_pipeline/annual_reports/vietstock_download_annual.py --drive-sync-existing

# After checking the manifest's drive_files entries, a later run can remove verified local copies.
python data_pipeline/annual_reports/vietstock_download_annual.py --drive-sync-existing --drive-prune-local

# Future crawls: upload each PDF and remove its local copy only after the Drive copy and manifest are verified.
python data_pipeline/annual_reports/vietstock_download_annual.py --download --drive-upload --drive-prune-local

# OCR works with local PDFs or downloads a verified temporary copy from Drive when local files are absent.
python data_pipeline/annual_reports/OCR_annuals.py --symbols FPT --years 2024
```

Each PDF's Drive ID, name, size and hashes are stored under `drive_files` in the manifest. ZIP/RAR archives are only removed by `--drive-prune-local` after every PDF member has been uploaded and the manifest has been saved. OCR deletes the downloaded temporary PDF on completion or error. The Git tracked PDF history is separate: moving files to Drive does not shrink old Git commits, and tracked PDFs are not removed from Git by these commands.

## Text extraction and OCR

If the manifest still points at `files/` but local PDFs have been moved to
`files_pdf/`, the extractor resolves the matching mirror automatically while
retaining the manifest path as provenance. If one manifest PDF path is not
present locally, the extractor reports that path and continues processing the
other PDFs in the same record. Use `--output-root tmp/ocr-pilot` for a
trial that leaves the existing `extracted/` corpus untouched. Pages with a
garbled text layer are sent to OCR; the original layer is preserved as
`text_layer_raw` and marked `BROKEN_TEXT_LAYER` for review.

Run extraction from the repository root. Native PDF text is preferred; Tesseract OCR handles pages without usable text:

```powershell
python data_pipeline/annual_reports/OCR_annuals.py --symbols FPT --years 2024
```

To normalize existing OCR text without running OCR again:

```powershell
python data_pipeline/annual_reports/OCR_annuals.py --symbols FPT --years 2024 --reclean-existing-json
```

The extractor uses Tesseract with Vietnamese and English (`vie+eng`, page segmentation mode 3) for pages without a usable text layer. When that mode finds no text, it retries the rendered page with mode 6 and marks any result for review. It keeps the original PDF unchanged and writes page text plus provenance JSON under `extracted/`. Each OCR page preserves Tesseract output in `text_raw`; the extractor's initial `text_clean` only applies Unicode NFC, hidden-character removal, and whitespace collapse. Gemini then reads `text_raw` directly and replaces `text_clean`. BCTN content is not merged into the BCTC API JSON.

Tesseract is a system program, so installing Python packages alone does not install it. On Windows, install Tesseract OCR and include both English and Vietnamese language data. Then verify that `tesseract --list-langs` lists `eng` and `vie`. The Python dependencies are:

```bash
python -m pip install -r data_pipeline/annual_reports/requirements-ocr.txt
```

If `tesseract` is not on PATH, pass its full executable path with `--tesseract`. Poppler's `pdftoppm` is also needed to render scanned PDF pages. To rerun FPT 2024 and 2025 with Tesseract, add `--force` so existing OCR pages are replaced:

```powershell
python data_pipeline/annual_reports/OCR_annuals.py --symbols FPT --years 2024,2025 --force --pdftoppm "C:\Users\pc\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe" --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## Gemini OCR text cleaning

The Gemini cleaner reads `page.text_raw` and writes its cleaned result directly to `page.text_clean`. The original `text_raw` is preserved. It does not render or send PDF pages. The cleaner asks Gemini not to guess unclear words or change numbers; a numeric-token mismatch prevents that page's `text_clean` from being written. This check does not prove all wording is correct, so spot-check results against the PDF.

Set the API key in the ignored repository-root `.env.local` or `.env` file (do not commit or paste the key into chat):

```text
GEMINI_API_KEY=your_key_here
```

Install the SDK and clean pages that already contain Tesseract OCR text:

```powershell
python -m pip install -r data_pipeline/annual_reports/requirements-ocr.txt
python data_pipeline/annual_reports/model_gemini.py --symbols FPT --years 2024
```

For a pilot extraction written with `--output-root`, pass the same directory to
the cleaner. `--pages` can limit a model check to specific PDF page numbers.

The default model is `gemini-3.8-flash`; override it with `--model` or `GEMINI_MODEL`. Providers are tried in this order: Gemini, Groq, another configured OpenAI-compatible API, then local Qwen through Ollama. Configure Groq with `GROQ_API_KEY`; optionally set `GROQ_MODEL` (default `openai/gpt-oss-20b`) and `GROQ_BASE_URL` (default `https://api.groq.com/openai/v1`). If `GROQ_API_KEY` is absent and the existing `OAI_BASE_URL` points to `api.groq.com`, the cleaner reuses `OAI_API_KEY` but uses the Groq model setting/default. The Groq request uses JSON output, limits generation to 4096 tokens, and validates numeric tokens before saving. The separate OpenAI-compatible provider still requires `OAI_BASE_URL`, `OAI_MODEL`, and `OAI_API_KEY`. Qwen requires Ollama and the model installed locally; it does not require another API key. Install Ollama from https://ollama.com/download/windows, then run `ollama pull qwen2.5:7b-instruct`. Pages already cleaned by Gemini, Groq, OpenAI-compatible, or Qwen are skipped unless `--refresh` is given.

For temporary Gemini service errors, the cleaner now tries stable `gemini-3.7-flash` before older Flash models. The default remains `gemini-3.8-flash`.

The default 2019–2025 range follows the seven year tabs visible on the supplied Vietstock page at implementation time. Use `--years` to make a different reporting-year scope explicit. A missing report is recorded as `NO_REPORT`; it is not silently treated as a failed download.
