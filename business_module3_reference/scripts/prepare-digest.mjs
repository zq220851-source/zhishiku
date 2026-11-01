// A coding agent can consume this JSON and follow the attached prompt, like Follow Builders.
import {collect,assemble} from '../src/core.mjs';
import {readFile} from 'node:fs/promises';
const topicArg=process.argv.find(x=>x.startsWith('--topics='));
const productArg=process.argv.find(x=>x.startsWith('--products='));
const topics=topicArg?topicArg.split('=')[1].split(','):[];
const products=productArg?productArg.split('=')[1].split(','):[];
const feed=await collect();
const prompt=await readFile(new URL('../prompts/summarize.md',import.meta.url),'utf8');
console.log(JSON.stringify({digest:assemble(feed,topics,'standard',products),prompt},null,2));
