"""Version fingerprint of the normalized source section, not an archived source copy."""
import hashlib
import json


def section_fingerprint(doc, section_index):
    section = doc.sections[section_index]
    payload = {'source_table': doc.source_table, 'source_id': str(doc.source_id),
               'label': section.label, 'header': section.header,
               'rows': [[row.key, row.text] for row in section.rows]}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()
