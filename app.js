const currencies = { USD: "$", EUR: "€", GBP: "£", INR: "₹", JPY: "¥", AUD: "A$", CAD: "C$", CHF: "Fr", CNY: "¥", SGD: "S$" };
const $ = (id) => document.getElementById(id);
let rates = {};
const api = async (url, options) => (await fetch(url, options)).json();

function fillCurrencies() {
  for (const id of ["source", "target"]) Object.entries(currencies).forEach(([code]) => $(id).add(new Option(`${code} · ${currencyName(code)}`, code)));
  $("source").value = "USD"; $("target").value = "EUR";
}
function currencyName(code) { return ({ USD: "US Dollar", EUR: "Euro", GBP: "British Pound", INR: "Indian Rupee", JPY: "Japanese Yen", AUD: "Australian Dollar", CAD: "Canadian Dollar", CHF: "Swiss Franc", CNY: "Chinese Yuan", SGD: "Singapore Dollar" })[code]; }
async function loadRates() {
  const source = $("source").value;
  const response = await api(`/api/rates?base=${source}`);
  rates = response.rates;
  $("source-symbol").textContent = currencies[source];
  $("budget-symbol").textContent = currencies[source];
  convert();
}
async function convert() {
  const source = $("source").value, target = $("target").value, amount = Number($("amount").value) || 0;
  const value = amount * (rates[target] || 0);
  $("result-label").textContent = `${amount.toLocaleString()} ${source} equals`;
  $("result").textContent = `${currencies[target]}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${target}`;
  $("trend-pair").textContent = `${source} / ${target}`;
  await api("/api/conversions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source, target, amount, result: value }) });
  loadHistory(source, target);
  if ($("travel-toggle").checked) renderBudget();
}
async function loadHistory(source, target) {
  const response = await api(`/api/history?source=${source}&target=${target}`);
  if (!response.points || response.points.length < 2) {
    $("chart").innerHTML = "";
    $("trend-change").textContent = "Unavailable";
    return;
  }
  const points = response.points;
  const min = Math.min(...points.map((p) => p.rate)), max = Math.max(...points.map((p) => p.rate));
  const coordinates = points.map((point, i) => `${(i / (points.length - 1)) * 900},${205 - ((point.rate - min) / ((max - min) || 1)) * 170}`).join(" ");
  $("chart").innerHTML = `<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c8f2de" stop-opacity=".8"/><stop offset="1" stop-color="#c8f2de" stop-opacity="0"/></linearGradient></defs><line class="chart-grid" x1="0" y1="35" x2="900" y2="35"/><line class="chart-grid" x1="0" y1="120" x2="900" y2="120"/><line class="chart-grid" x1="0" y1="205" x2="900" y2="205"/><polygon class="chart-area" points="0,205 ${coordinates} 900,205"/><polyline class="chart-line" points="${coordinates}"/>`;
  $("trend-change").textContent = `${(((points.at(-1).rate / points[0].rate) - 1) * 100).toFixed(2)}%`;
}
async function loadFavorites() {
  const data = await api("/api/favorites");
  $("favorites").innerHTML = data.favorites.length ? data.favorites.map((favorite) => `<div class="favorite" data-source="${favorite.source}" data-target="${favorite.target}"><div><strong>${favorite.source} → ${favorite.target}</strong><small>${currencyName(favorite.source)} to ${currencyName(favorite.target)}</small></div><button aria-label="Remove favorite">×</button></div>`).join("") : `<div class="empty">No favorites yet. Add your go-to pairs.</div>`;
  document.querySelectorAll(".favorite").forEach((item) => {
    item.onclick = (event) => { if (event.target.tagName === "BUTTON") return; $("source").value = item.dataset.source; $("target").value = item.dataset.target; loadRates(); };
    item.querySelector("button").onclick = async () => { await api(`/api/favorites?source=${item.dataset.source}&target=${item.dataset.target}`, { method: "DELETE" }); loadFavorites(); };
  });
}
function renderBudget() {
  const source = $("source").value, amount = Number($("budget").value) || 0;
  const major = ["EUR", "USD", "GBP", "JPY", "AUD"];
  $("budget-table").innerHTML = major.map((code) => `<div class="budget-cell"><b>${code}</b><strong>${currencies[code]}${(amount * (rates[code] || 1)).toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong><small>from ${amount.toLocaleString()} ${source}</small></div>`).join("");
}
fillCurrencies(); loadRates(); loadFavorites();
$("source").onchange = loadRates; $("target").onchange = convert; $("amount").oninput = convert; $("convert").onclick = convert;
$("swap").onclick = () => { [$("source").value, $("target").value] = [$("target").value, $("source").value]; loadRates(); };
$("add-favorite").onclick = async () => { await api("/api/favorites", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: $("source").value, target: $("target").value }) }); loadFavorites(); };
$("travel-toggle").onchange = (event) => { $("budget-panel").classList.toggle("visible", event.target.checked); if (event.target.checked) renderBudget(); };
$("budget").oninput = renderBudget;
