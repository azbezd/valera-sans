const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const base=process.env.SPECIMEN_URL||'http://127.0.0.1:8000/';
const expected=JSON.parse(fs.readFileSync(path.join(ROOT,'tests/browser-expected.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH,headless:true}:{headless:true});
 const results=[];
 for(const width of [390,1440])for(const colorScheme of ['light','dark']){
  const page=await browser.newPage({viewport:{width,height:1100},colorScheme});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(new URL('specimen/',base).href,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);
  const measurements=await page.evaluate(async({expected,base})=>{
   // One CSS pixel per font unit avoids OS-specific fractional-pixel advance
   // rounding at small sizes while keeping the strict shaping comparison.
   const el=document.createElement('span');el.style.cssText='position:absolute;visibility:hidden;white-space:pre;font-size:1000px;letter-spacing:0';document.body.append(el);const rows=[];
   for(const [ext,folder]of[['ttf','ttf'],['otf','otf'],['woff2','web']])for(const [style,cases]of Object.entries(expected)){
    const family='Check'+style+ext,weight={Light:300,Regular:400,Semibold:600}[style];
    const ff=new FontFace(family,`url("${new URL(`fonts/${folder}/ValeraSans-${style}.${ext}`,base).href}")`,{weight:String(weight)});
    await ff.load();document.fonts.add(ff);el.style.fontFamily=family;el.style.fontWeight=weight;
    for(const c of cases){el.textContent=c.text;el.style.fontFeatureSettings=c.calt?'"calt" 1':'"calt" 0';el.style.fontKerning=c.kern?'normal':'none';rows.push({ext,style,...c,actual:el.getBoundingClientRect().width})}
   }el.remove();return rows;
  },{expected,base});
  for(const r of measurements)assert(Math.abs(r.actual-r.width_units)<.12,JSON.stringify(r));
  await page.locator('#calt').uncheck();assert((await page.locator('#text').evaluate(e=>getComputedStyle(e).fontFeatureSettings)).includes('0'));
  await page.locator('#calt').check();await page.locator('#kern').uncheck();assert.equal(await page.locator('#text').evaluate(e=>getComputedStyle(e).fontKerning),'none');await page.locator('#kern').check();
  await page.locator('#tnum').check();assert.equal(await page.locator('#text').evaluate(e=>getComputedStyle(e).fontVariantNumeric),'tabular-nums');await page.locator('#tnum').uncheck();
  for(const weight of ['300','600','400']){await page.locator(`[data-weight="${weight}"]`).click();assert.equal(await page.locator('#text').evaluate(e=>getComputedStyle(e).fontWeight),weight)}
  await page.locator('#text').fill('Valera / er re / ёж');assert(!(await page.locator('#support').innerText()).includes('пока нет'));
  await page.locator('#text').fill('café');assert((await page.locator('#support').innerText()).includes('é'));
  await page.locator('#text').fill('Буквы, как от руки.\nValera / river / rare\nКраски, бумага, вещи вокруг.');
  await page.locator('#tracking').evaluate(e=>{e.value='20';e.dispatchEvent(new Event('input',{bubbles:true}))});assert((await page.locator('#tracking-value').innerText()).includes('+0.020'));
  await page.locator('#tracking').evaluate(e=>{e.value='0';e.dispatchEvent(new Event('input',{bubbles:true}))});
  assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));assert.equal(errors.length,0);
  await page.screenshot({path:path.join(ROOT,`qa/browser-${width}-${colorScheme}.png`),fullPage:true});
  results.push({width,colorScheme,measurements:measurements.length,font_formats:3,weights:3,controls:true,coverage_feedback:true,overflow:false,errors});await page.close();
 }
 await browser.close();fs.writeFileSync(path.join(ROOT,'qa/browser-validation.json'),JSON.stringify(results,null,2)+'\n');
 console.log('Browser checks passed:',results.reduce((sum,r)=>sum+r.measurements,0),'measurements');
})().catch(e=>{console.error(e);process.exit(1)});
