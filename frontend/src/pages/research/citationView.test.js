import test from 'node:test';
import assert from 'node:assert/strict';
import { citationView, modeLabel, safeSourceUrl } from './citationView.js';

test('analysis bundle displays the cited database article without losing its URL or locator', () => {
  const news = { evidence_id: 'db-news', source_id: 'document-1', source_type: 'NEWS',
    source_verified: true, title: 'Tin đã nạp', passage: 'Nội dung có nguồn',
    source_url: 'https://example.org/article', locator: { row_keys: ['line-3'] } };
  const price = { evidence_id: 'feed-price', source_type: 'PRICE', source_verified: true };
  const result = { execution_mode: 'LIVE', scope: { source_type: 'MARKET_ANALYSIS' },
    presentation: { sources: 'USED_LINKS' }, evidence_pack: { schema_version: '1.3', items: [price, news],
      evidence_packs: [{ items: [price] }, { items: [news] }] },
    answering: { status: 'DRAFT_READY', citations: [{ evidence_id: news.evidence_id, citation_number: 1 }] } };
  const sources = citationView(result);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].url, news.source_url);
  assert.equal(sources[0].passage, news.passage);
  assert.equal(sources[0].citationNumber, 1);
});

test('session summary keeps numbered sources from independent evidence packs', () => {
  const make = (id, type) => ({ evidence_id: id, source_type: type, source_verified: true,
    passage: 'Đoạn nguồn '+id, title: 'Nguồn '+id, locator: { section: 'Kỳ '+id } });
  const first = make('fpt-2025', 'BCTC');
  const second = make('vcb-2024', 'NEWS');
  const result = { execution_mode: 'LIVE', scope: { source_type: 'PRICE' },
    presentation: { sources: 'USED_LINKS' }, evidence_packs: [{ items: [first] }, { items: [second, make('unused','NEWS')] }],
    answering: { status: 'DRAFT_READY', citations: [{ evidence_id: first.evidence_id, citation_number: 1 },
      { evidence_id: second.evidence_id, citation_number: 2 }] } };
  const sources = citationView(result);
  assert.equal(sources.length, 2);
  assert.deepEqual(sources.map(s => s.citationNumber), [1,2]);
  assert.equal(sources[0].passage, first.passage);
});

test('a saved price observation cited by a session summary has a source card', () => {
  const item = { evidence_id: 'saved-price', source_type: 'PRICE', source_verified: true,
    title: 'Giá đã quan sát', passage: 'Giá tại ngày đã hỏi', locator: { section: 'vnstock/KBS' } };
  const result = { execution_mode: 'LIVE', evidence_packs: [{ items: [item] }],
    presentation: { sources: 'USED_LINKS' }, answering: { status: 'DRAFT_READY',
      citations: [{ evidence_id: item.evidence_id, citation_number: 1 }] } };
  assert.equal(citationView(result)[0]?.citationNumber, 1);
});

test('graph evidence opens a verified document URL without rewriting its locator', () => {
  const locator = { source_table: 'annual_reports', section: 'Hội đồng quản trị' };
  const item = { evidence_id: 'graph-chunk', source_type: 'BCTN', source_verified: true,
    source_url: 'https://example.org/annual.pdf', locator };
  const result = { execution_mode: 'LIVE', evidence_pack: { items: [item] } };
  assert.equal(citationView(result)[0].url, item.source_url);
  assert.equal(locator.url, undefined);
});

test('prices never show citation cards or source links', () => {
  assert.deepEqual(citationView({ execution_mode: 'LIVE', scope: { source_type: 'PRICE' },
    evidence_pack: { items: [{ evidence_id: 'price', source_type: 'PRICE', source_verified: true }] } }), []);
});

test('summaries show compact links only for articles used in the answer', () => {
  const item = { evidence_id: 'e1', source_type: 'NEWS', source_verified: true, title: 'Bài đã dùng',
    locator: { url: 'https://fireant.vn/bai-viet/tin/123' } };
  const result = { execution_mode: 'LIVE', presentation: { sources: 'USED_LINKS' },
    answering: { status: 'DRAFT_READY', citations: [{ evidence_id: 'e1', citation_number: 1 }] },
    evidence_pack: { items: [item, { ...item, evidence_id: 'unused' }] } };
  const sources = citationView(result);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].compact, true);
  assert.equal(sources[0].url, item.locator.url);
});

test('shows only verified live sources and distinguishes candidates from bound citations', () => {
  const item = { evidence_id: 'e1', passage: 'Nguồn thật', source_verified: true,
    title: 'Báo cáo FPT', locator: { source_table: 'financial_reports', section: 'Bảng cân đối', row_keys: ['r1'] } };
  assert.equal(citationView({ execution_mode: 'FIXTURE', evidence_pack: { items: [item] } }).length, 0);
  const result = { execution_mode: 'LIVE', evidence_pack: { items: [item, { ...item, evidence_id: 'e2', source_verified: false }] } };
  assert.equal(citationView(result).length, 1);
  assert.equal(citationView(result)[0].used, false);
  result.answering = { status: 'DRAFT_READY', citations: [{ evidence_id: 'e1' }] };
  assert.equal(citationView(result)[0].used, true);
  assert.equal(citationView(result)[0].location, 'Bảng cân đối');
});

test('source links reject executable schemes and credentials', () => {
  assert.equal(safeSourceUrl('javascript:alert(1)'), null);
  assert.equal(safeSourceUrl('data:text/html,hello'), null);
  assert.equal(safeSourceUrl('https://user:pass@example.com'), null);
  assert.equal(safeSourceUrl('https://cafef.vn/news.htm'), 'https://cafef.vn/news.htm');
});

test('mode label does not label live data as fixtures', () => {
  assert.match(modeLabel({ execution_mode: 'LIVE' }), /Nguồn dữ liệu thật/);
  assert.match(modeLabel({ execution_mode: 'FIXTURE' }), /Dữ liệu mẫu/);
});

test('citation numbers follow answer order instead of retrieval order', () => {
  const items = ['a', 'b', 'c'].map(id => ({ evidence_id: id, source_verified: true }));
  const view = citationView({ execution_mode: 'LIVE', evidence_pack: { items },
    answering: { status: 'DRAFT_READY', citations: [
      { evidence_id: 'b', citation_number: 1 }, { evidence_id: 'a', citation_number: 2 },
    ] } });
  assert.equal(view[0].citationNumber, 2);
  assert.equal(view[1].citationNumber, 1);
  assert.equal(view[2].citationNumber, null);
});

test('health sources expose stored PDF citations and reject unsafe links', () => {
  const item = { evidence_id: 'health', source_verified: true, snapshot: { kind: 'FINANCIAL_HEALTH', health: {
    citations: [{title:'Report',url:'https://example.org/report.pdf',page:33},
      {title:'Report',url:'https://example.org/report.pdf',page:33}, {url:'javascript:alert(1)'}]
  } } };
  const source = citationView({execution_mode:'LIVE',evidence_pack:{items:[item]}})[0];
  assert.equal(source.documentLinks.length, 1);
  assert.equal(source.documentLinks[0].page, 33);
  assert.match(source.sourceNote, /BCTC/);
});

test('stored locator source_url is retained without inventing a link for computed trends', () => {
  const items = [{evidence_id:'news',source_verified:true,locator:{source_url:'https://example.org/news'}},
    {evidence_id:'trend',source_verified:true,source_type:'PRICE_TREND'}];
  const sources = citationView({execution_mode:'LIVE',evidence_pack:{items}});
  assert.equal(sources[0].url, 'https://example.org/news');
  assert.equal(sources[1].url, null);
  assert.match(sources[1].sourceNote, /FinMind/);
});
