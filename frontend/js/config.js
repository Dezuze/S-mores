(function(){
  // HARDCODED implementation to ensure we hit the backend (Port 8000)
  // and avoid hitting the static server (Port 3000) which returns 501 on POST.
  const backendUrl = 'http://localhost:8000';
  
  window.API_BASE = backendUrl;
  console.log("Configured API_BASE:", window.API_BASE);

  // Helper can remain for future, but defaults are strict now
  window.setApiBase = function(url){
    window.API_BASE = url;
    console.log("Updated API_BASE:", window.API_BASE);
  };
})();
