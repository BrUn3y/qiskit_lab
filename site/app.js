/* The playground illustrates fixed ideal circuits; it does not call Qiskit or a QPU. */
"use strict";

const examples = {
  bell: {
    label: "ENTANGLEMENT / 2 QUBITS",
    title: "Two qubits. One shared state.",
    description:
      "A Hadamard gate creates a superposition. A controlled-X gate entangles the qubits. Measure them and their outcomes agree.",
    formula: "(|00〉 + |11〉) / √2",
    qubits: 2,
    gates: 2,
    probabilities: [0.5, 0, 0, 0.5],
    aria: "Bell circuit: Hadamard on qubit zero followed by controlled-X from qubit zero to qubit one",
    draw: () => gate(125, 45, "H", true) + control(235, 45, 110),
  },
  ghz: {
    label: "ENTANGLEMENT / 3 QUBITS",
    title: "Three qubits. Connected outcomes.",
    description:
      "Extend the Bell-state idea with a second controlled-X gate. In the ideal GHZ state, all three measured bits agree.",
    formula: "(|000〉 + |111〉) / √2",
    qubits: 3,
    gates: 3,
    probabilities: [0.5, 0, 0, 0, 0, 0, 0, 0.5],
    aria: "GHZ circuit: Hadamard on qubit zero, controlled-X from zero to one, then controlled-X from one to two",
    draw: () =>
      gate(120, 45, "H", true) + control(205, 45, 100) + control(280, 100, 155),
  },
  grover: {
    label: "AMPLITUDE AMPLIFICATION / 2 QUBITS",
    title: "One marked state. A focused search.",
    description:
      "For a two-qubit search with the marked state 11, one Grover iteration amplifies that state to probability one in the ideal case.",
    formula: "P(|11〉) = 1",
    qubits: 2,
    gates: "3 BLOCKS",
    probabilities: [0, 0, 0, 1],
    aria: "Grover circuit in logical blocks: Hadamard on both qubits, phase oracle marking eleven, then the diffusion operator",
    draw: () =>
      gate(108, 45, "H", true) +
      gate(108, 110, "H", true) +
      block(170, 23, 57, 110, "O₁₁") +
      block(252, 23, 57, 110, "D"),
  },
};

const byId = (id) => document.getElementById(id);
let current = "bell";
const gate = (x, y, label, accent = false) =>
  `<rect x="${x - 17}" y="${y - 17}" width="34" height="34" fill="${accent ? "#ff5b21" : "#1c1e19"}" stroke="${accent ? "#ff5b21" : "#b2b5a8"}"/><text x="${x}" y="${y + 5}" text-anchor="middle" fill="${accent ? "#1c1e19" : "#f2f2ec"}" font-family="PlexMono,monospace" font-size="15">${label}</text>`;
const control = (x, from, to) =>
  `<path d="M${x} ${from}V${to}" stroke="#f2f2ec"/><circle cx="${x}" cy="${from}" r="4" fill="#f2f2ec"/><circle cx="${x}" cy="${to}" r="13" fill="#1c1e19" stroke="#f2f2ec"/><path d="M${x - 13} ${to}h26M${x} ${to - 13}v26" stroke="#f2f2ec"/>`;
const block = (x, y, width, height, label) =>
  `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="#1c1e19" stroke="#b2b5a8"/><text x="${x + width / 2}" y="${y + height / 2 + 5}" text-anchor="middle" fill="#f2f2ec" font-family="PlexMono,monospace" font-size="15">${label}</text>`;

function drawCircuit(example) {
  const ys = example.qubits === 3 ? [45, 100, 155] : [45, 110];
  const lines = ys
    .map(
      (y, i) =>
        `<text x="8" y="${y + 4}" fill="#b2b5a8" font-family="PlexMono,monospace" font-size="12">q${i} |0〉</text><path d="M70 ${y}H365" stroke="#8b8e81"/><rect x="343" y="${y - 14}" width="28" height="28" fill="#1c1e19" stroke="#8b8e81"/><path d="M348 ${y + 5}a9 9 0 0 1 18 0m-9 0 6-10" fill="none" stroke="#f2f2ec"/>`,
    )
    .join("");
  byId("circuit-diagram").innerHTML =
    `<svg viewBox="0 0 395 ${example.qubits === 3 ? 195 : 155}" aria-hidden="true">${lines}${example.draw()}</svg>`;
  byId("circuit-diagram").setAttribute("aria-label", example.aria);
}

function drawDistribution(counts = null) {
  const example = examples[current];
  const total = counts ? counts.reduce((sum, n) => sum + n, 0) : 1;
  const values = counts || example.probabilities;
  const max = Math.max(...values) || 1;
  byId("distribution").innerHTML = values
    .map((value, i) => {
      const state = i.toString(2).padStart(example.qubits, "0");
      const label = counts
        ? `${value}`
        : `${Math.round((value / total) * 100)}%`;
      return `<div class="histogram-column" aria-label="State ${state}: ${label}${counts ? " shots" : ""}"><span class="histogram-value">${label}</span><div class="bar" style="--bar-height:${Math.max(0.7, (value / max) * 70)}%"></div><span class="histogram-state">${state}</span></div>`;
    })
    .join("");
  byId("distribution-label").textContent = counts
    ? "BROWSER SAMPLES / COUNTS"
    : "IDEAL PROBABILITIES";
  byId("sample-total").textContent = counts ? "1,024 SHOTS" : "THEORY";
  byId("distribution").setAttribute(
    "aria-label",
    counts
      ? "Browser-sampled measurement counts, 1,024 total shots"
      : "Ideal measurement probabilities",
  );
}

function chooseExample(name) {
  current = name;
  const example = examples[name];
  document.querySelectorAll(".experiment-tab").forEach((tab) => {
    const selected = tab.dataset.circuit === name;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    tab.classList.toggle("active", selected);
  });
  byId("experiment-panel").setAttribute("aria-labelledby", `tab-${name}`);
  ["label", "title", "description", "formula"].forEach((key) => {
    byId(`experiment-${key}`).textContent = example[key];
  });
  byId("gate-count").textContent =
    typeof example.gates === "number"
      ? `${example.gates} GATES`
      : example.gates;
  byId("experiment-status").textContent =
    "Browser illustration · ideal theory · no QPU connection";
  drawCircuit(example);
  drawDistribution();
}

document
  .querySelectorAll(".experiment-tab")
  .forEach((tab) =>
    tab.addEventListener("click", () => chooseExample(tab.dataset.circuit)),
  );
byId("sample-button").addEventListener("click", () => {
  const probabilities = examples[current].probabilities;
  const counts = probabilities.map(() => 0);
  for (let shot = 0; shot < 1024; shot++) {
    const value = Math.random();
    let cumulative = 0;
    for (let state = 0; state < probabilities.length; state++) {
      cumulative += probabilities[state];
      if (value < cumulative) {
        counts[state]++;
        break;
      }
    }
  }
  drawDistribution(counts);
  byId("experiment-status").textContent =
    "1,024 browser samples complete · ideal model · no Qiskit or QPU execution";
});
byId("reset-button").addEventListener("click", () => chooseExample(current));

document.querySelectorAll(".setup-tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    const name = tab.dataset.setup;
    document.querySelectorAll(".setup-tab").forEach((item) => {
      const selected = item === tab;
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
      item.classList.toggle("active", selected);
    });
    byId("setup-dam").hidden = name !== "dam";
    byId("setup-local").hidden = name !== "local";
    const walkthrough = byId("setup-walkthrough");
    if (walkthrough) walkthrough.hidden = name !== "dam";
    updateWalkthrough();
    byId("start-requirements").textContent =
      name === "dam"
        ? "A DAM account. Your curiosity. That’s a start."
        : "GIT / PYTHON 3.11–3.13 / UV";
    byId("copy-status").textContent = "";
  }),
);

// Keep tabs operable with the standard arrow, Home, and End keys.
document.querySelectorAll('[role="tablist"]').forEach((list) =>
  list.addEventListener("keydown", (event) => {
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const index = tabs.indexOf(document.activeElement);
    if (index < 0) return;
    let next;
    if (event.key === "ArrowRight" || event.key === "ArrowDown")
      next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp")
      next = (index + tabs.length - 1) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next !== undefined) {
      event.preventDefault();
      tabs[next].click();
      tabs[next].focus();
    }
  }),
);

document.querySelectorAll("[data-copy]").forEach((button) =>
  button.addEventListener("click", async () => {
    const text = byId(button.dataset.copy).textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
      byId("copy-status").textContent = "Installation commands copied.";
      button.textContent = "COPIED ✓";
      window.setTimeout(() => {
        button.textContent = "COPY ↗";
      }, 2200);
    } catch {
      byId("copy-status").textContent =
        "Select and copy the text above using your keyboard or device menu.";
    }
  }),
);

const menuButton = document.querySelector(".menu-toggle");
function closeMenu() {
  menuButton.setAttribute("aria-expanded", "false");
  byId("mobile-nav").hidden = true;
}
menuButton.addEventListener("click", () => {
  const open = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", String(open));
  byId("mobile-nav").hidden = !open;
});
document
  .querySelectorAll("#mobile-nav a")
  .forEach((link) => link.addEventListener("click", closeMenu));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !byId("mobile-nav").hidden) {
    closeMenu();
    menuButton.focus();
  }
});
window.matchMedia("(min-width: 901px)").addEventListener("change", (event) => {
  if (event.matches) closeMenu();
});

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let paused = reducedMotion.matches;
let walkthroughPaused = false;
function updateWalkthrough() {
  const still = paused || walkthroughPaused;
  const illustration = byId("walkthrough-image");
  const controls = byId("walkthrough-toggle");
  const walkthrough = byId("setup-walkthrough");
  if (!illustration || !controls || !walkthrough) return;
  const source =
    still || walkthrough.hidden
      ? illustration.dataset.poster
      : illustration.dataset.animation;
  if (illustration.getAttribute("src") !== source) illustration.src = source;
  controls.setAttribute("aria-pressed", String(still));
  controls.textContent = still ? "Play GIF ▷" : "Pause GIF Ⅱ";
}
byId("walkthrough-toggle")?.addEventListener("click", () => {
  if (paused) {
    paused = false;
    walkthroughPaused = false;
    updateMotion();
  } else {
    walkthroughPaused = !walkthroughPaused;
    updateWalkthrough();
  }
});
function updateMotion() {
  document.documentElement.classList.toggle("motion-paused", paused);
  byId("motion-toggle").setAttribute("aria-pressed", String(paused));
  byId("motion-toggle").setAttribute(
    "aria-label",
    paused ? "Resume animations" : "Pause animations",
  );
  byId("motion-toggle").textContent = paused ? "▷" : "Ⅱ";
  updateWalkthrough();
}
byId("motion-toggle").addEventListener("click", () => {
  paused = !paused;
  updateMotion();
});
reducedMotion.addEventListener("change", (event) => {
  paused = event.matches;
  updateMotion();
});
if ("IntersectionObserver" in window && !reducedMotion.matches) {
  document.documentElement.classList.add("js-motion");
  const observer = new IntersectionObserver(
    (entries) =>
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      }),
    { threshold: 0.08 },
  );
  document
    .querySelectorAll(".reveal")
    .forEach((element) => observer.observe(element));
}
byId("year").textContent = new Date().getFullYear();
updateMotion();
chooseExample("bell");
