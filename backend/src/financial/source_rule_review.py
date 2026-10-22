"""Validate evidence packaging; this module does not activate production rules."""
from decimal import Decimal, InvalidOperation
import re

from .config_validation import fingerprint


def validate_review_package(bundle):
    errors=[]
    body={k:v for k,v in bundle.items() if k!='manifest_sha256'}
    if bundle.get('manifest_sha256')!=fingerprint(body):errors.append('MANIFEST_MISMATCH')
    if bundle.get('schema_version')!='financial-source-rules-review-v1':errors.append('INVALID_SCHEMA')
    if bundle.get('production_enabled') is not False:errors.append('REVIEW_PACKAGE_CANNOT_ACTIVATE_PRODUCTION')
    if bundle.get('release_status')!='REVIEW_PACKAGE_NOT_PRODUCTION_CONFIGURATION':errors.append('INVALID_RELEASE_STATUS')
    samples={};used=set();rule_ids=set();identities=set()
    cases={}
    for c in bundle.get('cases',[]):
        if c['evidence_id'] in cases:errors.append('DUPLICATE_EVIDENCE')
        cases[c['evidence_id']]=c
        if not re.fullmatch('[a-f0-9]{64}',c.get('pdf_sha256','')):errors.append('INVALID_PDF_HASH')
    for s in bundle.get('samples',[]):
        if s['sample_id'] in samples:errors.append('DUPLICATE_SAMPLE')
        samples[s['sample_id']]=s
        c=cases.get(s['evidence_id'])
        if (not c or c.get('status')!='VERIFIED_BOUNDED_SNAPSHOT' or
            any(s.get(a)!=c.get(b) for a,b in [('symbol','symbol'),('provider_period','period'),('as_of','as_of'),('report_scope','scope')])):
            errors.append('SAMPLE_EVIDENCE_CONTEXT_MISMATCH')
        if any(not re.fullmatch('[a-f0-9]{64}',s.get('file_hashes',{}).get(k,'')) for k in ('raw','normalized','clean')):
            errors.append('MISSING_SOURCE_HASH')
        try:
            values=[Decimal(s[k]) for k in ('report_value','report_scale','json_value','json_to_standard_factor')]
            if not all(v.is_finite() for v in values) or values[1]<=0 or values[3]!=1 or values[0]*values[1]!=values[2]:
                errors.append('SAMPLE_SCALE_MISMATCH')
        except (KeyError,InvalidOperation,TypeError):errors.append('INVALID_SAMPLE_NUMBER')
    for r in bundle.get('rules',[]):
        identity=(r.get('source_provider'),r.get('industry'),r.get('section'),tuple(r.get('symbols',[])),r.get('source_field'))
        if r.get('mapping_rule_id') in rule_ids or identity in identities:errors.append('DUPLICATE_RULE')
        rule_ids.add(r.get('mapping_rule_id'));identities.add(identity)
        if r.get('production_enabled') is not False or r.get('activation_status')!='REVIEWED_SNAPSHOTS_ONLY':
            errors.append('RULE_CANNOT_ACTIVATE_PRODUCTION')
        if r.get('unknown_snapshot_policy')!='REQUIRE_EXPLICIT_REVIEW':errors.append('UNKNOWN_SNAPSHOT_NOT_BLOCKED')
        if r.get('factor')!='1' or r.get('source_unit')!='VND' or r.get('standard_unit')!='VND':
            errors.append('UNVERIFIED_JSON_CONVERSION')
        if not re.fullmatch('[a-f0-9]{64}',r.get('definition_sha256','')):errors.append('MISSING_DEFINITION_HASH')
        if not r.get('verified_samples'):errors.append('NO_RULE_EVIDENCE')
        for sid in r.get('verified_samples',[]):
            s=samples.get(sid)
            if sid in used:errors.append('SAMPLE_ASSIGNED_MULTIPLE_TIMES')
            used.add(sid)
            if not s or s['symbol'] not in r['symbols'] or any(s.get(k)!=r.get(k) for k in
                ('industry','source_field','source_code','canonical_metric_code')) or s['report_scope']!=r['scope']:
                errors.append('RULE_SAMPLE_SCOPE_MISMATCH')
    if used!=set(samples):errors.append('ORPHAN_OR_MISSING_SAMPLE')
    return errors
