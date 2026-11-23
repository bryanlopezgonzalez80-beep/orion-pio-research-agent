// Run: node --test jarvis-staging/tests/frontend-secret-guard.test.mjs
// Static defense in depth: not a substitute for Git history scanning or RLS tests.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readdir,readFile} from 'node:fs/promises';
import {join,extname} from 'node:path';
import {fileURLToPath} from 'node:url';

const site=fileURLToPath(new URL('../site/',import.meta.url));
const scannedExtensions=new Set(['.js','.mjs','.html','.css','.json','.webmanifest']);
const secretPatterns=[
  ['Supabase secret key',/sb_secret_[A-Za-z0-9_-]{8,}/g],
  ['Supabase legacy service-role JWT',/eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}/g],
  ['OpenAI project key',/sk-proj-[A-Za-z0-9_-]{12,}/g],
  ['OpenAI legacy key',/sk-[A-Za-z0-9]{32,}/g],
  ['GitHub classic token',/gh[pousr]_[A-Za-z0-9]{30,}/g],
  ['GitHub fine-grained token',/github_pat_[A-Za-z0-9_]{20,}/g],
  ['PEM private key',/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g]
];

async function filesIn(dir){
  const entries=await readdir(dir,{withFileTypes:true});
  const files=[];
  for(const entry of entries){
    if(entry.isSymbolicLink())continue;
    const path=join(dir,entry.name);
    if(entry.isDirectory())files.push(...await filesIn(path));
    else if(entry.isFile()&&scannedExtensions.has(extname(entry.name).toLowerCase()))files.push(path);
  }
  return files;
}

test('deployed frontend contains no recognizable private credentials',async()=>{
  const files=await filesIn(site);
  assert.ok(files.length>0,'No frontend files scanned: check the site directory');
  for(const path of files){
    const source=await readFile(path,'utf8');
    for(const [label,pattern] of secretPatterns){
      pattern.lastIndex=0;
      assert.equal(pattern.test(source),false,`${label} detected in ${path}; never commit private credentials to frontend`);
    }
  }
});

test('frontend uses a publishable Supabase key, never a secret key for createClient',async()=>{
  const app=await readFile(join(site,'app.js'),'utf8');
  assert.match(app,/const PUBLISHABLE_KEY\s*=\s*['"]sb_publishable_/);
  assert.match(app,/createClient\(SUPABASE_URL\s*,\s*PUBLISHABLE_KEY\s*,/);
  assert.doesNotMatch(app,/createClient\(SUPABASE_URL\s*,\s*(?:SERVICE_ROLE|SECRET_KEY|SUPABASE_SECRET)/);
});
