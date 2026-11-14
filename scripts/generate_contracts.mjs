/** Generate TS from the checked-in schema using the locked local generator. */
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';

const root = new URL('../', import.meta.url);
const schema = JSON.parse(await readFile(new URL('contracts/generated/schema.json', root), 'utf8'));

function guardRefs(value) {
  if (value === null || typeof value !== 'object') return;
  if ('$ref' in value && !/^#\/\$defs\/[A-Za-z0-9_]+$/.test(value.$ref)) {
    throw new Error(`Nonlocal schema reference refused: ${value.$ref}`);
  }
  for (const child of Object.values(value)) guardRefs(child);
}
guardRefs(schema);

let content = await compile(schema, 'AplombContracts', {
  bannerComment: '// Generated from contracts/generated/schema.json. Run npm run generate:contracts.\n// Do not edit; see contracts/README.md.',
  additionalProperties: false,
  unknownAny: true,
  unreachableDefinitions: true,
  enableConstEnums: false,
  $refOptions: { resolve: { external: false } },
});
// The upstream generator normalizes acronyms (I18nText -> I18NText). Keep every
// public spelling from the registry available to consumers without hand edits.
const exportedNames = new Set([...content.matchAll(/export (?:interface|type|enum) (\w+)/g)]
  .map(match => match[1]));
for (const name of Object.keys(schema.$defs)) {
  if (!exportedNames.has(name)) content += `\nexport type ${name} = AplombContracts["${name}"];\n`;
}
const target = new URL('web/src/contracts/types.ts', root);
if (process.argv.includes('--check')) {
  if (await readFile(target, 'utf8').catch(() => null) !== content) {
    throw new Error(`Generated file is stale: ${fileURLToPath(target)}; run npm run generate:contracts`);
  }
} else {
  await writeFile(target, content);
}
console.log('TypeScript contract types are current.');
