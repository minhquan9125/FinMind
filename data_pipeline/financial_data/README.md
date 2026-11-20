# Cào BCTC riêng

Từ gốc FinMind:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -B data_pipeline/financial_data/run_financial_pipeline.py --financial-only --symbols VCB,BID,CTG,MBB,TCB,FPT,CMG,ELC,ITD,ICT --output-root outputs/financial-captures
```

Chế độ này không gọi giá và không khởi tạo pricecollector. Mặc định cũ nếu không có`--financial-only` vẫn lấygiá+BCTC nhưtrước. Moduleform `python -m data_pipeline.financial_data.run_financial_pipeline` cũngdùngđược. `--output-root` chỉ dùngcùngfinancial-only.

Mỗi batch tạo thưmục mới:4nhóm/mã (KQKD,cânđối,lưuchuyển,ratios),rawresponse/hash,normalized đủtrườngnguồn vàmanifest. Requests tuần tựmin2giây, tốiđa2lần chonetwork/5xx;401/403/429 hoặc5xxRetryAfterdừngbatch. Đây làgiớihạnlocal, khôngcamkếtquota/SLAprovider. LịchautoBCTC/cron chưađượcthiếtlập.

`observations.json` làinput gọn cho bộphântíchhiệncó, chỉmappedcodesđược hỗtrợ; cácfieldkhác vẫnởraw/normalized. Mã nội bộVietcapCTIN làtickerICT, đãkiểmtrađịnhdanh; khôngbỏkiểmtickerlệch. `complete` nghĩacaptuređủ4nhóm/chấtlượngcấutrúc, khôngnghĩanguồnhoặcunit/hợpnhất/lũykếđãđượcphêduyệt.

Chạy báo cáo, thay đườngdẫn thànhobservations thực của batch:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -B backend/scripts/report_financial_health.py --snapshot PATH/observations.json --output outputs/financial-analysis
```

**Chỉ lưu local**, không tựghiPostgreSQL hoặcghìđèdata/raw/data/normalized. CLItrả0nếutấtcảmãcaptuređủ,1nếupartial/failed/blocked; luônxemmanifest. Nguồn khôngtrảmetadatađủthìgiữUNKNOWN/SOURCE_NATIVE, khôngđoán từđộlớnsốhoặcnhãnquý. Snapshotthực12Nov vàbằngchứngfull ở docs/sprint5/CHECKPOINT-BCTC-CAPTURE-2026-11-12.md.
