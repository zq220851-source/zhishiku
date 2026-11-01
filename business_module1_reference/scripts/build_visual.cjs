// Rebuild the local 3D bundle. No remote script imports in the resulting page.
const path=require('node:path');
const visual=path.resolve(__dirname,'../web/visual');
const sourceDependencies=path.resolve(__dirname,'../../../reference_3d_glass/MedRep-Coach-Original-3D-Glass/node_modules');
const esbuild=require(require.resolve('esbuild',{paths:[visual,path.resolve(__dirname,'../../medrep_coach_with_ai_rules')]}));
esbuild.buildSync({entryPoints:[path.join(visual,'pet-entry.js')],outfile:path.join(visual,'pet.js'),bundle:true,format:'esm',minify:true,nodePaths:[path.join(visual,'node_modules'),sourceDependencies],target:'es2020'});
console.log('Built original character and splash into web/visual/pet.js');
