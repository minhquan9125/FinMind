"""Keep the standalone chart's initial data synchronized with the local export."""
from __future__ import annotations

import json
import os
import re
import tempfile

from ohlcv.storage.store import ProjectPaths

_INITIAL = re.compile(r'(<script id="initial-data" type="application/json">).*?(</script>)',re.S)


def embed_chart_snapshot(paths: ProjectPaths, payload: dict) -> bool:
    target=paths.output('web/chart.html')
    if not target.is_file():
        return False
    old=target.read_text(encoding='utf-8')
    if len(_INITIAL.findall(old))!=1:
        raise ValueError('Chart must contain exactly one initial-data block')
    serialized=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    # JSON inside a script element must never contain literal closing markup.
    serialized=(serialized.replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
                .replace('\u2028','\\u2028').replace('\u2029','\\u2029'))
    updated=_INITIAL.sub(lambda match:match[1]+'\n'+serialized+'\n'+match[2],old,count=1)
    if updated==old:
        return True
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='\n',dir=target.parent,
                                         prefix='.chart-',suffix='.tmp',delete=False) as stream:
            temporary=stream.name
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        # Recheck path/link confinement before replacing the HTML.
        os.replace(temporary,paths.output('web/chart.html'))
        temporary=None
    finally:
        if temporary is not None:
            os.unlink(temporary)
    return True
