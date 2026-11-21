// Run: node --test jarvis-staging/tests/frontend-secret-boundary.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readdir,readFile} from 'node:fs/promises';
import {join} from 'node:path';
const root=new URL('../site/',import.meta.url);
async function frontendFiles(dir){
  const files=[];
  for(const item of await readdir(dir,{withFileTypes:true})){
    const path=join(dir,item.name);
    if(item.isDirectory())files.push(...await frontendFiles(path));
    else if(/\.(?:js|mjs|html|json|css)$/i.test(item.name))files.push(path);
  }
  return files;
}
test('frontend contains no Supabase secret/service-role or private OpenAI key literals',async()=>{
  const files=await frontendFiles(root);
  assert.ok(files.length>0,'expected frontend assets');
  for(const file of files){
    const source=await readFile(file,'utf8');
    assert.doesNotMatch(source,/sb_secret_[A-Za-z0-9_-]+/,'Supabase secret exposed in '+file);
    assert.doesNotMatch(source,/sk-(?:proj-)?[A-Za-z0-9_-]{16,}/,'private model key exposed in '+file);
    assert.doesNotMatch(source,/SUPABASE_SERVICE_ROLE_KEY\s*[:=]\s*['"`][^'"`]+/,'service-role credential exposed in '+file);
  }
});
test('frontend must not opt into paid model requests',async()=>{
  for(const file of await frontendFiles(root)){
    const source=await readFile(file,'utf8');
    assert.doesNotMatch(source,/ENABLE_MODEL_REQUESTS\s*[:=]\s*(?:true|['"]true['"]|1)\b/i,'paid model flag enabled in '+file);
  }
});

// Parse JWT claims rather than relying on base64 prefixes or JSON property order.
function containsServiceRoleJwt(source){
  for(const match of source.matchAll(/\b[A-Za-z0-9_-]{8,}\.([A-Za-z0-9_-]{8,})\.[A-Za-z0-9_-]{8,}\b/g)){
    try{
      const claims=JSON.parse(Buffer.from(match[1],'base64url').toString('utf8'));
      if(claims&&claims.role==='service_role')return true;
    }catch{
      // Non-JWT dotted strings are not credentials.
    }
  }
  return false;
}
test('JWT scanner detects privileged claims regardless of claim ordering',()=>{
  const jwt=(claims)=>['eyJhbGciOiJIUzI1NiJ9',Buffer.from(JSON.stringify(claims)).toString('base64url'),'abcdefgh123'].join('.');
  assert.equal(containsServiceRoleJwt(jwt({role:'service_role'})),true);
  assert.equal(containsServiceRoleJwt(jwt({aud:'authenticated',role:'service_role'})),true);
  assert.equal(containsServiceRoleJwt(jwt({role:'anon'})),false);
  assert.equal(containsServiceRoleJwt('not-a-jwt'),false);
});
test('frontend contains no embedded service-role JWT payloads',async()=>{
  for(const file of await frontendFiles(root)){
    const source=await readFile(file,'utf8');
    assert.equal(containsServiceRoleJwt(source),false,'service-role JWT exposed in '+file);
  }
});
