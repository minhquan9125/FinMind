const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');

test('complete inline chart scripts compile, including UI event handlers',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../web/chart.html'),'utf8');
  let count=0;
  for(const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)){
    if(/type\s*=\s*["']application\/json["']/i.test(match[1]))continue;
    new vm.Script(match[2],{filename:`chart-inline-${++count}.js`});
  }
  assert(count>=2);
});
