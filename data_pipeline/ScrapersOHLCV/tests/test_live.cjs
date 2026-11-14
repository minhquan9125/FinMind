const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../web/chart.html'),'utf8');
const core=html.match(/<script id="live-core">([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({AbortController,Date,setTimeout,clearTimeout});
vm.runInContext(core+'\nglobalThis.Controller=LiveController;',context);
const Controller=context.Controller;
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve();};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function setup(overrides={}){
  let seq=0,visible=true,calls=[];const timers=new Map(),applied=[],events=[];
  const controller=new Controller({
    setTimeout:(fn,delay)=>{timers.set(++seq,{fn,delay});return seq;},clearTimeout:id=>timers.delete(id),
    isVisible:()=>visible,getStatus:async s=>({session:{active:true}}),
    getQuote:async s=>{calls.push(s);return {session:{active:true},quote:{},data:{}};},
    applyQuote:(q,s)=>applied.push(s),onStatus:info=>events.push(info),...overrides});
  return {controller,timers,applied,events,calls,hide(){visible=false;controller.visibilityChanged();},
    show(){visible=true;controller.visibilityChanged();},async tick(){const [id,timer]=timers.entries().next().value;timers.delete(id);await timer.fn();await flush();}};
}

test('outside session never calls provider; opening starts automatically and lunch stops',async()=>{
  let active=false;const s=setup({getStatus:async()=>({session:{active,phase:active?'continuous':'lunch'}})});
  s.controller.select('FPT');await flush();assert.equal(s.calls.length,0);
  assert.equal([...s.timers.values()][0].delay,30000);
  active=true;await s.tick();assert.deepEqual(s.applied,['FPT']);
  assert.equal([...s.timers.values()][0].delay,5000);
  active=false;await s.tick();assert.equal(s.calls.length,1);s.controller.stop();
});
test('switch stops old symbol, rejects late quote and return fetches current price',async()=>{
  const old=deferred();const s=setup({getQuote:async symbol=>symbol==='FPT'?old.promise:{session:{active:true},quote:{},data:{}}});
  s.controller.select('FPT');await flush();s.controller.select('VCB');await flush();
  old.resolve({session:{active:true},quote:{},data:{}});await flush();assert.deepEqual(s.applied,['VCB']);
  s.controller.select('FPT');await flush();assert.deepEqual(s.applied,['VCB','FPT']);s.controller.stop();
});
test('hidden tab aborts late response; resume checks immediately; stop cancels timer',async()=>{
  const late=deferred();let count=0;const s=setup({getQuote:async()=>++count===1?late.promise:{session:{active:true},quote:{},data:{}}});
  s.controller.select('FPT');await flush();s.hide();late.resolve({session:{active:true},quote:{},data:{}});await flush();
  assert.equal(s.applied.length,0);assert.equal(s.timers.size,0);
  s.show();await flush();assert.equal(s.applied.length,1);s.controller.stop();assert.equal(s.timers.size,0);
});
test('missing session and session ending during quote fail closed',async()=>{
  for(const session of [undefined,{active:false}]){
    const s=setup({getQuote:async()=>({session,quote:{},data:{}})});
    s.controller.select('FPT');await flush();assert.equal(s.applied.length,0);s.controller.stop();
  }
  const s=setup({getStatus:async()=>({})});s.controller.select('FPT');await flush();assert.equal(s.calls.length,0);s.controller.stop();
});
test('budget waiting does not fetch; empty or stale quote never replaces data',async()=>{
  const s=setup({getStatus:async()=>({session:{active:true},wait_seconds:40})});
  s.controller.select('FPT');await flush();assert.equal(s.calls.length,0);assert.equal([...s.timers.values()][0].delay,40000);s.controller.stop();
  const empty=setup({getQuote:async()=>({session:{active:true},quote:null,wait_seconds:10})});
  empty.controller.select('FPT');await flush();assert.equal(empty.applied.length,0);assert.equal([...empty.timers.values()][0].delay,10000);empty.controller.stop();
});
test('errors back off 15/30/60 seconds; success resets; no overlapping timer calls',async()=>{
  let fail=true;const s=setup({getStatus:async()=>{if(fail)throw Error('network');return {session:{active:true}};}});
  s.controller.select('FPT');await flush();assert.equal([...s.timers.values()][0].delay,15000);
  await s.tick();assert.equal([...s.timers.values()][0].delay,30000);
  await s.tick();assert.equal([...s.timers.values()][0].delay,60000);
  fail=false;await s.tick();assert.equal([...s.timers.values()][0].delay,5000);assert.equal(s.controller.consecutiveErrors,0);
  assert.equal(s.timers.size,1);s.controller.stop();
});
