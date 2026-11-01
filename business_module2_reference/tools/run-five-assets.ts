/** Regenerates QA observed.json; never imports the frozen gold or review checker. */
import { readFileSync, writeFileSync } from 'node:fs';
import { Store } from '../lib/store';
import { FiveAssetLedger, type VisitEvidence } from '../lib/five-assets';
const records = JSON.parse(readFileSync(new URL('../tests/fixtures/five-asset-visits.json',import.meta.url),'utf8')) as VisitEvidence[];
const store = new Store(':memory:');
try {
  const ledger = new FiveAssetLedger(store);
  const snapshots = records.map((input, index) => {
    const result = ledger.record(input);
    return { step:index+1, submitted:{visitId:input.visitId,rawVersion:input.rawVersion},newEntries:result.entries,activeEntries:ledger.currentEntries(),cohort:ledger.cohortSummary(),historyV1:ledger.history('V1').length,activeVisits:ledger.current().length };
  });
  writeFileSync(new URL('../qa/observed.json',import.meta.url), JSON.stringify(snapshots,null,2));
  console.log(`Generated ${snapshots.length} snapshots from actual ledger rules.`);
} finally {store.close();}
