"""Select exact source spans around a reviewed name, without inventing table rows.

Offsets always address the original quote. Whitespace/case normalization is used
only to find anchors; text returned as evidence is never rewritten.
"""
import re
from .contract.entities import text_view


def person_spans(text, name, known_names):
    view, offsets = text_view(text)
    normalized = {text_view(n)[0].strip(): n for n in known_names if n}
    target = text_view(name)[0].strip()
    if not target:return []
    hits=[]
    for normalized_name in normalized:
        for match in re.finditer(r'(?<!\w)'+re.escape(normalized_name)+r'(?!\w)', view):
            hits.append((match.start(),match.end(),normalized_name))
    # A short name inside another reviewed full name is not the target person.
    hits=[h for h in hits if not any(o[0]<=h[0] and o[1]>=h[1] and o[1]-o[0]>h[1]-h[0] for o in hits)]
    hits.sort()
    spans=[]
    for index,(start,end,who) in enumerate(hits):
        if who!=target:continue
        raw_start,raw_end=offsets[start][0],offsets[end-1][1]
        left=text.rfind('\n',0,raw_start)+1
        # Honorific/title may precede a profile name, but not a preceding person.
        for _ in range(2):
            if left<=0:break
            previous=text.rfind('\n',0,left-1)+1
            line=text[previous:left].strip()
            if not re.match(r'^(?:Ông|Bà|Chủ tịch|Phó |Tổng Giám đốc|Giám đốc|Ủy viên|Thành viên|Kế toán|Trưởng|Người phụ trách|[-•]?\s*(?:Miễn nhiệm|Bổ nhiệm|Bồ nhiệm))',line,re.I):break
            if any(offsets[s][0]>=previous and offsets[e-1][1]<=left for s,e,n in hits if n!=target):break
            left=previous
        right=len(text)
        if index+1<len(hits):
            next_start=offsets[hits[index+1][0]][0]
            right=text.rfind('\n',raw_end,next_start)+1
            if right<=raw_end:right=next_start
        # Do not silently attribute an unreviewed person in an honorific row.
        for other in re.finditer(r'(?m)^\s*(?:Ông|Bà)\b',text[raw_end:right]):
            candidate=raw_end+other.start()
            if candidate>raw_end:right=candidate;break
        lines=text[raw_end:right].splitlines(keepends=True)
        kept=0
        for line in lines:
            if re.match(r'\s*(?:Kinh nghiệm|Quá trình công tác|Trình độ|Năm sinh|Sinh năm|Thông tin chung|Theo dõi chúng tôi|Copyright)',line,re.I):break
            kept+=len(line)
            if kept>1600:break
        right=min(right,raw_end+kept)
        if right<=raw_end:right=raw_end
        snippet=text[left:right].strip()
        if snippet:
            at=text.find(snippet,left,right+1)
            spans.append(dict(start=at,end=at+len(snippet),quote=snippet))
    return spans
