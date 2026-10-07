from pathlib import Path
import json
import re
import pytest

from ohlcv.app.snapshot import embed_chart_snapshot
from ohlcv.storage.store import ProjectPaths

TEMPLATE='<html><script id="initial-data" type="application/json">null</script><script>const example=1;</script></html>'


def test_embed_snapshot_escapes_script_content_and_preserves_bigint(local_tmp):
    paths=ProjectPaths(local_tmp)
    paths.output('web/chart.html').write_text(TEMPLATE,encoding='utf-8')
    payload={'version':1,'count':0,'bars':[], 'provenance':{'note':'</script><img src=x>&\u2028\u2029', 'volume':9223372036854775807}}
    assert embed_chart_snapshot(paths,payload)
    html=paths.output('web/chart.html').read_text(encoding='utf-8')
    raw=re.search(r'<script id="initial-data" type="application/json">(.*?)</script>',html,re.S).group(1)
    assert '<' not in raw and '>' not in raw and '&' not in raw
    assert json.loads(raw)==payload
    assert '<script>const example=1;</script>' in html


def test_missing_viewer_does_not_generate_partial_html(local_tmp):
    paths=ProjectPaths(local_tmp)
    assert embed_chart_snapshot(paths,{'version':1,'count':0,'bars':[]}) is False
    assert not paths.output('web/chart.html').exists()


def test_invalid_template_or_nonfinite_payload_retains_previous_file(local_tmp):
    paths=ProjectPaths(local_tmp)
    chart=paths.output('web/chart.html')
    chart.write_text('<html>old</html>',encoding='utf-8')
    with pytest.raises(ValueError):embed_chart_snapshot(paths,{'version':1,'count':0,'bars':[]})
    assert chart.read_text()=='<html>old</html>'
    chart.write_text(TEMPLATE,encoding='utf-8')
    with pytest.raises(ValueError):embed_chart_snapshot(paths,{'value':float('nan')})
    assert chart.read_text()==TEMPLATE


def test_public_ingest_refreshes_embedded_default(local_tmp):
    from datetime import date,datetime,timezone,timedelta
    from ohlcv.history.public import ingest_response
    paths=ProjectPaths(local_tmp)
    paths.output('web/chart.html').write_text(TEMPLATE,encoding='utf-8')
    now=datetime(2026,10,6,16,tzinfo=timezone(timedelta(hours=7)))
    stamp=int(datetime(2026,10,5,9,tzinfo=now.tzinfo).timestamp())
    report=ingest_response({'t':[stamp],'o':[62],'h':[63],'l':[61],'c':[62.5],'v':[100]},symbol='FPT',exchange='HOSE',start=date(2026,10,5),end=now.date(),fetched_at=now,paths=paths)
    assert report['chart_snapshot'] is True
    raw=re.search(r'<script id="initial-data" type="application/json">(.*?)</script>',paths.output('web/chart.html').read_text(encoding='utf-8'),re.S).group(1)
    data=json.loads(raw)
    assert data['bars'][0]['close']=='62.5'
    assert data['bars'][0]['source']=='dnse_public'
    assert data['provenance']['fetched_at']==now.isoformat()
