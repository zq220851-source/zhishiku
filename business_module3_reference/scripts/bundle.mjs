import {readFile,writeFile,mkdir} from 'node:fs/promises';
const root=new URL('../',import.meta.url);
const modules=await Promise.all(['pipeline','translations','translations-io','translation','delivery','demo-profile','pinyin-map','conference','scholar','live-knowledge','core'].map(name=>readFile(new URL('src/'+name+'.mjs',root),'utf8')));
const code=modules.map(text=>text.replace(/^import .+ from '\.\/[^']+';\r?\n/gm,'')).join('\n');
let html=await readFile(new URL('src/index.html',root),'utf8');
html=html.replace('/* MODULE1_CONNECTED_UI */',await readFile(new URL('src/connected-ui.js',root),'utf8'));
await mkdir(new URL('worker/',root),{recursive:true});
await writeFile(new URL('worker/index.js',root),code+'\nconst PAGE = '+JSON.stringify(html)+';\n');
console.log('Bundled application into worker/index.js');
