import {readFile,writeFile} from 'node:fs/promises';
import {translationSeeds} from '../src/translations.mjs';
import {sourceFingerprint,validateTranslation} from '../src/translation.mjs';
const path=process.argv[2];if(!path)throw new Error('用法：node scripts/import-translations.mjs translations.json');
const records=JSON.parse(await readFile(path,'utf8'));if(!Array.isArray(records)||!records.length)throw new Error('需要非空 JSON 数组');
const updated={...translationSeeds};
for(const row of records){
 if(typeof row.id!=='string'||!row.id||typeof row.sourceTitle!=='string'||!row.sourceTitle||typeof row.sourceAbstract!=='string'||!row.sourceAbstract)throw new Error('每条需要 id、sourceTitle、sourceAbstract');
 const source={originalTitle:row.sourceTitle,abstract:row.sourceAbstract};
 updated[row.id]={...validateTranslation(row,source),sourceHash:await sourceFingerprint(source),translatedAt:new Date().toISOString()};
}
await writeFile(new URL('../src/translations.mjs',import.meta.url),'// Exact-source AI translation cache; not medically reviewed.\nexport const translationSeeds = '+JSON.stringify(updated,null,2)+';\n');
console.log('已导入 '+records.length+' 条译文。请重新构建并重启服务。');
