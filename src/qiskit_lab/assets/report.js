/* Progressive enhancement: the static report remains readable without JavaScript. */
"use strict";
(() => {
  const publications = JSON.parse(document.getElementById("report-data").textContent);
  document.documentElement.classList.add("js");
  const number = new Intl.NumberFormat("en-US");
  const svgNS = "http://www.w3.org/2000/svg";
  function element(name, attributes, text) {
    const node = document.createElementNS(svgNS, name);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  document.querySelectorAll(".publication").forEach((section, index) => {
    const all = Object.entries(publications[index]).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    const total = all.reduce((sum, entry) => sum + entry[1], 0);
    const filter = section.querySelector(".state-filter");
    const mode = section.querySelector(".chart-mode");
    const previous = section.querySelector(".previous");
    const next = section.querySelector(".next");
    let page = 0;
    function draw() {
      const matches = all.filter(entry => entry[0].includes(filter.value.trim()));
      const pageCount = Math.max(1, Math.ceil(matches.length / 50));
      page = Math.max(0, Math.min(page, pageCount - 1));
      const tbody = section.querySelector("tbody");
      tbody.replaceChildren();
      for (const [state, count] of matches.slice(page * 50, page * 50 + 50)) {
        const row = document.createElement("tr");
        for (const value of [state, number.format(count), `${(count / (total || 1) * 100).toFixed(4)}%`]) {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.appendChild(cell);
        }
        tbody.appendChild(row);
      }
      if (!matches.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 3;
        cell.textContent = "No matching observed states.";
        row.appendChild(cell);
        tbody.appendChild(row);
      }
      section.querySelector(".page-info").textContent = `${number.format(matches.length)} states · Page ${page + 1} of ${pageCount}`;
      previous.disabled = page === 0;
      next.disabled = page + 1 >= pageCount;
      const svg = section.querySelector("svg");
      const top = matches.slice(0, 16);
      const height = Math.max(130, top.length * 32 + 38);
      svg.setAttribute("viewBox", `0 0 800 ${height}`);
      svg.replaceChildren(element("title", {}, "Observed measurement distribution"));
      svg.appendChild(element("line", {x1: 150, y1: 8, x2: 150, y2: height - 25, class: "axis"}));
      const isProbability = mode.value === "probability";
      const maximum = isProbability ? total || 1 : Math.max(1, ...top.map(entry => entry[1]));
      top.forEach(([state, count], i) => {
        const y = i * 32 + 12;
        const width = count / maximum * 530;
        const short = state.length > 18 ? `${state.slice(0, 7)}…${state.slice(-7)}` : state;
        svg.appendChild(element("text", {x: 134, y: y + 17, "text-anchor": "end"}, short));
        const bar = element("rect", {x: 151, y, width, height: 24, class: "bar"});
        bar.appendChild(element("title", {}, `${state}: ${number.format(count)} shots (${(count / (total || 1) * 100).toFixed(2)}%)`));
        svg.appendChild(bar);
        svg.appendChild(element("text", {x: Math.min(700, width + 161), y: y + 17},
          isProbability ? `${(count / (total || 1) * 100).toFixed(2)}%` : number.format(count)));
      });
      svg.appendChild(element("text", {x: 150, y: height - 4, class: "axis-label"},
        `${isProbability ? "Probability" : "Counts (axis scales to largest count)"} · top 16 observed states`));
    }
    filter.addEventListener("input", () => { page = 0; draw(); });
    mode.addEventListener("change", draw);
    previous.addEventListener("click", () => { page -= 1; draw(); });
    next.addEventListener("click", () => { page += 1; draw(); });
    draw();
  });
})();
