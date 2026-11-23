# Qiskit Lab project website

An English project website inspired by the supplied editorial-grid reference.
It uses static HTML, CSS, and JavaScript, with no build step or runtime dependencies.
The DAM and Qiskit logos were supplied by the repository owner. They appear as
“Built on DAM” and “Built with Qiskit” technology credits in the header and footer.
The project uses its own text wordmark and QL favicon, separate from these credits.
IBM Plex fonts are
self-hosted; their license is in `assets/PLEX-LICENSE.txt`.

Preview from the repository root:

```sh
python3 -m http.server 4173 --directory site --bind 127.0.0.1
```

Open <http://127.0.0.1:4173>. The `Publish project website` GitHub Actions
workflow deploys this directory to <https://brun3y.github.io/qiskit_lab/> when
website changes reach `main`. GitHub Pages must use the GitHub Actions source.
Deployment adds content versions to the stylesheet and script URLs so browsers
load the matching assets after an update.

The DAM setup instructions follow the catalog workflow: **Starter kits → Research
→ Qiskit Lab → Use this starter kit**. The owner-supplied animated walkthrough
appears beneath the instructions. Its pause control uses a still frame; the site
animation control and reduced-motion preferences also pause it.

The playground illustrates fixed, ideal Bell, GHZ, and two-qubit Grover circuits.
It uses analytically specified probabilities and `Math.random()` to draw 1,024
browser samples. It does not execute Qiskit or submit QPU jobs. These illustrations
are not scientific receipts or hardware results. The Grover diagram groups its
phase oracle and diffusion operator into logical blocks.

The page includes keyboard-accessible tabs, native FAQ disclosures, a mobile
navigation menu, clipboard actions, and a global animation pause control.
Operating-system reduced-motion preferences disable animated effects.
