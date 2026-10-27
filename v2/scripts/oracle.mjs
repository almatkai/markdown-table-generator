// Execute the byte-exact pinned upstream command with mocked @raycast/api.
// No copied table implementation: Node strips types and vm links the real source.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
const root = fileURLToPath(new URL('../', import.meta.url));
const source = readFileSync(new URL('../tests/fixtures/upstream/generate-markdown-table.tsx', import.meta.url), 'utf8');
let events = [];
let probe = false;
let clipboardFailure = false;
const stop = Symbol('stop before upstream unbounded generation');
const api = new vm.SyntheticModule(['Clipboard', 'Toast', 'showToast', 'LaunchProps'], function () {
  this.setExport('LaunchProps', undefined);
  this.setExport('Clipboard', { async copy(text) { events.push({ copy: text }); if (clipboardFailure) throw new Error('mock clipboard failure'); } });
  this.setExport('Toast', { Style: { Success: 'success', Failure: 'failure' } });
  this.setExport('showToast', (style, message) => {
    events.push({ style, message });
    if (probe) throw stop; // Original toast precedes table generation.
  });
});
const module = new vm.SourceTextModule(stripTypeScriptTypes(source));
await module.link(specifier => {
  assert.equal(specifier, '@raycast/api');
  return api;
});
await module.evaluate();
// Confirm the original failure ordering that V2 deliberately corrects.
clipboardFailure = true;
await assert.rejects(module.namespace.default({arguments:{rows:'1',columns:'1'}}), /mock clipboard failure/);
assert.equal(events[0].style,'success');
assert.equal(typeof events[1].copy,'string');
clipboardFailure = false;
const cases = [];
const add = (rows, columns, boundedProbe = false) => cases.push({ rows, columns, boundedProbe });
for (let r = 1; r <= 12; r++) for (let c = 1; c <= 13; c++) add(String(r), String(c));
for (const value of ['',' ','0','-0','-1','+0','abc','NaN','Infinity','-Infinity','0x10','+0X10','0b11','0o10',
  '.5','-.5','+ 1','--1','++1','١','１','1_000','1,000','+0012','001','1.9','2.99junk','3e9','4E-7',
  '5 apples','6\u0000stuff','7\n8','9-10','10.0','+11','12\u2028junk',' 13 ', '\u00851','\u180e1','\u200b1','\u20601',
  '\uffff1','\u00001']) {
  add(value, '2'); add('3', value);
}
for (const cp of [9,10,11,12,13,32,160,5760,...Array.from({length:11},(_,i)=>8192+i),8232,8233,8239,8287,12288,65279]) {
  add(String.fromCodePoint(cp)+'+2junk','3'); add('2',String.fromCodePoint(cp)+'3.5');
}
for (const value of ['9007199254740991','9007199254740992','9007199254740993','18446744073709551615',
  '18446744073709551616','1'+'0'.repeat(308),'9'.repeat(308),'9'.repeat(309),
  '17976931348623157'+'0'.repeat(292), '17976931348623158'+'0'.repeat(292),
  '17976931348623159'+'0'.repeat(292), '0'.repeat(1500)+'2', '0'.repeat(1500),
  '1'+'0'.repeat(10000), '-'+ '9'.repeat(1000)]) {
  // Only probe the original validation: throwing in its toast prevents huge loops.
  add(value,'1',true); add('1',value,true); add(value,'bad',true);
}
// Independent boundary fixtures, including exact 8 MiB. Rejecting cases probe
// upstream validation only, since the V2 bound intentionally changes behavior.
add('4124','136'); add('4125','136',true);
add('472205','1'); add('472206','1',true);
add('1','226600'); add('1','226601',true);
const results = [];
for (const item of cases) {
  events = []; probe = item.boundedProbe;
  try { await module.namespace.default({ arguments: { rows:item.rows, columns:item.columns } }); }
  catch (e) { if (e !== stop) throw e; }
  const toast = events.find(e => e.style);
  assert.ok(toast);
  if (toast.style === 'failure') {
    assert.equal(events.length,1); results.push({error:toast.message});
  } else if (probe) {
    // Zero-prefixed 2 fits even though this case uses the safe validation probe.
    if (item.rows.replace(/^0+/, '') === '2' || item.columns.replace(/^0+/, '') === '2') {
      events = []; probe = false;
      await module.namespace.default({ arguments: {rows:item.rows,columns:item.columns} });
      results.push({table:events[1].copy});
    } else results.push({error:'Markdown table exceeds the 8 MiB output limit.'});
  } else {
    assert.equal(events.length,2);
    assert.equal(events[0].style,'success');
    assert.equal(events[0].message,'Markdown table copied to clipboard!');
    assert.equal(typeof events[1].copy,'string');
    assert.ok(events[1].copy.endsWith('\n'));
    results.push({table:events[1].copy});
  }
}
const run = spawnSync('cargo',['run','--quiet','--locked','--example','oracle_bridge'], {
  cwd:root, input:cases.map(x=>JSON.stringify(x)).join('\n')+'\n', encoding:'utf8', maxBuffer:128*1024*1024,
});
assert.equal(run.status,0,run.stderr);
const native = run.stdout.trim().split('\n').map(x=>JSON.parse(x));
assert.equal(native.length,results.length);
for (let i=0;i<cases.length;i++) assert.deepEqual(native[i],results[i],`Oracle case ${i}: ${JSON.stringify(cases[i]).slice(0,180)}`);
console.log(`${cases.length} executed upstream/native oracle cases passed (large dimensions validation-only; no unbounded loops).`);
