# Gemini API smoke test failure

- endpoint: https://api.genai.mil/v1/chat/completions
- model_requested: gemini-2.5-flash
- status_code: 503
- exception_message: The remote server returned an error: (503) Server Unavailable.
- error_details: 

  
    
    
    Unauthorized Access - GenAI.mil
    
    
    
*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;background-color:#0b0b1d;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;position:relative;overflow:hidden;touch-action:manipulation;-webkit-tap-highlight-color:transparent}#network-canvas{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;touch-action:none;-webkit-user-select:none;user-select:none}@media (prefers-reduced-motion:reduce){#network-canvas{display:none}}.error-container{background:rgba(31,41,55,0.7);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid rgb(55,65,81);border-radius:12px;box-shadow:0 20px 25px -5px rgba(0,0,0,0.1),0 10px 10px -5px rgba(0,0,0,0.04);max-width:620px;width:100%;padding:48px 32px;text-align:center;position:relative;z-index:1}.logo{max-width:300px;height:auto;margin:0 auto 32px;display:block}.error-code{font-size:72px;font-weight:700;color:#dc2626;margin-bottom:16px;line-height:1}h1{font-size:28px;font-weight:600;color:#f9fafb;margin-bottom:16px}.error-message{font-size:18px;color:#d1d5db;margin-bottom:32px;line-height:1.6}.info-box{background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:20px;margin-bottom:24px;text-align:left}.info-box p{color:#991b1b;font-size:14px;line-height:1.6;margin-bottom:12px}.info-box p:last-child{margin-bottom:0}.info-box strong{font-weight:600}.contact-info{font-size:14px;color:#4b5563;margin-top:24px;padding-top:24px;border-top:1px solid #e5e7eb}.contact-info a{color:#2563eb;text-decoration:none}.contact-info a:hover{text-decoration:underline}.cta-box{margin-top:24px;text-align:center}.cta-box p{font-size:18px;color:#d1d5db;margin-bottom:8px;line-height:1.6}.cta-box a{color:#06b6d4;text-decoration:none;font-size:18px}.cta-box a:hover{text-decoration:underline}@media (max-width:768px){.error-container{padding:40px 28px}.error-code{font-size:64px}h1{font-size:26px}.error-message{font-size:17px}.cta-box p{font-size:17px}.cta-box a{font-size:17px}.logo{max-width:225px}}@media (max-width:640px){.error-container{padding:32px 24px}.error-code{font-size:56px}h1{font-size:24px}.error-message{font-size:16px}.cta-box p{font-size:16px}.cta-box a{font-size:16px}.logo{max-width:150px}}
  
  
    
    
      

      
        You have reached this page because you are not authorized to visit
        GenAI.mil from outside of DoW networks. If you believe this is an error,
        please contact your command's IT service desk.
      

      
        Want to access the DoW's latest AI tools? Join today!
        
          https://www.todaysmilitary.com/
        
      
    


!function(){if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;const c=document.getElementById('network-canvas');if(!c)return;const x=c.getContext('2d',{alpha:!0,desynchronized:!0});if(!x){c.style.display='none';return}const P='rgba(6, 182, 212, 0.6)',L='rgba(6, 182, 212, 0.15)',M=120;let p=[],a,r=()=>{c.width=window.innerWidth;c.height=window.innerHeight},n=(w,h)=>Math.max(20,Math.floor(w*h/15e3)),m=t=>{const s=[];for(let i=0;i{o.x+=o.vx;o.y+=o.vy;if(o.xc.width)o.vx*=-1;if(o.yc.height)o.vy*=-1},d=()=>{x.fillStyle=P;p.forEach(o=>{x.beginPath();x.arc(o.x,o.y,o.radius,0,Math.PI*2);x.fill();u(o)})},l=()=>{x.strokeStyle=L;x.lineWidth=1;for(let i=0;i{x.clearRect(0,0,c.width,c.height);d();l();a=requestAnimationFrame(f)},init=()=>{r();p=m(n(c.width,c.height));f()};init();window.addEventListener('resize',()=>{a&&cancelAnimationFrame(a);init()})}()

  


- created_utc: 2026-05-28T10:58:46Z
