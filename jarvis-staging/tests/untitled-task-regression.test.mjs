import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, trustedCommand} from '../site/briefing.js';

const now=new Date('2026-11-22T16:00:00Z');
const base={loaded:true,verifiedAt:now.getTime()-1000,now};

test('literal Sin título is a valid saved task, not an empty placeholder',()=>{
  const result=dailyBriefing({...base,tasks:[{title:'Sin título',status:'pending'}]});
  assert.match(result,/1 pendientes/);
  assert.match(result,/1\. Sin título/);
});

test('invisible-only titles are not counted as saved commitments',()=>{
  // Actual Unicode code points, not literal backslash-u escape sequences.
  const invisible=String.fromCharCode(0x200b,0xfeff);
  const result=dailyBriefing({...base,tasks:[{title:invisible,status:'pending'}]});
  assert.match(result,/0 pendientes/);
});

test('stale task verification must not be reported as current',()=>{
  const result=dailyBriefing({...base,verifiedAt:now.getTime()-16*60*1000,tasks:[{title:'Sin título',status:'pending'}]});
  assert.match(result,/No puedo verificar tus tareas/);
  assert.doesNotMatch(result,/1 pendientes/);
});

test('departure queries must refuse to invent traffic or departure minutes in both languages',()=>{
  for(const phrase of ['A qué hora debo salir','When should I leave']){
    const response=trustedCommand(phrase,base);
    assert.ok(response,phrase);
    assert.match(response.text,/No puedo calcular|I cannot calculate/);
    assert.doesNotMatch(response.text,/\b(?:15|20|30|45) minutos\b|\b(?:15|20|30|45) minutes\b/);
  }
});
