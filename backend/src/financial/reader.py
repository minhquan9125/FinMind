"""Read one explicitly selected financial version; no automatic latest-version merge."""
from decimal import Decimal, InvalidOperation
import json
import uuid

from .import_plan import require_frozen_configuration, release_values
from .source_rule_review import validate_review_package

SQL="""
SELECT fr.report_id::text, c.symbol, rp.period_code, m.section,m.code,m.canonical_name,
       m.industry_scope,o.observation_id::text,o.metric_id::text,o.value,o.unit,o.scale,o.currency,o.locator_json,
       fr.payload_id::text,fr.job_id::text,fr.statement_scope,fr.report_version,fr.restated_from_id::text,
       p.source_uri,p.sha256 AS payload_sha256,p.job_id::text AS payload_job_id,
       j.schema_version AS ingestion_schema
FROM public.financial_reports fr
JOIN public.companies c USING(company_id)
JOIN public.reporting_periods rp USING(period_id)
JOIN public.observations o USING(report_id)
JOIN public.metrics m USING(metric_id)
LEFT JOIN public.raw_payloads p ON p.payload_id=fr.payload_id
LEFT JOIN public.ingestion_jobs j ON j.job_id=fr.job_id
WHERE c.symbol=$1 AND rp.period_code=$2
ORDER BY fr.report_id,m.section,m.code,o.observation_id
"""


class FinancialReadError(ValueError):pass


def locator(row):
    value=row.get('locator_json') or {}
    value=json.loads(value) if isinstance(value,str) else value
    if not isinstance(value,dict):raise FinancialReadError('INVALID_LOCATOR')
    return value


def source_family(row):
    """Recognize ingestion provenance, not report counts or changing metric names."""
    schema = row.get('ingestion_schema')
    uri = (row.get('source_uri') or '').replace('\\', '/')
    if schema == 'clean-v1' and uri.endswith('/tai_chinh_clean.json'):
        return 'clean'
    if schema in ('1.0', 'normalized-financial-v2') and uri.endswith('#financial_data'):
        return 'normalized'
    return 'unknown'


def select_report_rows(rows, *, symbol, period_code, config_version_id=None, report_id=None,
                       source_family_name=None, payload_id=None):
    """Also validate filtering in Python, so mixed results cannot be summed silently."""
    selected=[]
    if source_family_name not in (None, 'clean', 'normalized'):
        raise FinancialReadError('INVALID_SOURCE_FAMILY')
    config=str(uuid.UUID(str(config_version_id))) if config_version_id else None
    for record in rows:
        row=dict(record)
        if row['symbol']!=symbol or row['period_code']!=period_code:
            raise FinancialReadError('SOURCE_QUERY_CONTEXT_MISMATCH')
        loc=locator(row);meta=loc.get('financial_mapping')
        if meta is not None and not isinstance(meta,dict):raise FinancialReadError('INVALID_MAPPING_METADATA')
        if config is None:
            if 'financial_mapping' in loc:continue
        elif not meta or meta.get('config_version_id')!=config:
            continue
        if report_id and str(row['report_id'])!=str(report_id):continue
        if source_family_name and source_family(row)!=source_family_name:continue
        if payload_id and str(row.get('payload_id'))!=str(payload_id):continue
        if row.get('payload_job_id') is not None and row['payload_job_id']!=row.get('job_id'):
            raise FinancialReadError('SOURCE_JOB_MISMATCH')
        selected.append(row)
    reports={r['report_id'] for r in selected}
    if len(reports)>1:
        # Legacy normalized ingestion stores each statement as a separate report.
        # Merge only when explicitly requested and provenance identifies ONE batch.
        groups={(r.get('payload_id'),r.get('job_id')) for r in selected}
        can_group=(source_family_name=='normalized' and len(groups)==1
                   and all(r.get('payload_id') and r.get('job_id') for r in selected))
        if not can_group:
            raise FinancialReadError('AMBIGUOUS_REPORT_VERSION: choose source_family and payload_id or report_id; no automatic latest selection')
        if any(r.get('restated_from_id') or r.get('report_version',1)!=1 for r in selected):
            raise FinancialReadError('AMBIGUOUS_REPORT_VERSION: restated reports require explicit report_id')
        scopes={r.get('statement_scope') for r in selected}
        legacy_sections={'BALANCE_SHEET','INCOME_STATEMENT','CASH_FLOW','RATIO'}
        meaningful_scopes=scopes-legacy_sections-{None,'UNKNOWN'}
        if meaningful_scopes and (len(meaningful_scopes)>1 or scopes-meaningful_scopes):
            raise FinancialReadError('INCONSISTENT_REPORT_SCOPE')
        for rid in reports:
            if len({r['section'] for r in selected if r['report_id']==rid})!=1:
                raise FinancialReadError('INVALID_SECTION_REPORT_GROUP')
        for section in {r['section'] for r in selected}:
            if len({r['report_id'] for r in selected if r['section']==section})!=1:
                raise FinancialReadError('AMBIGUOUS_REPORT_VERSION: multiple reports in one section')
    keys=[(r['industry_scope'],r['section'],r['code']) for r in selected]
    if len(keys)!=len(set(keys)):raise FinancialReadError('DUPLICATE_METRIC_IN_SELECTED_REPORT')
    return selected


def interpret_rows(rows, bundle=None, inferred_overrides=None):
    samples={s['sample_id']:s for s in bundle['samples']} if bundle else {}
    rules={r['mapping_rule_id']:r for r in bundle['rules']} if bundle else {}
    definitions={(t['industry'],t['metric_id']):t for t in release_values(bundle)['financial.metric_catalogue']} if bundle else {}
    facts=[]
    for row in rows:
        loc=locator(row);meta=loc.get('financial_mapping')
        try:value=Decimal(str(row['value']))
        except (ValueError,InvalidOperation) as exc:raise FinancialReadError('INVALID_VALUE') from exc
        if not value.is_finite():raise FinancialReadError('NONFINITE_VALUE')
        fact=dict(report_id=str(row['report_id']),observation_id=str(row['observation_id']),
            symbol=row['symbol'],period_code=row['period_code'],section=row['section'],source_code=row['code'],
            source_name=row['canonical_name'],source_value=str(value),source_unit=row['unit'],
            source_scale=row['scale'],source_currency=row['currency'],
            verification_status='UNVERIFIED',reason='LEGACY_NOT_CERTIFIED_BY_THIS_READER',
            standard_value=None,standard_unit=None,canonical_metric_code=None,canonical_name=None,
            scope=None,as_of=None,config_version_id=None)
        fact.update(source_family=source_family(row),payload_id=row.get('payload_id'),
                    job_id=row.get('job_id'),source_uri=row.get('source_uri'),
                    payload_sha256=row.get('payload_sha256'))
        if meta:
            if bundle is None:raise FinancialReadError('FROZEN_MAPPING_REQUIRED')
            if meta.get('schema_version')!='financial-mapping-locator-v1' or not meta.get('config_version_id'):
                raise FinancialReadError('INVALID_MAPPING_METADATA')
            if meta.get('mapping_manifest_sha256')!=bundle['manifest_sha256']:
                raise FinancialReadError('MAPPING_MANIFEST_MISMATCH')
            fact['config_version_id']=meta['config_version_id']
            if meta.get('status')=='UNVERIFIED':
                if row['unit']!='SOURCE_NATIVE' or row['scale']!=1 or row['currency'] is not None:
                    raise FinancialReadError('UNVERIFIED_ROW_UNIT_CHANGED')
                fact['reason']=meta.get('reason','UNVERIFIED')
                override = (inferred_overrides or {}).get(
                    (row['symbol'], row['period_code'], row['section'].lower(), row['code'])
                )
                if override:
                    if override.get('source_field') != loc.get('source_field'):
                        raise FinancialReadError('INFERENCE_SOURCE_FIELD_MISMATCH')
                    if Decimal(str(row['value'])) != Decimal(str(override['source_value'])):
                        raise FinancialReadError('INFERENCE_VALUE_CHANGED')
                    fact.update(
                        verification_status=override['status'],
                        reason=override['reason'],
                        standard_value=str(row['value']),
                        standard_unit=override['inferred_unit'],
                        inferred_unit=override['inferred_unit'],
                        inferred_scale=override['inferred_scale'],
                        inferred_currency=override['inferred_currency'],
                        citation_allowed=override['citation_allowed'],
                    )
            elif meta.get('status')=='WORKBOOK_APPROVED':
                if row['unit']!='VND' or row['scale']!=1 or row['currency']!='VND':
                    raise FinancialReadError('WORKBOOK_APPROVED_ROW_UNIT_CHANGED')
                fact.update(
                    verification_status='WORKBOOK_APPROVED',
                    reason='WORKBOOK_APPROVED_UNIT_MAPPING_NOT_PRIMARY_SOURCE_EVIDENCE',
                    standard_value=str(value),
                    standard_unit='VND',
                    canonical_metric_code=meta.get('canonical_metric_code'),
                    mapping_rule_id=meta.get('mapping_rule_id'),
                    citation_allowed=False,
                )
            else:
                sample=samples.get(meta.get('evidence_sample_id'));rule=rules.get(meta.get('mapping_rule_id'))
                if not sample or not rule or sample['sample_id'] not in rule['verified_samples']:
                    raise FinancialReadError('MAPPING_EVIDENCE_MISSING')
                try:source_value=Decimal(meta.get('source_value','NaN'))
                except (InvalidOperation,TypeError) as exc:raise FinancialReadError('INVALID_SOURCE_VALUE_METADATA') from exc
                checks=(meta.get('mapping_manifest_sha256')==bundle['manifest_sha256'],
                    sample['symbol']==row['symbol'],sample['provider_period']==row['period_code'],
                    row['industry_scope']==rule['industry'],row['section']==rule['section'],
                    sample['source_code']==row['code'],sample['source_field']==loc.get('source_field'),
                    meta.get('canonical_metric_code')==rule['canonical_metric_code'],
                    meta.get('definition_sha256')==rule['definition_sha256'],
                    meta.get('source_provider')==rule['source_provider'],
                    meta.get('scope')==sample['report_scope'],meta.get('as_of')==sample['as_of'],
                    meta.get('evidence_id')==sample['evidence_id'],
                    loc.get('file_sha256')==sample['file_hashes']['clean'],
                    loc.get('source_sha256')==sample['file_hashes']['normalized'],
                    row['unit']=='VND',row['scale']==1,row['currency']=='VND',
                    meta.get('conversion_factor')=='1',meta.get('source_unit')=='VND',
                    meta.get('period_basis')=='POINT_IN_TIME',
                    meta.get('unit_status')=='VERIFIED_SNAPSHOT',
                    value==Decimal(sample['json_value']),value==source_value)
                if not all(checks):raise FinancialReadError('MAPPING_OR_SOURCE_CHANGED')
                definition=definitions[(rule['industry'],rule['canonical_metric_code'])]
                case=next(c for c in bundle['cases'] if c['evidence_id']==sample['evidence_id'])
                fact.update(verification_status='VERIFIED_SNAPSHOT',reason=None,
                    standard_value=str(value),standard_unit='VND',canonical_metric_code=rule['canonical_metric_code'],
                    canonical_name=definition['chosen_name'],scope=sample['report_scope'],as_of=sample['as_of'],
                    period_basis='POINT_IN_TIME',mapping_rule_id=rule['mapping_rule_id'],
                    evidence_id=sample['evidence_id'],issuer_fiscal_year=case['year'],
                    report_column=case.get('column','CLOSING'),mapping_manifest_sha256=bundle['manifest_sha256'])
        facts.append(fact)
    return facts


async def read_financial_facts(conn, symbol, period_code, *, config_version_id=None, report_id=None,
                             source_family_name=None, payload_id=None,corpus_version_id=None,
                             expected_corpus_hash=None,use_default_corpus=True,
                             inferred_overrides=None):
    """Caller owns READ ONLY REPEATABLE READ. Empty selection never falls back."""
    symbol=symbol.strip().upper()
    if corpus_version_id is None and use_default_corpus:
        from ..core.config import get_settings
        settings=get_settings()
        corpus_version_id=settings.default_corpus_version_id
        if corpus_version_id and expected_corpus_hash is None:
            expected_corpus_hash=settings.default_corpus_manifest_sha256
    scope=None
    if corpus_version_id:
        from ..documents.corpus_scope import load_scope
        scope=await load_scope(conn,corpus_version_id,expected_hash=expected_corpus_hash)
    bundle=None
    if config_version_id:
        config_version_id=str(uuid.UUID(str(config_version_id)))
        raw=await conn.fetchval('SELECT config_value FROM public.system_configs WHERE config_version_id=$1 AND config_key=$2',
            uuid.UUID(config_version_id),'financial.source_mapping')
        bundle=json.loads(raw) if isinstance(raw,str) else raw
        if not isinstance(bundle,dict) or validate_review_package(bundle):raise FinancialReadError('INVALID_FROZEN_MAPPING')
        await require_frozen_configuration(conn,[{'config_version_id':config_version_id}],bundle)
    if scope:
        from ..documents.corpus_scope import fact_value_hash,CorpusScopeError
        sql=SQL.replace('SELECT fr.report_id::text','SELECT cf.value_hash,fr.report_id::text',1)
        sql=sql.replace('WHERE c.symbol=$1',
            'JOIN public.corpus_facts cf ON cf.observation_id=o.observation_id AND cf.corpus_version_id=$3\nWHERE c.symbol=$1',1)
        rows=await conn.fetch(sql,symbol,period_code,uuid.UUID(scope.corpus_version_id))
        for row in rows:
            if not row['value_hash'] or fact_value_hash(row)!=row['value_hash'].strip():
                raise CorpusScopeError('CORPUS_FACT_CHANGED','Observation changed since corpus registration')
            # Metric IDs in the current financial ingestion contract are derived
            # from industry/section/code. A global metric edit must not relabel
            # an unchanged value silently inside a frozen corpus.
            expected_metric=uuid.uuid5(uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea'),
                f'metric:{row["industry_scope"]}:{row["section"]}:{row["code"]}')
            if str(expected_metric)!=str(row['metric_id']):
                raise CorpusScopeError('CORPUS_METRIC_IDENTITY_CHANGED','Metric meaning differs from immutable identity')
    else:
        rows=await conn.fetch(SQL,symbol,period_code)
    selected=select_report_rows(rows,symbol=symbol,period_code=period_code,
                                config_version_id=config_version_id,report_id=report_id,
                                source_family_name=source_family_name,payload_id=payload_id)
    facts=interpret_rows(selected,bundle,inferred_overrides)
    if scope:
        for fact in facts:fact['corpus_version_id']=scope.corpus_version_id
    return facts
