// Render editable layouts with the released font, never simulated letterforms.
const {chromium}=require('playwright');
const path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1280,height:640},deviceScaleFactor:1.5});
 const url=pathToFileURL(path.join(root,'specimen/cover.html')).href;
 fs.mkdirSync(path.join(root,'qa'),{recursive:true});
 for(const [name,hash] of [['banner',''],['features','#examples']]){
  await page.goto(url+hash);await page.evaluate(()=>document.fonts.ready);
  if(!await page.evaluate(()=>document.fonts.check('100px "Valera Sans"')))throw Error('Font not loaded');
  await page.screenshot({path:path.join(root,`qa/preview-${name}.png`)});
 }
 await page.close();
 const social=await browser.newPage({viewport:{width:1280,height:640},deviceScaleFactor:1});
 await social.goto(url);await social.evaluate(()=>document.fonts.ready);
 await social.screenshot({path:path.join(root,'specimen/social-preview.jpg'),type:'jpeg',quality:94});
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
