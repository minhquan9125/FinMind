"""An opt-in question type: verified facts first, labelled conditional guidance.

Ordinary research, source-bound questions and forecasts keep their own routes.
This module never generates prices, targets, allocations or return promises.
"""
import copy
import re
from .retrieval_flow.intent import _fold

VERSION='conditional-assessment-v1'


def recover_source_facts(result,request):
    """Use exact verified source lines if generated wording cannot be used.

    Scope/source failures stay failures. There is no second generation call and
    every extract still passes the existing support-quote and numeric checks.
    """
    answer=result.get('answering') or {}
    if answer.get('status')=='DRAFT_READY':return result
    allowed={'UNSUPPORTED_CLAIM','INVALID_CITATION','NOT_STATED_IN_SOURCE','GEMINI_UNAVAILABLE',
        'GEMINI_TIMEOUT','PROVIDER_NOT_CONFIGURED','INVALID_GEMINI_RESPONSE','INPUT_LIMIT_EXCEEDED',
        'CALL_LIMIT_EXCEEDED','BUDGET_EXCEEDED','OUTPUT_LIMIT_EXCEEDED','USAGE_LIMIT_EXCEEDED'}
    if answer.get('reason_code') not in allowed:return result
    from ..b1_answering.evidence.citations import prepare_evidence,CitationError
    from ..b1_answering.evidence.grounded import validate_grounded
    try:evidence=prepare_evidence(result.get('evidence_pack'))
    except (CitationError,TypeError,ValueError):return result
    groups={'PRICE':'Giá','PRICE_TREND':'Xu hướng giá','FINANCIAL_HEALTH':'Tình hình tài chính','NEWS':'Tin tức'}
    claims=[];seen=set()
    for eid,item in evidence.items():
        kind=item.get('source_type')
        if kind not in groups or kind in seen:continue
        lines=[line.strip() for line in item['passage'].splitlines() if line.strip()]
        if not lines:continue
        if kind=='PRICE_TREND':
            prefix='Dài hạn:' if request['horizon']=='LONG' else 'Ngắn hạn:'
            quote=next((line for line in lines if prefix in line),None)
        elif kind=='FINANCIAL_HEALTH':
            quote='\n'.join(item['passage'].splitlines()[:3]).strip()
        elif kind=='NEWS':
            title=item.get('title')or''
            quote=title if title and title in item['passage'] else lines[0]
        else:quote=lines[0]
        if not quote or len(quote)>3000:continue
        claim=dict(text=groups[kind]+': '+quote,evidence_ids=[eid],support_quotes=[{'evidence_id':eid,'quote':quote}])
        try:validate_grounded({'claims':[claim]},evidence,result.get('scope'))
        except CitationError:continue
        claims.append(claim);seen.add(kind)
    if not claims:return result
    try:draft=validate_grounded({'claims':claims},evidence,result.get('scope'))
    except CitationError:return result
    reason=answer.get('reason_code')
    manifest=copy.deepcopy(answer.get('manifest') or {})
    manifest.update(response_mode='SOURCE_BOUND_ASSESSMENT_FACTS',generation_failure=reason)
    result['answering']={**answer,**draft,'status':'DRAFT_READY','reason_code':'ASSESSMENT_SOURCE_FACTS',
        'message':'Trả dữ kiện trực tiếp từ nguồn đã kiểm tra khi bản diễn đạt chưa hợp lệ.',
        'manifest':manifest,'trace':answer.get('trace',[])+[{'event':'assessment_source_facts','generation_failure':reason}]}
    return result


def assessment_request(question,context=None):
    norm=_fold(question).strip(' .?!')
    pending=(context or {}).get('_pending_assessment')
    prior=pending or (context or {}).get('_assessment_request')
    if prior and re.fullmatch(r'(?:toi |minh |em )?(?:chon |muon )?(?:ngan han|dai han|luot song)(?: nhe| di)?',norm):
        return {**copy.deepcopy(prior),'horizon':'LONG' if 'dai han' in norm else 'SHORT','blocked':False}
    from .hybrid_router.decision_engine import ScopeResolver,DEFAULT_COMPANIES
    from .input_normalization import registered_symbols
    companies=ScopeResolver().resolve(question).scope.companies
    known=set(registered_symbols())
    bare=any(norm==alias for alias,ids in DEFAULT_COMPANIES.items() if set(ids)&set(companies))
    bare=bare or (len(companies)==1 and norm==companies[0].lower() and companies[0] in known)
    if pending and bare:
        return {**copy.deepcopy(pending),'companies':companies,'blocked':False}
    # News describing corporate acquisitions/buybacks is not a user trade decision.
    if re.search(r'\b(?:bctn|bctc|bao cao|bai bao|bai viet|tin tuc|tin don|thong bao|nghi quyet|theo tin|trong tin|mua lai|co phieu quy|thau tom|sap nhap|ban von|ban tai san|chao ban|phat hanh)\b',norm):
        return None
    if (re.search(r'^tin\b|\b(?:mua (?:cong ty|doanh nghiep|dat|tai san|trai phieu|bao hiem|thiet bi)|ban (?:san pham|dich vu|dat|thiet bi)|ngoai te)\b',norm)
            or any(re.search(r'\b'+re.escape(s.lower())+r'\s+(?:co|da|dang|se)\s+(?:mua|ban)\b',norm) for s in companies)):
        return None
    if re.search(r'\b(?:19|20|21)\d{2}\b',norm):
        return None  # Never substitute today's evidence for a historical request.
    sell=bool(re.search(r'\bbán\b',question,re.I) or re.search(r'\b(?:nen ban|can nhac ban|thoat hang|ra hang)\b',norm)
        or any(re.search(r'\bban\s+(?:co phieu\s+)?'+re.escape(s.lower())+r'\b',norm) for s in companies))
    side='BUY' if re.search(r'\b(?:mua|xuong tien|vao hang)\b',norm) else 'SELL' if sell else None
    if not side:return None
    decision=bool(re.search(r'\b(?:co nen|nen mua|nen ban|nen vao|nen xuong tien|can nhac mua|can nhac ban)\b',norm)
        or re.search(r'\b(?:mua|ban|vao hang|xuong tien|thoat hang|ra hang)\b.*\b(?:duoc|on|hop ly|chua|khong)\b',norm))
    if not decision:return None
    blocked=bool(re.search(r'\b(?:chac chan|dam bao|cam ket|bao lai|gia muc tieu|all in|tat tay|vay tien|margin|bao nhieu tien|bao nhieu phan tram|ty trong|du doan)\b|\b\d+\s*%',norm))
    if not companies and re.search(r'\b(?:vay|the|ma nay|ma do|co phieu nay|cong ty do|mua duoc|ban duoc)\b',norm):
        companies=list((context or {}).get('companies') or [])
    horizon='LONG' if re.search(r'\bdai han\b',norm) else 'SHORT' if re.search(r'\b(?:ngan han|luot song)\b',norm) else 'UNSPECIFIED'
    return dict(side=side,companies=companies,horizon=horizon,blocked=blocked)


def attach_assessment(result,request):
    """Only interpret already cited, validated facts; preserve the factual claims."""
    answer=result.get('answering') or {}
    if answer.get('status')!='DRAFT_READY':return result
    symbol=result['scope']['companies'][0]
    citations={c['evidence_id']:c.get('citation_number') for c in answer.get('citations',[])}
    evidence={i['evidence_id']:i for i in (result.get('evidence_pack') or {}).get('items',[])}
    cited=[evidence[eid] for eid in citations if eid in evidence]
    trend=next((i for i in cited if i.get('source_type')=='PRICE_TREND'),None)
    horizon='200' if request['horizon']=='LONG' else '20'
    label=(((trend or {}).get('snapshot',{}).get('trend',{}).get('horizons') or {}).get(horizon) or {}).get('label')
    reviewed=((trend or {}).get('snapshot',{}).get('trend',{}).get('source') or {}).get('approval_status')=='APPROVED'
    if not reviewed:label=None
    basis=[trend['evidence_id']] if trend and label in ('UP','DOWN','SIDEWAYS') else []
    if request['side']=='BUY':
        if label=='UP':
            view=f'Có thể đưa {symbol} vào danh sách cân nhắc; tín hiệu xu hướng thuận lợi là một yếu tố hỗ trợ, chưa đủ để kết luận mức giá đang hợp lý.'
        elif label=='DOWN':
            view=f'Ưu tiên theo dõi {symbol}; tín hiệu xu hướng giảm hiện chưa hỗ trợ việc cân nhắc mua chỉ dựa trên diễn biến giá.'
        else:
            view=f'Chưa đủ cơ sở từ các dữ kiện đã xác minh để nghiêng về việc mua {symbol}; nên tiếp tục theo dõi thay vì kết luận từ một chỉ báo.'
    else:
        if label=='DOWN':
            view=f'Nếu đang nắm giữ {symbol}, có thể rà soát lại rủi ro theo tín hiệu xu hướng giảm; tín hiệu này chưa đủ để kết luận cần bán ngay.'
        else:
            view=f'Chưa đủ cơ sở từ các dữ kiện đã xác minh để kết luận cần bán {symbol}; cần đối chiếu thêm mục tiêu và thời gian nắm giữ.'
    refs=''.join(f' [{citations[eid]}]' for eid in basis if citations[eid] is not None)
    limitations='Định giá và mức rủi ro phù hợp với bạn chưa được xác định; đánh giá này không bảo đảm lợi nhuận.'
    if trend and not reviewed:limitations+=' Nguồn dữ liệu xu hướng chưa được xác nhận đã duyệt.'
    followup='Bạn đang cân nhắc ngắn hạn hay dài hạn?' if request['horizon']=='UNSPECIFIED' else ''
    interpretation=dict(kind='CONDITIONAL',policy_version=VERSION,side=request['side'],horizon=request['horizon'],
        text=view,basis_evidence_ids=basis,limitations=[limitations])
    answer['conditional_assessment']=interpretation
    answer['draft']+='\n\nNhận định có điều kiện:\n'+view+refs+'\n\n'+limitations+(' '+followup if followup else '')
    answer.setdefault('trace',[]).append({'event':'conditional_assessment','policy_version':VERSION,'basis_evidence_ids':basis})
    answer.setdefault('manifest',{})['assessment_policy_version']=VERSION
    return result
