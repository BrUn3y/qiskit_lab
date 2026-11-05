// Bundle licensed IBM Plex fonts so opening the report makes no external requests.
import { readFileSync, writeFileSync } from 'node:fs';
const assets = new URL('../../src/qiskit_lab/assets/', import.meta.url);
let css = '';
for (const [family, name, weight] of [
  ['Sans', 'Light', 300], ['Sans', 'Regular', 400], ['Sans', 'SemiBold', 600], ['Mono', 'Regular', 400],
]) {
  const base = `node_modules/@ibm/plex-${family.toLowerCase()}/`;
  const font = new URL(`${base}fonts/split/woff2/IBMPlex${family}-${name}-Latin1.woff2`, import.meta.url);
  css += `@font-face{font-family:'IBM Plex ${family}';font-weight:${weight};font-style:normal;font-display:swap;src:url(data:font/woff2;base64,${readFileSync(font).toString('base64')}) format('woff2')}\n`;
}
writeFileSync(new URL('fonts.css', assets), css);
for (const [source, name] of [['@carbon/styles/LICENSE', 'CARBON-LICENSE'], ['@ibm/plex-sans/LICENSE.txt', 'PLEX-LICENSE']]) {
  const text = readFileSync(new URL(`node_modules/${source}`, import.meta.url), 'utf8');
  writeFileSync(new URL(name, assets), text.replace(/\r\n/g, '\n').replace(/[ \t]+$/gm, ''));
}
