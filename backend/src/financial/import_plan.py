"""Evidence-bound import planning. Unknown inputs stay unverified, never guessed."""
from collections import Counter
from decimal import Decimal
import json
import uuid

from .config_validation import fingerprint
from .source_rule_review import validate_review_package
from .reviewed_mapping import DATA
from .inferred_units import load_inferred_unit_overrides

NS=uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea')


def load_rules(path):
    bundle=json.loads(path.read_text(encoding='utf-8'))
    errors=validate_review_package(bundle)
    if errors:raise ValueError(f'Invalid source rule package: {errors}')
    return bundle


def make_plan(item, bundle, workbook_overrides=None):
    """Certify only exact clean-file snapshots, periods, values and source identities."""
    samples={s['sample_id']:s for s in bundle['samples']}
    manifest=bundle['manifest_sha256']
    config_id=str(uuid.uuid5(NS,f'financial-import-config:{manifest}'))
    data=item['data'];provider=data['nguồn_dữ_liệu'].get('nguồn_tài_chính')
    index={}
    for rule in bundle['rules']:
        for sid in rule['verified_samples']:
            sample=samples[sid]
            key=(sample['symbol'],sample['provider_period'],sample['source_code'])
            if key in index:raise ValueError('Ambiguous reviewed sample identity')
            index[key]=(rule,sample)
    entries=[]
    for period,section,metric,value in item['values']:
        code=metric['mã_chuẩn'];field=metric['trường_gốc']
        matches=[r for r in bundle['rules'] if item['symbol'] in r['symbols']
                 and r['industry']==data['ngành'] and r['source_code']==code
                 and r['source_field']==field and r['section']=={'balance_sheet':'BALANCE_SHEET'}.get(section)]
        entry=dict(period=period,section=section,code=code,source_field=field,
                   source_value=str(value),unit='SOURCE_NATIVE',scale=1,currency=None,
                   status='UNVERIFIED',reason='NO_REVIEWED_RULE')
        candidate=index.get((item['symbol'],period,code)) if section=='balance_sheet' else None
        if matches and not candidate:entry['reason']='PERIOD_NOT_IN_VERIFIED_SAMPLES'
        if candidate:
            rule,sample=candidate
            reason=None
            if rule not in matches or provider!=rule['source_provider']:reason='SOURCE_CONTEXT_MISMATCH'
            elif item['digest']!=sample['file_hashes']['clean']:reason='INPUT_SNAPSHOT_CHANGED'
            elif data['nguồn_dữ_liệu'].get('sha256_nguồn')!=sample['file_hashes']['normalized']:reason='SOURCE_PROVENANCE_CHANGED'
            elif value!=Decimal(sample['json_value']):reason='VALUE_CHANGED'
            if reason:entry['reason']=reason
            else:
                entry.update(status='VERIFIED_SNAPSHOT',reason=None,unit='VND',currency='VND',
                    financial_mapping=dict(schema_version='financial-mapping-locator-v1',
                        config_version_id=config_id,mapping_manifest_sha256=manifest,
                        mapping_rule_id=rule['mapping_rule_id'],definition_sha256=rule['definition_sha256'],
                        canonical_metric_code=rule['canonical_metric_code'],source_provider=provider,
                        source_field=field,source_schema_version=rule['source_schema_version'],
                        evidence_sample_id=sample['sample_id'],evidence_id=sample['evidence_id'],
                        as_of=sample['as_of'],scope=sample['report_scope'],period_basis='POINT_IN_TIME',
                        unit_status='VERIFIED_SNAPSHOT',conversion_factor='1',
                        source_value=str(value),source_unit='VND'))
        if workbook_overrides:
            approved=workbook_overrides.get((item['symbol'],period,section,code))
            if approved:
                if approved.get('source_field') != field or Decimal(approved['source_value']) != value:
                    raise ValueError('WORKBOOK_APPROVED_VALUE_MISMATCH')
                entry.update(
                    status='WORKBOOK_APPROVED',
                    reason=None,
                    unit=approved['inferred_unit'],
                    scale=approved['inferred_scale'],
                    currency=approved['inferred_currency'],
                    financial_mapping=dict(
                        schema_version='financial-mapping-locator-v1',
                        config_version_id=config_id,
                        mapping_manifest_sha256=manifest,
                        status='WORKBOOK_APPROVED',
                        source_field=field,
                        source_value=str(value),
                        unit_status='WORKBOOK_APPROVED',
                        source_unit=approved['inferred_unit'],
                        conversion_factor=str(approved['inferred_scale']),
                        approval_basis=approved['approval_basis'],
                        citation_allowed=False,
                    ),
                )
        entries.append(entry)
    return dict(schema_version='financial-import-plan-v1',symbol=item['symbol'],
        file_sha256=item['digest'],config_version_id=config_id,mapping_manifest_sha256=manifest,
        rules_release_status=bundle['release_status'],database_writes=False,
        entries=entries,counts=dict(Counter(e['status'] for e in entries)),
        reasons=dict(Counter(e['reason'] for e in entries if e['reason'])))


def load_workbook_approved_overrides(path):
    return load_inferred_unit_overrides(path)


async def require_frozen_configuration(conn, plans, bundle):
    """A local evidence package alone cannot enable writes to the shared database."""
    config_id=uuid.UUID(plans[0]['config_version_id'])
    row=await conn.fetchrow('SELECT frozen_at FROM public.config_versions WHERE config_version_id=$1',config_id)
    if not row or row['frozen_at'] is None:
        raise ValueError('Financial configuration is not registered and frozen in Supabase; run offline plan only')
    stored=await conn.fetchval('SELECT config_value FROM public.system_configs WHERE config_version_id=$1 AND config_key=$2',
                              config_id,'financial.source_mapping')
    stored=json.loads(stored) if isinstance(stored,str) else stored
    if stored!=bundle:raise ValueError('Registered financial mapping differs from reviewed package')
    expected=release_values(bundle)
    for key in ('financial.metric_catalogue','financial.unit_rules','financial.mapping_manifest'):
        value=await conn.fetchval('SELECT config_value FROM public.system_configs WHERE config_version_id=$1 AND config_key=$2',config_id,key)
        value=json.loads(value) if isinstance(value,str) else value
        if value!=expected[key]:raise ValueError(f'Frozen configuration missing or mismatched: {key}')


def release_values(bundle):
    """Concrete JSON values for review before registering/freeze; does not write DB."""
    links=json.loads(DATA.read_text(encoding='utf-8'))['links']
    catalogue={}
    for rule in bundle['rules']:
        targets=[r['target'] for r in links if r['industry_scope']==rule['industry']
                 and r['section']==rule['section'] and r['code']==rule['source_code'] and r.get('target')]
        if len(targets)!=1 or fingerprint(targets[0])!=rule['definition_sha256']:
            raise ValueError('Catalogue definition has changed since evidence review')
        catalogue[(rule['industry'],rule['canonical_metric_code'])]=targets[0]
    definitions=[catalogue[k] for k in sorted(catalogue)]
    units=[dict(rule_id=r['mapping_rule_id']+':unit',mapping_rule_id=r['mapping_rule_id'],
        source_unit='VND',standard_unit='VND',factor='1',currency='VND',dimension='money',
        applicability='EXACT_VERIFIED_SNAPSHOTS_ONLY') for r in bundle['rules']]
    manifest=dict(schema_version='financial-import-release-v1',mode='VERIFIED_SNAPSHOT_IMPORT',
        mapping_manifest_sha256=bundle['manifest_sha256'],catalogue_sha256=fingerprint(definitions),
        unit_rules_sha256=fingerprint(units),unverified_policy='PRESERVE_NATIVE_WITH_STATUS')
    return {'financial.source_mapping':bundle,'financial.metric_catalogue':definitions,
            'financial.unit_rules':units,'financial.mapping_manifest':manifest}
