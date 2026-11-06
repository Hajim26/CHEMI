const fs=require('fs'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const start=script.indexOf('      let memberDialogContext = null;');
const end=script.indexOf('      function teammateMatchElement(contest) {',start);
assert(start>0 && end>start);
const snippet=script.slice(start,end);
class El {
 constructor(){this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.style={};this.isConnected=true;this.kids=[];this.classList={add(){},remove(){}};this.dataset={};}
 replaceChildren(){this.kids=[];}
 append(obj){this.kids.push(obj);}
 focus(){doc.activeElement=this;}
 addEventListener(){}
}
const elements=new Map();
const $=(name)=>{if(!elements.has(name))elements.set(name,new El());return elements.get(name);};
const doc={body:{style:{overflow:''}}, activeElement:new El(), createElement(){return new El();},addEventListener(){}};
$('memberProfileOverlay').hidden=true;
const state={competencies:[{name:'Python 백엔드'},{name:'데이터 분석'}]};
let backendPosts=[];
const apiCall=async(path,method,body)=>{backendPosts.push({path,method,body});return {ok:true}};
const loadMatchRequests=async()=>{};
const renderContests=()=>{};
const contestMatchKey=c=>c.url || c.title;
const controller=Function('document','$','state','previewMode','actualMatchEnabled','cloudMode','signedIn','contestMatchKey','confirm','apiCall','loadMatchRequests','renderContests',snippet+';return {openMemberProfile,closeMemberProfile,sendMemberInvitation,sendDemoInvitation,demoInvitationExists,isRealInviteAllowed};');
const helper=controller(doc,$,state,false,true,true,true,contestMatchKey,()=>true,apiCall,loadMatchRequests,renderContests);
const contest={title:'예시 AI 공모전',url:'contest-example-id'};
const fake={id:'TM001',nickname:'가상 학생',university:'시연대학교',major:'디자인학과',grade:'2학년',skills:[{name:'Figma'}],interests:['디자인'],is_synthetic:true,bio:'예시 인물'};
const score={member:fake,score:84,reason:'디자인 역할을 보완할 수 있어요.',source:'rules'};
helper.openMemberProfile(contest,score,new El());
assert.equal($('memberProfileOverlay').hidden,false);
assert.equal($('memberDialogInvite').hidden,false,'mock invite must be visible for synthetic members');
assert($('memberDialogInvite').textContent.includes('시연'));
assert.equal(helper.sendDemoInvitation(fake,contest,new El()),true,'mock invite should be allowed');
assert.equal(helper.demoInvitationExists(fake,contest),true);
assert.equal(backendPosts.length,0,'synthetic invite never reaches real API');
assert.equal($('memberDialogTitle').textContent,'가상 학생');
assert.equal($('memberDialogMySkills').kids.length,2);
assert.equal($('memberDialogTheirSkills').kids[0].textContent,'Figma');
assert.equal($('memberDialogBioSection').hidden,false);
helper.closeMemberProfile();assert.equal($('memberProfileOverlay').hidden,true);
const real={id:'00000000-0000-0000-0000-000000000001',nickname:'참여 회원',major:'컴퓨터공학과',skills:[{name:'API 개발'}],interests:['AI·개발'],is_synthetic:false};
const realResult={member:real,score:81,reason:'서비스 개발 역할 보완',source:'ai'};
helper.openMemberProfile(contest,realResult,new El());
assert.equal($('memberDialogInvite').hidden,false);
assert.equal($('memberDialogBioSection').hidden,true);
assert.equal($('memberDialogMeta').textContent,'컴퓨터공학과');
assert.equal($('memberDialogScoreType').textContent,'AI 선정 · 예비점수');
(async()=>{
  const btn=new El();
  const sent=await helper.sendMemberInvitation(real,contest,btn,'함께하고 싶습니다');
  assert.equal(sent,true);
  assert.equal(backendPosts.length,1);
  assert.equal(backendPosts[0].path,'/api/team/request');
  assert.equal(backendPosts[0].body.message,'함께하고 싶습니다');
  const duplicate=await helper.sendMemberInvitation(real,contest,new El(),'');
  assert.equal(duplicate,false);
  console.log('Step 14 mock-DOM interaction checks passed: demo-only invite, profile, real invite, duplicate prevention');
})().catch(err=>{console.error(err);process.exit(1)});
