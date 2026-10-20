const text=document.querySelector('#text'),size=document.querySelector('#size'),tracking=document.querySelector('#tracking');
const supported=new Set(Array.from(' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_abcdefghijklmnopqrstuvwxyz{|}~\u00a0«»ЁАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдежзийклмнопрстуфхцчшщъыьэюяё\u2009–—…\u202f₽№\n\r\t'));
if(innerWidth<650)size.value='36';
function update(){
 const px=Number(size.value),tr=Number(tracking.value)/1000;
 text.style.fontSize=px+'px';document.querySelector('#size-value').value=px+' px';
 text.style.letterSpacing=tr+'em';document.querySelector('#tracking-value').value=(tr>0?'+':'')+tr.toFixed(3)+' em';
 text.style.fontFeatureSettings=document.querySelector('#calt').checked?'"calt" 1':'"calt" 0';
 text.style.fontKerning=document.querySelector('#kern').checked?'normal':'none';
 text.style.fontVariantNumeric=document.querySelector('#tnum').checked?'tabular-nums':'normal';
 text.style.height='auto';text.style.height=Math.max(280,text.scrollHeight+4)+'px';
 const missing=[...new Set([...text.value].filter(c=>!supported.has(c)))];
 document.querySelector('#support').textContent=missing.length?'В шрифте пока нет: '+missing.join(' ')+'. Эти знаки показывает запасной шрифт.':'Настоящий шрифт. Текст остаётся на твоём устройстве.';
}
document.querySelectorAll('[data-weight]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-weight]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));text.style.fontWeight=button.dataset.weight;update()}));
for(const el of [text,size,tracking,...document.querySelectorAll('.switches input')])el.addEventListener('input',update);
Promise.all([300,400,600].map(w=>document.fonts.load(`${w} 64px "Valera Sans"`))).then(update);update();
