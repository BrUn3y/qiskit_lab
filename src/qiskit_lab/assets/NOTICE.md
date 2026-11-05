# Report asset notices

- IBM Carbon Design System styles: `@carbon/styles` 1.119.0, Apache-2.0.
  Copyright IBM Corp. Official source: https://github.com/carbon-design-system/carbon
  The included `carbon.css` is compiled from the official reset, button, tag,
  table, text-input, link, select and Gray 100 theme Sass modules.
  License: `CARBON-LICENSE`.
- IBM Plex Sans 1.1.0 and IBM Plex Mono 2.5.0 fonts, SIL Open Font License 1.1.
  Copyright IBM Corp. Official source: https://github.com/IBM/plex
  Latin 1 font subsets are embedded in `fonts.css` without modification.
  License: `PLEX-LICENSE`.
- `report.css` and `report.js` implement the Qiskit Lab report layout and
  progressive enhancements. SVG charts use Carbon colors and theme tokens.

Rebuild with `npm ci --ignore-scripts` and `npm run build` in
`tools/report-assets`. Exact npm dependencies are pinned in its lockfile.
The Python runtime does not require Node.js, Sass or a CDN.
