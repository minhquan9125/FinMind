"""Freeze and run one new check of the fixed resolution; no fitting/calibration."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.documents.embeddings import get_embedding_service
from src.retrieval_orchestration.intent_composition import requests
from src.retrieval_orchestration.intent_request_consensus import resolve
from src.retrieval_orchestration.intent_scoring import classifier_probabilities,rankings
from src.retrieval_orchestration.intent_library import load_library
from src.retrieval_orchestration.intent_matching import IntentMatcher
from prepare_s5_intent_scorer import sha,write,read_rows
from run_s5_intent_consensus import stats

PARENT=ROOT/'outputs/s5_intent_composition_20261112'
OUT=PARENT/'new-check'
TEMPLATES={
 'NUMERIC':['Chi phí lãi vay của {c} trong năm 2020 là bao nhiêu?', 'Cho biết giá trị hàng tồn kho {c} tại 30/06/2020.', 'Tỷ lệ chi trả cổ tức của {c} năm 2020 bằng bao nhiêu phần trăm?'],
 'REPORT_CONTENT':['BCTN {c} năm 2020 mô tả định hướng chuyển đổi số như thế nào?', 'Giải thích phương pháp ghi nhận hàng tồn kho trong thuyết minh BCTC {c} năm 2020.', 'Trích nguyên văn đoạn cam kết về an toàn lao động trong BCTN {c} năm 2020.'],
 'NEWS':['Tìm các bản tin về {c} ký hợp đồng xuất khẩu trong tháng 08/2020.', 'Tóm lược bài báo về {c} triển khai dự án đăng ngày 12/09/2020.', 'Cho danh sách bài tin {c} phát hành trái phiếu trong quý III/2020.'],
 'PERSON_ROLE':['Ai giữ chức Phó Tổng giám đốc {c} tại cuối năm 2020?', 'Ông Lâm được bổ nhiệm làm Giám đốc tài chính {c} vào ngày nào trong năm 2020?', 'Ai đảm trách vị trí kế toán trưởng {c} cuối 2020? Trích câu làm bằng chứng cho câu trả lời.'],
 'ENTITY_RELATION':['Doanh nghiệp nào nắm cổ phần chi phối {c} tại cuối năm 2020?', 'Liệt kê các đơn vị do {c} kiểm soát tại 30/06/2020.', 'Có bao nhiêu công ty liên kết của {c} tại cuối năm 2020?'],
 'TREND':['Nhận định đà cải thiện biên lợi nhuận {c} trong các năm 2017–2020 có ổn định không?', 'Diễn biến giá {c} và dòng tiền kinh doanh trong 2017–2020 cho tín hiệu cùng chiều hay trái chiều?', 'Đánh giá chiều hướng ROA {c} qua các năm 2017–2020.'],
 'MIXED':['Ai giữ chức Phó Tổng giám đốc {c} cuối 2020? BCTN {c} mô tả định hướng chuyển đổi số như thế nào?', 'Cho biết chi phí lãi vay {c} năm 2020 và tìm các bản tin phát hành trái phiếu {c} quý III/2020.', 'Liệt kê các đơn vị do {c} kiểm soát cuối 2020 rồi hãy lấy giá trị doanh thu 2020 của từng đơn vị.']}


def main():
    if OUT.exists(): raise FileExistsError('NEW_CHECK_ALREADY_ATTEMPTED')
    scorer=ROOT/'outputs/s5_intent_scorer_20261112'
    fit=ROOT/json.loads((scorer/'fit-location.json').read_text())['output']
    parent_summary=json.loads((PARENT/'consensus-v2/summary.json').read_text())
    if not parent_summary['passes_gate']: raise ValueError('DEVELOPMENT_GATE_NOT_PASSED')
    metadata=json.loads((scorer/'method.json').read_text())
    labels=json.loads((fit/'summary.json').read_text())['labels']
    parameters=np.load(fit/'parameters.npz',allow_pickle=False)
    cases=[dict(id=f'NEW-{label}-{i}-{company}',text=text.format(c=company),intent_label=label,
             family_id=f'NEW-{label}-{i}',company=company,split='FINAL_CHECK_ONLY')
           for label,phrases in TEMPLATES.items() for i,text in enumerate(phrases,1) for company in ['VHC','DBC']]
    training=read_rows(scorer/'training.jsonl')
    if {r['text'].casefold() for r in cases}&{r['text'].casefold() for r in training}: raise ValueError('TEST_TRAIN_OVERLAP')
    parts=[requests(r['text']) for r in cases]
    texts=sorted({r['text'] for r in cases}|{q for spans in parts for q in spans})
    original_dir=ROOT/'outputs/s5_wbs033_20261110/intent-library-v1'
    watched=[fit/'parameters.npz',PARENT/'consensus-v2/method.json',PARENT/'consensus-v2/summary.json',
             ROOT/'backend/src/retrieval_orchestration/intent_request_consensus.py',
             ROOT/'backend/src/retrieval_orchestration/intent_composition.py',
             ROOT/'backend/src/retrieval_orchestration/intent_scoring.py',Path(__file__),*original_dir.iterdir()]
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in watched if p.is_file()}
    OUT.mkdir()
    write(OUT/'method.json',dict(status='FROZEN_BEFORE_CHECK',source_hashes=hashes,rows=42,
           authored_by_same_agent=True,blind_test=False,no_fit=True,no_calibration=True,
           model=metadata['model'],confidence=None,one_check_after_frozen_development=True))
    write(OUT/'cases.json',cases); write(OUT/'request-parts.json',parts); write(OUT/'texts.json',texts)
    encoder=get_embedding_service()
    expected=metadata['model']
    if (encoder.model_name,encoder.revision)!=(expected['name'],expected['revision']): raise ValueError('MODEL_MISMATCH')
    print(f'Encoding {len(texts)} texts for 42 frozen new cases; no fitting.',flush=True)
    vectors=np.asarray(encoder.embed_texts(texts),dtype=np.float32)
    if vectors.shape!=(len(texts),1024) or not np.isfinite(vectors).all(): raise ValueError('INVALID_VECTORS')
    np.save(OUT/'vectors.npy',vectors,allow_pickle=False)
    lookup=dict(zip(texts,vectors))
    raw=classifier_probabilities(np.stack([lookup[r['text']] for r in cases]),parameters['coefficients'],parameters['intercepts'])
    original=IntentMatcher(load_library(original_dir),encoder)
    baseline=[original._rank(r['text'],lookup[r['text']],7,5) for r in cases]
    raw_ranking=rankings([r['text'] for r in cases],raw,labels,'intent-linear-v1','CLASSIFIER_PROBABILITY_UNCALIBRATED',expected)
    results=[]
    for i,(case,spans) in enumerate(zip(cases,parts)):
        component=classifier_probabilities(np.stack([lookup[q] for q in spans]),parameters['coefficients'],parameters['intercepts']) if spans!=[case['text']] else []
        decision=resolve(raw[i],component,labels)
        results.append(dict(id=case['id'],question=case['text'],gold=case['intent_label'],
               final_label=decision['intent_label'],resolution=decision,base_ranking=raw_ranking[i],
               original_ranking=baseline[i],parts=spans,
               component_probabilities=np.asarray(component).tolist()))
    metrics={name:stats([dict(r,final_label=(r['original_ranking']['groups'][0]['intent_label'] if name=='original'
                         else r['base_ranking']['groups'][0]['intent_label'] if name=='linear' else r['final_label'])) for r in results],labels)
             for name in ['original','linear','consensus']}
    old_correct_to_wrong=[r['id'] for r in results if r['base_ranking']['groups'][0]['intent_label']==r['gold']!=r['final_label']]
    for name,digest in hashes.items():
        if sha(ROOT/name)!=digest: raise ValueError('SOURCE_CHANGED_DURING_CHECK')
    write(OUT/'results.json',results)
    write(OUT/'summary.json',dict(status='COMPLETED_ONE_NEW_CHECK_NOT_E2E_APPROVAL',metrics=metrics,
         linear_correct_to_wrong=old_correct_to_wrong,confidence=None,
         calibrated=False,runtime_unchanged=True,no_legacy_threshold_applied=True))
    print(json.dumps(dict(correct={name:m['correct'] for name,m in metrics.items()},linear_correct_to_wrong=old_correct_to_wrong),indent=2))


if __name__=='__main__': main()
