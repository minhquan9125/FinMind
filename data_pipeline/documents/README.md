# Company report documents

This pipeline keeps annual reports separate from the Vietcap financial-statement JSON pipeline.

## Vietstock annual reports

The page shown in the browser is [VietstockFinance — Báo cáo thường niên](https://finance.vietstock.vn/tai-lieu/bao-cao-thuong-nien.htm). The page loads its report list from Vietstock's website endpoints (`getrptdoctype`, `getrptterm`, `getrptfile`); this is an observed website interface, **not a documented partner API**. The collector uses the page's normal session and anti-forgery token, applies request pacing, follows only Vietstock-hosted file links, and does not bypass login, CAPTCHAs, or access restrictions.

Run from the repository root:

```powershell
# Save metadata and direct source URLs for the latest seven years
backend/.venv/Scripts/python.exe data_pipeline/documents/vietstock_annual.py --catalog-only

# Download the latest two report years (2024–2025) for the default 10-company scope
backend/.venv/Scripts/python.exe data_pipeline/documents/vietstock_annual.py --download

# Explicitly download the full catalog range only when needed
backend/.venv/Scripts/python.exe data_pipeline/documents/vietstock_annual.py --years 2019,2020,2021,2022,2023,2024,2025 --download

# Limit symbols and years
backend/.venv/Scripts/python.exe data_pipeline/documents/vietstock_annual.py --symbols BID,VCB --years 2024,2025 --download
```

The manifest is `data/references/vietstock/annual_reports/manifest.json`. Downloaded files are stored under `files/{SYMBOL}/{YEAR}/`; ZIPs are retained and PDF members are extracted with path traversal checks. The manifest records the title, year, direct source URL, provider document ID, source update time, file hash, local paths, and collection status. Generated binary files are ignored by Git; the manifest and scripts remain reviewable.

## Text extraction and OCR

Run extraction from the repository root. Native PDF text is preferred; PaddleOCR handles pages without usable text:

```powershell
.venv-paddleocr/Scripts/python.exe data_pipeline/documents/extract_vietstock_annuals.py --symbols FPT --years 2024
```

To normalize existing OCR text without running OCR again:

```powershell
.venv-paddleocr/Scripts/python.exe data_pipeline/documents/extract_vietstock_annuals.py --symbols FPT --years 2024 --reclean-existing-json
```

The extractor uses PaddleOCR for pages without a usable text layer. It keeps the original PDF unchanged and writes page text plus provenance JSON under `extracted/`. Each OCR page preserves PaddleOCR output in `text_raw`; the extractor's initial `text_clean` only applies Unicode NFC, hidden-character removal, and whitespace collapse. Gemini then reads `text_raw` directly and replaces `text_clean`. BCTN content is not merged into the BCTC API JSON.

## Gemini OCR text cleaning

The Gemini cleaner reads PaddleOCR's `page.text_raw` and writes its cleaned result directly to `page.text_clean`. The original `text_raw` is preserved. It does not render or send PDF pages. The cleaner asks Gemini not to guess unclear words or change numbers; a numeric-token mismatch prevents that page's `text_clean` from being written. This check does not prove all wording is correct, so spot-check results against the PDF.

Set the API key in the ignored repository-root `.env.local` or `.env` file (do not commit or paste the key into chat):

```text
GEMINI_API_KEY=your_key_here
```

Install the SDK into the OCR environment and clean pages that already contain PaddleOCR text:

```powershell
.venv-paddleocr/Scripts/python.exe -m pip install -r data_pipeline/documents/requirements-paddleocr.txt
.venv-paddleocr/Scripts/python.exe data_pipeline/documents/correct_annual_ocr_with_gemini.py --symbols FPT --years 2024
```

The default model is `gemini-3.8-flash`; override it with `--model` or `GEMINI_MODEL`. Temporary Gemini errors are retried with exponential backoff, then providers are tried in this order: Gemini, configured OpenAI-compatible API, and local Qwen through Ollama. Enable the OpenAI-compatible provider only when all three values are set: `OAI_BASE_URL`, `OAI_MODEL`, and `OAI_API_KEY` (or pass `--oai-base-url`, `--oai-model`, and `--oai-api-key`). Qwen requires Ollama and the model installed locally; it does not require another API key. Install Ollama from https://ollama.com/download/windows, then run `ollama pull qwen2.5:7b-instruct`. Pages already cleaned by Gemini, OpenAI-compatible, or Qwen are skipped unless `--refresh` is given.

The default 2019–2025 range follows the seven year tabs visible on the supplied Vietstock page at implementation time. Use `--years` to make a different reporting-year scope explicit. A missing report is recorded as `NO_REPORT`; it is not silently treated as a failed download.
