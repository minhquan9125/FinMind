"""Shared syntax for a company-only continuation; no model or history scan."""
import re
from .retrieval_flow.intent import _fold


def company_continuation(text, companies, aliases=None):
    """Return true only when the turn changes a company, not its subject.

    A bare ticker retains the existing new-topic/clarification contract. Linking
    words or a question suffix make reuse of the last subject explicit.
    """
    norm=_fold(text).strip(' .?!')
    names=list(companies)
    if aliases:
        names += [name for name,targets in aliases.items() if set(targets)&set(companies)]
    if not names:return False
    target='(?:'+'|'.join(re.escape(_fold(n)) for n in sorted(set(names),key=len,reverse=True))+')'
    match=re.fullmatch(r'(?P<link>the con |vay con |con |doi sang |chuyen sang |quay lai |the |vay )?'
        r'(?:ma |cong ty |ngan hang )?'+target+
        r'(?: (?:nam )?(?:19|20|21)\d{2})?'
        r'(?P<tail> thi sao| sao| thi the nao| nhu the nao| the nao)?(?: nhi| nhe| a)?',norm)
    return bool(match and (match['link'] or match['tail']))
