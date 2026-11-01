/** Explicit live check: sends only the fictional fixture, never database feedback. Not part of npm test. */
import { loadEnvConfig } from '@next/env';
import { mkdirSync, writeFileSync } from 'node:fs';
import { mainFixture, sampleReflection } from '../lib/fixture';
import { modelProvider, settings, promptVersion } from '../lib/provider';
import { validateExtraction, derive } from '../lib/analysis';
import { Module2Error } from '../lib/errors';

async function main() {
  loadEnvConfig(process.cwd());
  const config = settings(), fixture = mainFixture();
  const started = Date.now();
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const response = await originalFetch(input, init);
    const wire = await response.clone().text();
    mkdirSync('.data', { recursive: true, mode: 0o700 });
    writeFileSync('.data/live-response.txt', wire.replaceAll(config.apiKey, '[REDACTED]'), { mode: 0o600 });
    return response;
  };
  try {
    const output = await modelProvider(config)(sampleReflection, fixture.codebook);
    mkdirSync('.data', { recursive: true, mode: 0o700 });
    writeFileSync('.data/live-extraction.json', JSON.stringify(output, null, 2), { mode: 0o600 });
    const extraction = validateExtraction(sampleReflection, output, fixture.codebook);
    const analysis = derive(extraction, fixture, config.model, promptVersion);
    const summary = { transportAndSchemaPassed: true, model: config.model, durationMs: Date.now() - started,
      units: analysis.units.length, relations: analysis.relations.length,
      differences: analysis.differences.map(d => ({ skillId: d.skillId, coverage: d.coverage, personalSignal: d.personalSignal })),
      expectedMainSignalsFound: analysis.differences.some(d => d.skillId === 'endpoint-explanation' && d.coverage === 'FULL') && analysis.differences.some(d => d.skillId === 'subgroup-extrapolation' && d.coverage === 'NONE' && d.personalSignal === 'PENDING_VERIFY') };
    mkdirSync('.data', { recursive: true, mode: 0o700 });
    writeFileSync('.data/live-analysis.json', JSON.stringify({ rawText: sampleReflection, analysis }, null, 2), { mode: 0o600 });
    writeFileSync('docs/verification-live-api.json', JSON.stringify(summary, null, 2));
    console.log(JSON.stringify(summary));
    if (!summary.expectedMainSignalsFound) process.exitCode = 1;
  } catch (error) {
    const safe = error instanceof Module2Error ? { code: error.code, message: error.message } : { code: 'LIVE_REQUEST_FAILED' };
    console.log(JSON.stringify({ transportAndSchemaPassed: false, model: config.model, durationMs: Date.now() - started, error: safe }));
    process.exitCode = 1;
  } finally { globalThis.fetch = originalFetch; }
}
void main();
