const fs = require('fs');
const assert = require('assert');
const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const start=script.indexOf('      // Step 16: show received/sent requests separately.');
const end=script.indexOf("      $('saveMatchSettings').addEventListener",start);
assert(start>0&&end>start,'Step 16 request script should be present');
const snippet=script.slice(start,end);
class El {
 constructor(tag='div') {
  this.tag=tag;this.children=[];this.events={};this.textContent='';this.hidden=false;this.disabled=false;
  this.attributes={};this.classes=new Set();this.className='';
  this.classList={add:(name)=>this.classes.add(name),remove:(name)=>this.classes.delete(name)};
 }
 append(...objects){this.children.push(...objects);}
 replaceChildren(...children){this.children=[...children];}
 setAttribute(name,value){this.attributes[name]=String(value);}
 addEventListener(name,handler){this.events[name]=handler;}
 querySelectorAll(selector){return selector==='button'?this.children.filter(el=>el.tag==='button'):[];}
 click(){return this.events.click?.();}
}
const els=new Map();
const $=(id)=>{if(!els.has(id))els.set(id,new El());return els.get(id)};
const document={createElement:(tag)=>new El(tag)};
const invitedMatches=new Set(),sentRequestStatus=new Map();
let renderContestsCount=0;
const renderContests=()=>renderContestsCount++;
let rows=[
 {id:1,direction:'received',other_nickname:'디자이너A',contest_title:'공모전A',contest_id:'a',sender_id:'send',recipient_id:'me',status:'pending',message:'참여해주세요',created_at:'2026-11-06T00:00:00Z'},
 {id:2,direction:'sent',other_nickname:'기획자B',contest_title:'공모전B',contest_id:'b',sender_id:'me',recipient_id:'recipient-b',status:'pending',message:'',created_at:'2026-11-06T01:00:00Z'},
 {id:3,direction:'sent',other_nickname:'개발자C',contest_title:'공모전C',contest_id:'c',sender_id:'me',recipient_id:'recipient-c',status:'declined',message:'',created_at:'2026-11-06T02:00:00Z'},
];
const calls=[];
async function apiCall(path,method,payload){
 calls.push({path,method,payload});
 if(path==='/api/me/requests')return {requests:rows};
 if(path==='/api/team/respond'){
  const item=rows.find(x=>x.id===payload.request_id);item.status=payload.action;return {ok:true};
 }
 throw Error('Unexpected API: '+path);
}
const demoRows=[];let demoSaves=0;
const controller=new Function('document','$','apiCall','renderContests','cloudMode','signedIn','previewMode','invitedMatches','sentRequestStatus','confirm','demoSentRequests','saveDemoSentRequests',
  "let requestTab='received',lastRequestRows=[],requestLoading=false;const requestStatusLabels={pending:'응답 대기',accepted:'수락 · 연결됨',declined:'거절됨',cancelled:'취소됨'};"+
  snippet+";return {renderMatchRequests,loadMatchRequests,getTab:()=>requestTab,getDemoRows:()=>demoSentRequests};");
const view=controller(document,$,apiCall,renderContests,true,true,false,invitedMatches,sentRequestStatus,()=>true,demoRows,()=>demoSaves++);
(async()=>{
 await view.loadMatchRequests();
 assert.strictEqual($('requestPendingReceived').textContent,'1');
 assert.strictEqual($('requestPendingSent').textContent,'1');
 assert.strictEqual($('requestAcceptedTotal').textContent,'0');
 assert.strictEqual($('receivedRequestsCount').textContent,'(1)');
 assert.strictEqual($('sentRequestsCount').textContent,'(2)');
 assert.strictEqual($('matchRequestList').children.length,1);
 assert.strictEqual($('matchRequestList').children[0].children[4].children.length,2,'recipient can accept or decline');
 assert.strictEqual(sentRequestStatus.get('recipient-c|c'),'declined');
 // Accept the received request; should persist and update all status indicators.
 const receivedItem=$('matchRequestList').children[0];
 const accept=receivedItem.children[4].children[0];
 await accept.click();
 assert.strictEqual(rows[0].status,'accepted');
 assert.strictEqual($('requestAcceptedTotal').textContent,'1');
 assert.strictEqual($('matchRequestList').children[0].children.some(x=>x.className==='match-accepted-note'),true);
 // Switch to sent tab, cancel the pending request. Declined request stays displayed.
 await $('sentRequestsTab').click();
 assert.strictEqual(view.getTab(),'sent');
 assert.strictEqual($('matchRequestList').children.length,2);
 const toCancel=$('matchRequestList').children[0];
 const action=toCancel.children.find(x=>x.className==='match-request-actions');
 assert(action, 'sender should have a cancellation button');
 await action.children[0].click();
 assert.strictEqual(rows[1].status,'cancelled');
 assert.strictEqual($('requestPendingSent').textContent,'0');
 assert.strictEqual(sentRequestStatus.get('recipient-b|b'),'cancelled');
 assert(calls.some(c=>c.path==='/api/team/respond'&&c.payload.action==='accepted'));
 assert(calls.some(c=>c.path==='/api/team/respond'&&c.payload.action==='cancelled'));
 assert(renderContestsCount>=3);
 // A local-only demonstration request appears in the same sent tab, distinctly labeled.
 demoRows.push({id:'demo-record',is_demo:true,direction:'sent',status:'demo',recipient_id:'TM001',contest_id:'fake',other_nickname:'가상 인물',contest_title:'시연 공모전',created_at:'2026-11-06T00:00:00Z'});
 view.renderMatchRequests();
 assert.strictEqual($('sentRequestsCount').textContent,'(3)');
 const mock=$('matchRequestList').children[0];
 assert(mock.className.includes('is-demo'));
 assert(mock.children[0].children[1].textContent.includes('시연용'));
 assert(mock.children.some(n=>n.className==='match-demo-help'));
 const mockDelete=mock.children.find(n=>n.className==='match-request-actions').children[0];
 await mockDelete.click();
 assert.strictEqual(view.getDemoRows().length,0);
 assert.strictEqual(demoSaves,1);
 assert.strictEqual($('sentRequestsCount').textContent,'(2)');
 assert.strictEqual(calls.filter(c=>c.path==='/api/team/respond').length,2,'deleting demo record must not call Supabase');
 console.log('Step 16 mock UI: tabs, counts, accept, cancel, declined status, contest button sync PASSED');
})().catch(error=>{console.error(error);process.exit(1)});
