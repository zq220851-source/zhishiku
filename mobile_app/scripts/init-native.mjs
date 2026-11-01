import {existsSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
const targets = process.platform === 'darwin' ? ['android','ios'] : ['android'];
for (const target of targets) {
  if (!existsSync(target)) {
    console.log(`Creating ${target} native project with Capacitor...`);
    execFileSync('npx', ['cap', 'add', target], {stdio:'inherit'});
  }
}
execFileSync('npx',['cap','sync'],{stdio:'inherit'});
if (process.platform !== 'darwin') console.log('iOS target: run npx cap add ios on a Mac with Xcode.');
