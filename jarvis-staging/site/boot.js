// Runs without external dependencies. Never handles tokens or private data.
(function(){
  const login=document.getElementById('login');
  const warning=document.getElementById('login-message');
  const status=document.getElementById('status-label');
  if(login)login.hidden=false;
  const showFailure=()=>{
    if(window.jarvisInitialized===true)return;
    if(status)status.textContent='REVISAR CONEXIÓN';
    if(warning)warning.textContent='No se pudo iniciar la conexión segura. Comprueba Internet y recarga la página.';
  };
  window.addEventListener('error',function(event){
    if(window.jarvisInitialized!==true && String(event.filename||'').includes('app.js'))showFailure();
  });
  window.addEventListener('unhandledrejection',function(){if(window.jarvisInitialized!==true)showFailure()});
  const timer=window.setTimeout(showFailure,11000);
  window.addEventListener('jarvis:initialized',()=>window.clearTimeout(timer),{once:true});
  const form=document.getElementById('login-form');
  if(form)form.addEventListener('submit',function(event){
    if(window.jarvisInitialized===true)return;
    event.preventDefault();showFailure();
  });
})();
