"""Admin-set local cost estimates. Never a provider invoice or a spending lock."""
from datetime import datetime,timezone
from decimal import Decimal
import json
import uuid
from .research_metrics import ResearchMetrics,VN,utc_now

DEFAULT={'mode':'unconfigured','period':'month','limit_usd':'10','warn_at':80,'rates':[]}


class ApiBudget:
    def __init__(self,root):
        self.metrics=ResearchMetrics(root)
        with self.metrics.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS budget_versions(
                id TEXT PRIMARY KEY,created_at TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,config TEXT NOT NULL)''')

    def configuration(self):
        with self.metrics.connect() as conn:
            rows=conn.execute('SELECT * FROM budget_versions ORDER BY rowid DESC LIMIT 50').fetchall()
        history=[{**dict(r),'config':json.loads(r['config'])} for r in rows]
        return {'config':history[0]['config'] if history else DEFAULT,'version':history[0]['id'] if history else None,'history':history}

    def save(self,config,actor,reason,expected_version):
        with self.metrics.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            current=conn.execute('SELECT id FROM budget_versions ORDER BY rowid DESC LIMIT 1').fetchone()
            if (current[0] if current else None)!=expected_version:raise ValueError('BUDGET_CONFIG_CHANGED')
            ident=str(uuid.uuid4())
            conn.execute('INSERT INTO budget_versions VALUES(?,?,?,?,?)',(ident,utc_now(),actor,reason,json.dumps(config)))
        return ident

    def snapshot(self,at=None):
        data=self.configuration();cfg=data['config']
        local=(at or datetime.now(timezone.utc)).astimezone(VN)
        start=local.replace(hour=0,minute=0,second=0,microsecond=0)
        if cfg['period']=='month':start=start.replace(day=1)
        if cfg['period']=='month':
            end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
        else:
            from datetime import timedelta
            end=start+timedelta(days=1)
        rates={r['model']:r for r in cfg['rates']};used=Decimal(0);unknown=unpriced=0;models={}
        with self.metrics.connect() as conn:
            rows=conn.execute('SELECT calls FROM requests WHERE created_at>=? AND created_at<?',
                (start.astimezone(timezone.utc).isoformat(),end.astimezone(timezone.utc).isoformat())).fetchall()
        for row in rows:
            for call in json.loads(row[0]):
                usage=call.get('usage');rate=rates.get(call['model'])
                if usage is None:unknown+=1;continue
                if cfg['mode']=='free':cost=Decimal(0)
                elif cfg['mode']=='paid' and rate:
                    # Non-prompt total includes visible output and reasoning.
                    cost=(Decimal(usage['input_tokens'])*Decimal(rate['input_per_million'])+
                          Decimal(usage['total_tokens']-usage['input_tokens'])*Decimal(rate['output_per_million']))/Decimal(1000000)
                else:unpriced+=1;continue
                used+=cost;models[call['model']]=models.get(call['model'],Decimal(0))+cost
        limit=Decimal(cfg['limit_usd']);pct=used/limit*100
        configured=cfg['mode']!='unconfigured'
        try:
            from ..b1_answering.core.policy import Limits
            limits=Limits.load()
            runtime={k:getattr(limits,k) for k in ('version','model','max_input_tokens','max_output_tokens','max_total_tokens','max_generation_calls','read_timeout_seconds')}
        except Exception:runtime={}
        return {**data,'runtime_limits':runtime,'usage':{'configured':configured,'currency':'USD','period':cfg['period'],
            'starts_at':start.isoformat(),'ends_at':end.isoformat(),'used_usd':str(used),
            'limit_usd':str(limit),'percent':float(pct),'warn_at':cfg['warn_at'],
            'warning':configured and pct>=cfg['warn_at'],'exceeded':configured and used>=limit,
            'unknown_calls':unknown,'unpriced_calls':unpriced,'complete':configured and not(unknown or unpriced),
            'by_model':[{'model':k,'estimated_usd':str(v)} for k,v in sorted(models.items())],
            'enforcement':'WARN_ONLY','scope':'LOCAL_LIVE_WEB_CHAT'}}
