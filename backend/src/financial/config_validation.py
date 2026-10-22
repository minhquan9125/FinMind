"""Offline validation of reviewed inputs; never approve or convert source values."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json

from .reviewed_mapping import RETAINED


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_unit_rule(rule):
    """Reject ambiguous numeric factors and incompatible physical dimensions."""
    errors = []
    for field in ('rule_id', 'source_unit', 'target_unit', 'dimension', 'evidence'):
        if not isinstance(rule.get(field), str) or not rule[field].strip():
            errors.append(f'MISSING_{field.upper()}')
    if rule.get('source_dimension') != rule.get('dimension') or rule.get('target_dimension') != rule.get('dimension'):
        errors.append('INCOMPATIBLE_DIMENSIONS')
    try:
        factor = rule['factor']
        if not isinstance(factor, str):
            raise ValueError('Factor must be an exact decimal string')
        number = Decimal(factor)
        if not number.is_finite() or number <= 0:
            raise ValueError('Factor must be positive and finite')
    except (KeyError, InvalidOperation, ValueError):
        errors.append('INVALID_FACTOR')
    if rule.get('approved') is not True:
        errors.append('UNIT_RULE_NOT_APPROVED')
    # FX needs an independent rate/date policy and cannot be a static scale rule.
    if rule.get('source_currency') != rule.get('target_currency'):
        errors.append('CURRENCY_CONVERSION_NOT_SUPPORTED')
    return errors


def validate_reviewed_inputs(catalogue, mapping):
    errors, checks, seen = [], [], set()
    if catalogue.get('schema_version') != 'reviewed-metric-links-v1' or mapping.get('schema_version') != 'reviewed-metric-links-v1':
        errors.append('UNSUPPORTED_INPUT_SCHEMA')
    definitions = {}
    for criterion in catalogue.get('criteria', []):
        key = (criterion.get('industry'), criterion.get('metric_id'))
        if key in definitions:
            errors.append(f'DUPLICATE_CATALOGUE_ID:{key}')
        definitions[key] = criterion
        for field in ('industry','metric_id','chosen_name','definition','statement','kind','unit_dimension','standard_unit_label','review_decision'):
            if not isinstance(criterion.get(field), str) or not criterion[field].strip():
                errors.append(f'INVALID_CATALOGUE_FIELD:{key}:{field}')
    for row in mapping.get('links', []):
        key = (row.get('industry_scope'), row.get('section'), row.get('code'))
        local_errors, blockers = [], []
        if key in seen:
            local_errors.append('DUPLICATE_SOURCE_IDENTITY')
        seen.add(key)
        if any(not isinstance(v, str) or not v.strip() for v in key):
            local_errors.append('MISSING_SOURCE_IDENTITY')
        target = row.get('target')
        linked = row.get('status') in {'linked', 'linked_with_conditions'}
        if linked != bool(target):
            local_errors.append('STATUS_TARGET_MISMATCH')
        if row.get('status') not in {'linked','linked_with_conditions','not_retained','no_match','ambiguous'}:
            local_errors.append('UNKNOWN_MAPPING_STATUS')
        if target:
            selected = definitions.get((key[0], target.get('metric_id')))
            if selected is None or selected != target:
                local_errors.append('TARGET_NOT_EXACT_CATALOGUE_ENTRY')
            if target.get('industry') != key[0]:
                local_errors.append('CROSS_INDUSTRY_TARGET')
            if target.get('review_decision') not in RETAINED or target.get('kind') != 'reported':
                local_errors.append('TARGET_NOT_RETAINED_REPORTED_METRIC')
        else:
            blockers.append('CATALOGUE_TARGET_NOT_APPROVED')
        # Existing reviewed input is not the future frozen configuration contract.
        for field in ('source_provider', 'source_schema_version', 'mapping_rule_id', 'definition_revision'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                blockers.append('MISSING_' + field.upper())
        if not row.get('source_fields') or any(not isinstance(v,str) or not v.strip() for v in row.get('source_fields', [])):
            blockers.append('SOURCE_FIELD_NOT_IDENTIFIED')
        for field in ('source_unit_verified','source_context_verified','value_conversion_allowed'):
            if type(row.get(field)) is not bool:
                local_errors.append('INVALID_BOOLEAN_' + field.upper())
            if row.get(field) is not True:
                blockers.append(field.upper() + '_NOT_CONFIRMED')
        rule = row.get('unit_rule')
        if not isinstance(rule, dict):
            blockers.append('MISSING_UNIT_RULE')
        else:
            blockers.extend(validate_unit_rule(rule))
        if not row.get('scope_policy') or not row.get('period_basis_policy'):
            blockers.append('MISSING_SCOPE_OR_PERIOD_POLICY')
        # All rules are drafts until packaged in an explicitly frozen, verified release.
        blockers.append('REQUIRES_FROZEN_CONFIGURATION_RELEASE')
        checks.append(dict(industry=key[0], section=key[1], code=key[2],
            source_name=row.get('canonical_name'), target_name=(target or {}).get('chosen_name'),
            catalogue_linked=linked, errors=local_errors, blockers=blockers,
            ready_for_import=False))
        errors.extend(f'{key}:{e}' for e in local_errors)
    return dict(schema_version='financial-config-readiness-v1', database_writes=False,
        input_hashes=dict(catalogue=fingerprint(catalogue), mapping=fingerprint(mapping)),
        catalogue_entries=len(definitions), source_identities=len(checks),
        catalogue_linked=sum(c['catalogue_linked'] for c in checks),
        ready_for_import=0, structure_valid=not errors, errors=errors,
        blocker_counts=dict(Counter(b for c in checks for b in c['blockers'])), checks=checks)
