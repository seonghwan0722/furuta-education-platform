/* Only serializes lesson data. Restoring a file never starts a simulation or motor. */
(function(){
  'use strict';
  window.LessonBridge={register(kind,get,set){
    if(window.parent===window)return {publish(){}};
    document.body.inert=true;
    let ready=false,timer=null,epoch=0;
    function send(id){if(!ready)return;try{window.parent.postMessage({type:'lesson-state',kind,id,epoch,state:get({requested:!!id})},'*');}catch(e){window.parent.postMessage({type:'lesson-state',kind,id,epoch,error:e.message},'*');}}
    function publish(){clearTimeout(timer);timer=setTimeout(()=>send(null),180);}
    window.addEventListener('message',e=>{
      if(e.source!==window.parent||!e.data||e.data.kind!==kind)return;
      if(e.data.type==='lesson-restore'){try{epoch=e.data.epoch;set(e.data.state);ready=true;document.body.inert=false;document.body.dataset.lessonReady='true';send(e.data.id);}catch(error){document.body.inert=false;window.parent.postMessage({type:'lesson-state',kind,id:e.data.id,epoch,error:error.message},'*');}}
      if(e.data.type==='lesson-snapshot'&&ready){clearTimeout(timer);send(e.data.id);}
    });
    document.addEventListener('input',publish);document.addEventListener('change',publish);document.addEventListener('click',publish);
    window.parent.postMessage({type:'lesson-ready',kind},'*');return {publish};
  }};
})();
