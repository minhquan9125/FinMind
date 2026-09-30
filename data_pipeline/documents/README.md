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

Run text-layer extraction first:

```powershell
backend/.venv/Scripts/python.exe data_pipeline/documents/extract_vietstock_annuals.py
```

Only pages with no usable text are sent to OCR when explicitly requested:

```powershell
backend/.venv/Scripts/python.exe data_pipeline/documents/extract_vietstock_annuals.py --ocr
```

`--ocr` requires OCRmyPDF, Tesseract, and the Tesseract Vietnamese (`vie`) language data installed on the machine. It uses `--skip-text`, keeps the original PDF unchanged, and writes a separate searchable PDF under `searchable/`. Page text and provenance JSON go under `extracted/`. A page with OCR text is still marked as OCR-derived; it must be checked against the source PDF before extracting or mapping financial figures. BCTN content is not merged into the BCTC API JSON.

The default 2019–2025 range follows the seven year tabs visible on the supplied Vietstock page at implementation time. Use `--years` to make a different reporting-year scope explicit. A missing report is recorded as `NO_REPORT`; it is not silently treated as a failed download.
