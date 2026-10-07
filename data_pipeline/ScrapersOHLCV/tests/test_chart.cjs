// Pure data-contract tests: no browser or external packages required.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {resolve}=require('node:path');
const vm=require('node:vm');
const html=readFileSync(resolve(__dirname,'../web/chart.html'),'utf8');
const core=html.match(/<script id="data-core">([\s\S]*?)<\/script>/)[1];
const data=vm.runInNewContext(core+'\nChartData;', {TextEncoder});
const candle=(changes={})=>({symbol:'FPT',exchange:'HOSE',trade_date:'2026-10-06',open:'100',high:'105',low:'99',close:'104',volume:1300,source:'dnse',price_basis:'raw',volume_basis:'matched',status:'open',quality:'complete',revision:2,reconciled_at:null,...changes});
const payload=(bars)=>({version:1,count:bars.length,bars});
const normalized=(bar)=>data.normalize(payload([bar]))[0].bars[0];

test('actual pipeline export shape and source text survive',()=>{const bar=normalized(candle());assert.equal(bar.close,'104');assert.equal(bar.volume,'1300');assert.equal(bar.revision,'2');});
test('large integer tokens retain SQLite bigint precision',()=>{const json=JSON.stringify(payload([candle()])).replace('"volume":1300','"volume":9223372036854775807');assert.equal(data.normalize(data.parseJSON(json))[0].bars[0].volume,'9223372036854775807');});
test('quoted number text, escaped quotes and UTF8 BOM parse normally',()=>{const text='\ufeff'+JSON.stringify({...payload([candle()]),note:'volume:9223372036854775807 " \\ tiếng Việt'});assert.equal(data.parseJSON(text).note,'volume:9223372036854775807 " \\ tiếng Việt');});
test('unsafe pre-parsed volume, fractions and overflow rejected',()=>{for(const volume of [9007199254740992,1.5,-1,true,'9223372036854775808'])assert.throws(()=>normalized(candle({volume})),/Volume/);});
test('malformed JSON cannot be repaired by bigint token transformation',()=>{for(const json of ['{"volume":001}','{"volume":1e}','{"volume":NaN}','{"volume":Infinity}','{"volume":+123}','{"volume":9223372036854775807x}'])assert.throws(()=>data.parseJSON(json),/JSON/);});
test('huge input fails before parsing',()=>{assert.throws(()=>data.parseJSON(' '.repeat(data.MAX_FILE+1)),/10 MiB/);});
test('version, count and row limit enforced',()=>{assert.throws(()=>data.normalize({version:true,count:0,bars:[]}),/version/);assert.throws(()=>data.normalize({version:1,count:1,bars:[]}),/count/);assert.throws(()=>data.normalize({version:1,count:20001,bars:Array(20001).fill(candle())}),/20.000/);});
test('invalid trading date and nonstring symbols rejected',()=>{for(const trade_date of ['2026-02-30','2025-02-29','0000-01-01','2026-1-01'])assert.throws(()=>normalized(candle({trade_date})),/Ngày/);assert.equal(data.validDate('2024-02-29'),true);assert.throws(()=>normalized(candle({symbol:['FPT']})),/Mã/);});
test('status and quality must be strings, including prototype keys',()=>{for(const status of [['open'],'constructor','__proto__',null])assert.throws(()=>normalized(candle({status})),/Trạng thái/);for(const quality of [['complete'],'toString'])assert.throws(()=>normalized(candle({quality})),/Trạng thái/);});
test('closed candles require real timezone-bearing reconciliation',()=>{for(const reconciled_at of [null,'2026-10-06T15:00:00','2026-02-30T15:00:00+07:00'])assert.throws(()=>normalized(candle({status:'closed',reconciled_at})),/đối soát/);assert.equal(normalized(candle({status:'closed',reconciled_at:'2026-10-06T15:00:00+07:00'})).status,'closed');});
test('Decimal text coherence checked before floating-point rounding',()=>{assert.throws(()=>normalized(candle({open:'100.0000000000000000002',high:'100.0000000000000000001',close:'100'})),/nhất quán/);const result=normalized(candle({open:'1e-10',high:'2e-10',low:'0.5e-10',close:'1.234567890123456789e-10'}));assert.equal(result.close,'1.234567890123456789e-10');});
test('partial OHLC, numeric prices, nonfinite or zero prices rejected',()=>{for(const changes of [{open:null},{open:100},{open:'NaN'},{open:'Infinity'},{open:'0'},{open:'1e999'}])assert.throws(()=>normalized(candle(changes)));});
test('no-trade retains null OHLC with zero volume only',()=>{const changes={open:null,high:null,low:null,close:null,quality:'no_trade',volume:0};const bar=normalized(candle(changes));assert.equal(bar.close,null);assert.equal(bar.values[3],null);assert.throws(()=>normalized(candle({...changes,volume:1})),/no_trade/);assert.throws(()=>normalized(candle({quality:'no_trade'})),/no_trade/);});
test('sorting and identity isolate different sources, bases, exchanges',()=>{const bars=[candle({trade_date:'2026-10-07'}),candle(),candle({source:'other'}),candle({price_basis:'adjusted'}),candle({volume_basis:'total'}),candle({exchange:'HNX'})];const groups=data.normalize(payload(bars));assert.equal(groups.length,5);const main=groups.find(group=>group.key==='FPT|HOSE|dnse|raw|matched');assert.equal(main.bars[0].trade_date,'2026-10-06');assert.equal(main.bars[1].trade_date,'2026-10-07');});
test('duplicate daily row rejected rather than double-counted',()=>{assert.throws(()=>data.normalize(payload([candle(),candle({revision:3})])),/Trùng ngày/);});
test('date and finality filters preserve provisional distinction',()=>{const bars=data.normalize(payload([candle(),candle({trade_date:'2026-10-07',status:'closed',reconciled_at:'2026-10-07T15:00:00+07:00'})]))[0].bars;assert.equal(data.filter(bars,'2026-10-07','',false).length,1);assert.equal(data.filter(bars,'','',true).length,1);assert.throws(()=>data.filter(bars,'2026-10-08','2026-10-06',false),/Từ ngày/);assert.equal(data.normalize(payload([])).length,0);});
