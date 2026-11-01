/** Compile only module2/lib into a disposable directory for portable Node 22 benchmark. */
const fs=require('node:fs');
const path=require('node:path');
let ts;
try {ts=require(require.resolve('typescript',{paths:[process.cwd(),path.dirname(process.execPath)+'/../lib/node_modules']}));}
catch {console.error('TypeScript compiler not found. Install project dependencies or make `typescript` available to Node.');process.exit(2);}
const root=path.resolve(__dirname,'..');
const out=path.join(root,'.bench-compiled');
function walk(dir){for(const item of fs.readdirSync(dir,{withFileTypes:true})){
 const src=path.join(dir,item.name);
 if(item.isDirectory())walk(src);
 else if(src.endsWith('.ts')&&!src.endsWith('.d.ts')){
  const dest=path.join(out,path.relative(root,src)).replace(/\.ts$/,'.js');
  const result=ts.transpileModule(fs.readFileSync(src,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,esModuleInterop:true}});
  fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,result.outputText);
 }
}}
walk(path.join(root,'lib'));
console.log('Benchmark build complete (transpile only; NOT full project typecheck).');
