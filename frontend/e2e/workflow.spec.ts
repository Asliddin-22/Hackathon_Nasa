import {test,expect} from '@playwright/test';

test('astronaut-to-doctor workflow, delayed visibility, and acknowledgment',async({page},testInfo)=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Your mission starts here.'})).toBeVisible();
 await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await expect(page.getByRole('heading',{name:'Your health, in orbit.'})).toBeVisible();
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByLabel('Delay per leg (seconds)').fill('0');
 await page.getByRole('button',{name:'Save settings',exact:true}).click();
 await expect(page.getByRole('button',{name:'Saved',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Simulate offline',exact:true}).click();
 await expect(page.getByRole('button',{name:'Restore Earth link',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Medical assistant',exact:true}).click();
 await page.getByText('Onboard symptom log and monitoring tools',{exact:true}).click();
 await page.getByLabel('Describe your symptoms').fill('Browser test: dizziness after resistance exercise');
 await page.getByRole('button',{name:'Record synthetic symptom report'}).click();
 await expect(page.getByText('Report saved and queued for medical review.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Flight surgeon Ground review & medical feedback'}).click();
 await page.getByRole('button',{name:'Enter doctor workspace'}).click();
 await expect(page.getByRole('heading',{name:'Connected care. Across the distance.'})).toBeVisible();
 await expect(page.getByLabel('Delivered finding').locator('option').filter({hasText:'Symptom report awaiting medical review'})).toHaveCount(0);
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByRole('button',{name:'Restore Earth link',exact:true}).click();
 await page.getByRole('button',{name:'Process due messages',exact:true}).click();
 await expect(page.locator('tbody').getByText('Delivered',{exact:true}).first()).toBeVisible();
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Flight surgeon Ground review & medical feedback'}).click();
 await page.getByRole('button',{name:'Enter doctor workspace'}).click();
 await expect(page.getByLabel('Delivered finding')).toBeVisible();
 await page.getByLabel('Delivered finding').selectOption({label:'Reported symptoms · Symptom report awaiting medical review'});
 await expect(page.getByText('Browser test: dizziness after resistance exercise',{exact:true})).toBeVisible();
 await page.getByLabel('Clinical review note').fill('Reviewed the synthetic dizziness report');
 await page.getByLabel('Feedback to astronaut').fill('Please record the context and collection times of the follow-up measurements.');
 await page.getByRole('button',{name:'Send reviewed feedback'}).click();
 await expect(page.getByText('Review saved. Return delivery queued.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Earth link',exact:true}).click();
 await page.getByRole('button',{name:'Process due messages',exact:true}).click();
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await page.getByRole('button',{name:'Alerts & feedback',exact:true}).click();
 await expect(page.getByText('Please record the context and collection times of the follow-up measurements.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Acknowledge',exact:true}).click();
 await expect(page.getByText(/^Acknowledged /)).toBeVisible();
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByRole('button',{name:'Process due messages',exact:true}).click();
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Flight surgeon Ground review & medical feedback'}).click();
 await page.getByRole('button',{name:'Enter doctor workspace'}).click();
 await expect(page.getByText(/^Crew acknowledgment received:/)).toBeVisible();
 expect(errors).toEqual([]);
 await page.screenshot({path:testInfo.outputPath('doctor.png'),fullPage:true});
});

test('history, manual ingestion, analysis details, simulator, and mobile layout',async({page},testInfo)=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await expect(page.getByRole('heading',{name:'Your health, in orbit.'})).toBeVisible();
 await page.screenshot({path:testInfo.outputPath('overview.png'),fullPage:true});
 await page.getByRole('button',{name:/Cardiovascular Review needed/}).first().click();
 await expect(page.getByRole('dialog')).toContainText('Experimental rule: 15% increase');
 await page.getByRole('button',{name:'Close ×'}).click();
 await page.getByRole('button',{name:'Health history',exact:true}).click();
 await page.getByRole('button',{name:'Add measurement',exact:true}).click();
 await page.getByLabel('Value (bpm)').fill('72');
 await page.getByRole('button',{name:'Save measurement',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByLabel('Data provenance').selectOption('manual');
 await expect(page.locator('tbody tr')).toHaveCount(1);
 await expect(page.locator('tbody')).toContainText('72');
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV'}).click();
 expect((await download).suggestedFilename()).toBe('gravityguard-resting_hr.csv');
 await page.getByRole('button',{name:'Health overview',exact:true}).click();
 await page.getByRole('button',{name:'Start simulator',exact:true}).click();
 await expect(page.getByRole('button',{name:'Pause simulator',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Pause simulator',exact:true}).click();
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Open navigation',exact:true}).click();
 await page.getByRole('button',{name:'Health history',exact:true}).click();
 await expect(page.getByRole('heading',{name:'A history worth understanding.'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await expect(page.locator('.sidebar')).toHaveCSS('transform','matrix(1, 0, 0, 1, -240, 0)');
 await page.screenshot({path:testInfo.outputPath('mobile.png'),fullPage:true});
 expect(errors).toEqual([]);
});

test('built dashboard runs from FastAPI without external asset requests',async({page},testInfo)=>{
 const remote:string[]=[];
 await page.route('**/*',async route=>{
   const host=new URL(route.request().url()).hostname;
   if(host!=='127.0.0.1'&&host!=='localhost'){remote.push(route.request().url());await route.abort();return}
   await route.continue();
 });
 await page.goto('http://127.0.0.1:8002/');
 await expect(page.getByRole('heading',{name:'Your mission starts here.'})).toBeVisible();
 await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await expect(page.getByRole('heading',{name:'Your health, in orbit.'})).toBeVisible();
 await expect(page.getByRole('img',{name:/Resting heart rate daily mean chart/})).toBeVisible();
 expect(remote).toEqual([]);
});

test('offline conversation is honest, persists, and does not fabricate a clinical assessment',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await page.getByRole('button',{name:'Medical assistant',exact:true}).click();
 await page.getByLabel('Your medical question',{exact:true}).fill('Explain oxygen transport.');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 const card=page.getByRole('article',{name:'Medical assistant answer'});
 await expect(card).toContainText('Generation unavailable');
 await card.getByText('Detailed analysis',{exact:true}).click();
 await expect(card.getByRole('heading',{name:'Patient observations'})).toHaveCount(0);
 await page.reload();await page.getByRole('button',{name:'Medical assistant',exact:true}).click();
 await expect(page.getByText('Explain oxygen transport.',{exact:true})).toBeVisible();
});

test('generated education, a conversational follow-up, and selectively retrieved personal evidence',async({page},testInfo)=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 // This backend uses mocked model responses, with remote transport blocked.
 await page.goto('http://127.0.0.1:8003/');
 await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await page.getByRole('button',{name:'Medical assistant',exact:true}).click();
 await page.getByLabel('Your medical question',{exact:true}).fill('Why do hormone signals act at a distance?');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 const card=page.getByRole('article',{name:'Medical assistant answer'});
 await expect(card).toContainText('Muse Wonder · generated');
 await expect(card).toContainText('General model knowledge');
 const first=await card.locator('.assistant-short').innerText();
 await card.getByText('Detailed analysis',{exact:true}).click();
 await expect(card.getByRole('heading',{name:'Patient observations'})).toHaveCount(0);
 await expect(card.getByRole('heading',{name:'Generated explanation'})).toBeVisible();
 await page.getByLabel('Continue this conversation',{exact:true}).fill('What makes those signals stop?');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 await expect(card.locator('.assistant-short')).not.toHaveText(first);
 await expect(card).toContainText('Muse Wonder · generated');
 await page.getByRole('button',{name:'New conversation',exact:true}).click();
 await page.getByLabel('Your medical question',{exact:true}).fill('My arms tire earlier in resistance sessions. What should I consider?');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 await expect(card).toContainText('Muse Wonder · generated');
 await card.getByText('Detailed analysis',{exact:true}).click();
 await expect(card.getByRole('heading',{name:'Patient observations'})).toBeVisible();
 await expect(card.locator('tbody')).toContainText('Muscle strength');
 await expect(card.locator('tbody')).not.toContainText('Resting heart rate');
 await page.screenshot({path:testInfo.outputPath('generated-conversation.png'),fullPage:true});
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByLabel('Delay per leg (seconds)').fill('0');
 await page.getByRole('button',{name:'Save settings',exact:true}).click();
 // Previously queued messages keep their original due time; make another turn
 // after changing delay, then deliver that actual review request.
 await page.getByRole('button',{name:'Medical assistant',exact:true}).click();
 await page.getByRole('button',{name:'New conversation',exact:true}).click();
 await page.getByLabel('Your medical question',{exact:true}).fill('My arms tire earlier in resistance sessions. What should I consider?');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 await expect(card).toContainText('Muse Wonder · generated');
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByRole('button',{name:'Process due messages',exact:true}).click();
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Flight surgeon Ground review & medical feedback'}).click();
 await page.getByRole('button',{name:'Enter doctor workspace'}).click();
 await page.getByLabel('Delivered finding').selectOption({label:'AI assistant review · Medical assistant conversation for review'});
 await expect(page.getByRole('article',{name:'Medical assistant answer'}).first()).toContainText('Muse Wonder · generated');
 expect(errors).toEqual([]);
});


test('emergency guidance precedes generation, chat continues, and conversations reach doctor',async({page})=>{
 const failures:string[]=[];page.on('response',r=>{if(r.status()>=500)failures.push(`${r.status()} ${r.url()}`)});
 await page.goto('http://127.0.0.1:8003/');
 await page.getByRole('button',{name:'Enter astronaut workspace'}).click();
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByLabel('Delay per leg (seconds)').fill('0');
 await page.getByRole('button',{name:'Save settings',exact:true}).click();
 await expect(page.getByRole('button',{name:'Saved',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Medical assistant',exact:true}).click();
 await page.getByRole('button',{name:'New conversation',exact:true}).click();
 await page.getByLabel('Your medical question',{exact:true}).fill('An unfamiliar serious change is happening. Can you help me understand it?');
 await page.getByLabel('I am reporting warning signs that need immediate onboard attention.',{exact:true}).check();
 await page.getByLabel('Medical personnel available?').selectOption('no');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 const card=page.getByRole('article',{name:'Medical assistant answer'});
 await expect(card.getByRole('heading',{name:'Independent emergency guidance'})).toBeVisible();
 await expect(card).toContainText('You can continue chatting while it is prepared.');
 await expect(page.getByRole('button',{name:'Ask medical assistant',exact:true})).toBeEnabled();
 await page.getByLabel('Continue this conversation',{exact:true}).fill('It started suddenly and I am alone. What information matters?');
 await page.getByRole('button',{name:'Ask medical assistant',exact:true}).click();
 await expect(card.getByRole('heading',{name:'Independent emergency guidance'})).toBeVisible();
 await expect(card).toContainText('Muse Wonder · generated');
 await card.getByText('Detailed analysis',{exact:true}).click();
 await expect(card.getByRole('heading',{name:'Generated explanation'})).toBeVisible();
 await expect(card.getByRole('heading',{name:'Follow-up questions'})).toBeVisible();
 await expect(card).toContainText('No mission-approved clinical procedure is installed');
 await page.getByRole('button',{name:'Mission & Earth link',exact:true}).click();
 await page.getByRole('button',{name:'Process due messages',exact:true}).click();
 await page.getByRole('button',{name:'Sign out and switch workspace'}).click();
 await page.getByRole('button',{name:'Flight surgeon Ground review & medical feedback'}).click();
 await page.getByRole('button',{name:'Enter doctor workspace'}).click();
 const archive=page.locator('section').filter({has:page.getByRole('heading',{name:'Medical assistant history',exact:true})});
 await expect(archive.getByText('An unfamiliar serious change is happening. Can you help me understand it?',{exact:false})).toBeVisible();
 await expect(archive.getByText('It started suddenly and I am alone. What information matters?',{exact:false})).toBeVisible();
 expect(failures).toEqual([]);
});


test('concurrent background generations, polling, and sync complete without SQLite write conflicts',async({request})=>{
 const base='http://127.0.0.1:8003/api';
 const auth=await request.post(`${base}/auth/login`,{data:{username:'astronaut',password:'demo-orbit-2026'}});
 const session=await auth.json();const headers={Authorization:`Bearer ${session.token}`};
 const setting=await request.patch(`${base}/mission/context`,{headers,data:{online:true,delay_seconds:0}});expect(setting.status()).toBe(200);
 const submitted=await Promise.all(Array.from({length:4},()=>request.post(`${base}/assistant/messages`,{headers,data:{question:'An unfamiliar serious change is happening. Can you help me understand it?',warning_signs:true,wait_for_completion:false}})));
 expect(submitted.map(r=>r.status())).toEqual([201,201,201,201]);
 const messages=await Promise.all(submitted.map(r=>r.json()));
 const syncing=await Promise.all(Array.from({length:6},()=>request.post(`${base}/sync`,{headers})));
 expect(syncing.every(r=>r.status()===200)).toBeTruthy();
 await expect.poll(async()=>{
   const states=await Promise.all(messages.map(async m=>{const response=await request.get(`${base}/assistant/messages/${m.id}`,{headers});expect(response.status()).toBe(200);return (await response.json()).generation_status}));
   return states;
 },{timeout:15000}).toEqual(['complete','complete','complete','complete']);
 expect((await request.post(`${base}/sync`,{headers})).status()).toBe(200);
 const doctor=await (await request.post(`${base}/auth/login`,{data:{username:'doctor',password:'demo-orbit-2026'}})).json();
 const archive=await (await request.get(`${base}/doctors/conversations/astro-01`,{headers:{Authorization:`Bearer ${doctor.token}`}})).json();
 for(const m of messages)expect(archive.find((r:{message:{id:string}})=>r.message.id===m.id).message.generation_status).toBe('complete');
});
