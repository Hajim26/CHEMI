const assert=require('assert');const fs=require('fs');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const start=script.indexOf('      function teammateMatchElement(contest) {');
const end=script.indexOf('      function renderContests() {',start);
assert(start>=0&&end>start);
const snippet=script.slice(start,end);
class El {
  constructor(tag='div'){this.tag=tag;this.children=[];this.events={};this.textContent='';this.disabled=false;this.title='';this.attributes={};this.className='';}
  append(...v){this.children.push(...v)}
  prepend(...v){this.children.unshift(...v)}
  setAttribute(k,v){this.attributes[k]=v}
  addEventListener(k,v){this.events[k]=v}
  click(){return this.events.click?.()}
}
const document={createElement:tag=>new El(tag)};
const contest={id:'p',title:'공공데이터 활용 경진대회',category:'AI·개발'};
const key=()=>contest.id;
const real={id:'123e4567-e89b-12d3-a456-426614174001',nickname:'회원 B',is_synthetic:false,major:'데이터학과',skills:[{name:'SQL'},{name:'Python 데이터 분석'},{name:'시각화'}]};
const fake={...real,id:'TM010',is_synthetic:true};
let active=real;let sent=0;let demoSent=0;
const teammateCache=new Map([[contest.id,{member:active,score:68,reason:'부족 역할 보완',source:'rules'}]]);
const sentRequestStatus=new Map();const invitedMatches=new Set();
function sendMemberInvitation(member,contest,btn){sent++;btn.disabled=true;return Promise.resolve(true)}
let renderCalls=0;
const renderContests=()=>renderCalls++;
const helper=Function('document','teammateCache','contestMatchKey','trim','sentRequestStatus','invitationKey',
  'requestButtonLabel','openMemberProfile','isRealInviteAllowed','sendMemberInvitation','renderContests','demoInvitationExists','sendDemoInvitation',snippet+';return teammateMatchElement');
const render=helper(document,teammateCache,key,v=>String(v??'').trim(),sentRequestStatus,()=>real.id+'|'+contest.id,
  ()=> '응답 대기 중',()=>{},m=>!m.is_synthetic,sendMemberInvitation,renderContests,()=>demoSent>0,()=>{demoSent++;return true;});
(async()=>{
  let strip=render(contest);let actions=strip.children[2];
  assert.strictEqual(actions.className,'match-action-row');
  assert.strictEqual(actions.children.length,2);
  assert(actions.children[0].textContent.includes('상세 보기'));
  assert.strictEqual(actions.children[1].textContent,'매칭 요청');
  assert.strictEqual(actions.children[1].disabled,false);
  await actions.children[1].click();
  assert.strictEqual(sent,1);
  teammateCache.set(contest.id,{member:fake,score:66,reason:'예시',source:'rules'});
  strip=render(contest);actions=strip.children[2];
  assert.strictEqual(actions.children.length,2);
  assert.strictEqual(actions.children[1].textContent,'매칭 요청 (시연)');
  assert.strictEqual(actions.children[1].disabled,false);
  assert(actions.children[1].title.includes('가상'));
  await actions.children[1].click();
  assert.strictEqual(sent,1,'synthetic profile must never submit a real request');
  assert.strictEqual(demoSent,1,'synthetic profile triggers only local demo record');
  strip=render(contest);actions=strip.children[2];
  assert(actions.children[1].disabled,'duplicate demo request must be disabled');
  const chips=strip.children[0].children[1].children[1].children;
  assert.deepStrictEqual(chips.map(c=>c.textContent),['SQL','Python 데이터 분석','+1']);
  console.log('Step 22 real request and enabled mock synthetic button adjacent to details: PASSED');
})().catch(e=>{console.error(e);process.exit(1)});
