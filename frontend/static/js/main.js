// main.js — BeiSmart KE

// ── Theme toggle ───────────────────────────────────────────────────────────────
function initThemeToggle() {
    const html  = document.documentElement;
    const btn   = document.getElementById("theme-toggle");
    const icon  = document.getElementById("theme-icon");
    const label = document.getElementById("theme-label");
    if (!btn) return;

    function applyTheme(theme) {
        html.setAttribute("data-theme", theme);
        if (theme === "dark") {
            icon.textContent  = "🌙";
            if (label) label.textContent = "Dark";
        } else {
            icon.textContent  = "☀️";
            if (label) label.textContent = "Light";
        }
        localStorage.setItem("beismart-theme", theme);
    }

    applyTheme(localStorage.getItem("beismart-theme") || "dark");
    btn.addEventListener("click", () => {
        const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(next);
    });
}


// ── Live clock ─────────────────────────────────────────────────────────────────
function updateClock() {
    const el = document.getElementById("live-time");
    if (el) el.textContent = new Date().toLocaleTimeString("en-KE", {
        hour: "2-digit", minute: "2-digit", second: "2-digit"
    });
}
updateClock();
setInterval(updateClock, 1000);


// ── Toast ──────────────────────────────────────────────────────────────────────
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const icons = { success: "✓", error: "✕", info: "ℹ" };
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || "ℹ"}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}


// ── Animated counter ───────────────────────────────────────────────────────────
function animateCounter(el, target, prefix = "", suffix = "", duration = 900) {
    const isFloat   = String(target).includes(".");
    const start     = 0;
    const startTime = performance.now();
    const update    = (now) => {
        const elapsed  = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease     = 1 - Math.pow(1 - progress, 3);
        const current  = start + (target - start) * ease;
        el.textContent = prefix + (isFloat
            ? current.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })
            : Math.round(current).toLocaleString("en-KE")) + suffix;
        if (progress < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
}


// ── Skeleton loader ────────────────────────────────────────────────────────────
function showSkeletons(count = 5) {
    const cardView    = document.getElementById("card-view");
    const statsWrap   = document.getElementById("stats-wrap");
    const resultsWrap = document.getElementById("results-wrap");
    if (!cardView || !statsWrap || !resultsWrap) return;

    statsWrap.style.display = "grid";
    statsWrap.innerHTML = Array(4).fill(0).map(() => `
        <div class="stat-card">
            <div class="skel-card" style="width:36px;height:36px;border-radius:8px;flex-shrink:0;"></div>
            <div class="stat-info" style="gap:8px;">
                <div class="skel-card" style="width:80px;height:22px;"></div>
                <div class="skel-card" style="width:100px;height:10px;"></div>
            </div>
        </div>`).join("");

    resultsWrap.style.display = "block";
    cardView.innerHTML = `<div class="skeleton">${Array(count).fill(0).map(() =>
        `<div class="skel-card"></div>`).join("")}</div>`;
}


// ── Recent searches ────────────────────────────────────────────────────────────
const RECENT_KEY = "beismart-recent";
const MAX_RECENT = 6;

function getRecent() {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; }
    catch { return []; }
}

function saveRecent(query) {
    let recent = getRecent().filter(q => q.toLowerCase() !== query.toLowerCase());
    recent.unshift(query);
    if (recent.length > MAX_RECENT) recent = recent.slice(0, MAX_RECENT);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
}

function removeRecent(query) {
    const recent = getRecent().filter(q => q !== query);
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
}

function clearRecent() {
    localStorage.removeItem(RECENT_KEY);
}

function renderRecentDropdown(input) {
    const recent   = getRecent();
    const dropdown = document.getElementById("recent-dropdown");
    if (!dropdown) return;

    if (recent.length === 0) {
        dropdown.classList.remove("show");
        return;
    }

    dropdown.innerHTML = `
        <div class="recent-header">
            Recent Searches
            <button class="recent-clear" id="clear-recent">Clear all</button>
        </div>
        ${recent.map(q => `
        <div class="recent-item" data-query="${q}">
            <span class="recent-item-icon">🕐</span>
            <span>${q}</span>
            <button class="recent-item-remove" data-remove="${q}">✕</button>
        </div>`).join("")}
    `;
    dropdown.classList.add("show");

    // Click a recent item
    dropdown.querySelectorAll(".recent-item").forEach(item => {
        item.addEventListener("click", (e) => {
            if (e.target.classList.contains("recent-item-remove")) return;
            input.value = item.dataset.query;
            dropdown.classList.remove("show");
            document.getElementById("search-form").dispatchEvent(new Event("submit"));
        });
    });

    // Remove individual
    dropdown.querySelectorAll(".recent-item-remove").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            removeRecent(btn.dataset.remove);
            renderRecentDropdown(input);
        });
    });

    // Clear all
    document.getElementById("clear-recent")?.addEventListener("click", () => {
        clearRecent();
        dropdown.classList.remove("show");
    });
}

function initRecentSearches() {
    const input    = document.getElementById("search-input");
    const dropdown = document.getElementById("recent-dropdown");
    if (!input || !dropdown) return;

    input.addEventListener("focus", () => {
        if (input.value.trim() === "") renderRecentDropdown(input);
    });

    input.addEventListener("input", () => {
        if (input.value.trim() === "") renderRecentDropdown(input);
        else dropdown.classList.remove("show");
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".search-wrap")) dropdown.classList.remove("show");
    });
}


// ── Category selector ────────────────────────────────────────────────────────
let activeCategory = "all";

const CATEGORY_SITES = {
    all:         "Jumia, Avechi, Hotpoint, Quickmart, Kilimall, Amazon",
    electronics: "Jumia, Avechi, Hotpoint, Kilimall, Amazon",
    appliances:  "Jumia, Hotpoint, Avechi, Kilimall",
    food:        "Quickmart",
    fashion:     "Jumia, Kilimall",
    general:     "Jumia, Avechi, Kilimall",
};

function initCategoryBar() {
    const bar = document.getElementById("category-bar");
    if (!bar) return;
    bar.querySelectorAll(".cat-pill").forEach(btn => {
        btn.addEventListener("click", () => {
            bar.querySelectorAll(".cat-pill").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeCategory = btn.dataset.category;
            const hint = document.getElementById("category-sites");
            if (hint) hint.textContent = CATEGORY_SITES[activeCategory] || "All sites";
        });
    });
}


// ── Filter + sort bar ──────────────────────────────────────────────────────────
let allProducts  = [];
let activeFilter = "all";
let activeSort   = "default";

const SITES = ["Jumia","Avechi","Hotpoint","Quickmart","Kilimall","Carrefour","Amazon"];

function renderFilterBar(products) {
    const sitePills = SITES
        .filter(s => products.some(p => p.site === s))
        .map(s => `<button class="filter-pill" data-filter="${s}">${s} (${products.filter(p=>p.site===s).length})</button>`)
        .join("");

    return `
    <span class="filter-label">Filter:</span>
    <button class="filter-pill active" data-filter="all">All (${products.length})</button>
    ${sitePills}
    <div class="filter-divider"></div>
    <span class="filter-label">Sort:</span>
    <button class="filter-pill active" data-sort="default">Best Deal</button>
    <button class="filter-pill" data-sort="asc">Price ↑</button>
    <button class="filter-pill" data-sort="desc">Price ↓</button>`;
}

function applyFilterSort() {
    let filtered = [...allProducts];
    if (activeFilter !== "all") filtered = filtered.filter(p => p.site === activeFilter);
    if (activeSort === "asc")  filtered.sort((a, b) => a.price - b.price);
    if (activeSort === "desc") filtered.sort((a, b) => b.price - a.price);
    renderCards(filtered);
}

function initFilterBar() {
    const bar = document.getElementById("filter-sort-bar");
    if (!bar) return;

    bar.querySelectorAll("[data-filter]").forEach(btn => {
        btn.addEventListener("click", () => {
            bar.querySelectorAll("[data-filter]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeFilter = btn.dataset.filter;
            applyFilterSort();
        });
    });

    bar.querySelectorAll("[data-sort]").forEach(btn => {
        btn.addEventListener("click", () => {
            bar.querySelectorAll("[data-sort]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeSort = btn.dataset.sort;
            applyFilterSort();
        });
    });
}


// ── Price drop indicator ───────────────────────────────────────────────────────
async function fetchPriceDrops(query) {
    try {
        const res  = await fetch(`/api/history?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (!data.history || data.history.length === 0) return {};

        // For each site, find the previous price before the latest entry
        const bysite = {};
        data.history.forEach(r => {
            if (!bysite[r.site]) bysite[r.site] = [];
            bysite[r.site].push({ price: r.price, time: r.timestamp });
        });

        const drops = {};
        Object.entries(bysite).forEach(([site, entries]) => {
            if (entries.length >= 2) {
                const latest = entries[entries.length - 1].price;
                const prev   = entries[entries.length - 2].price;
                if (latest < prev) drops[site] = { latest, prev, diff: prev - latest };
            }
        });
        return drops;
    } catch { return {}; }
}


// ── Site badge helper ──────────────────────────────────────────────────────────
function siteBadgeClass(site) {
    const map = {
        Jumia: "badge-jumia", Avechi: "badge-avechi", Hotpoint: "badge-hotpoint",
        Quickmart: "badge-quickmart", Kilimall: "badge-kilimall",
        Carrefour: "badge-carrefour", Amazon: "badge-amazon"
    };
    return map[site] || "badge-jumia";
}

// ── Render cards ───────────────────────────────────────────────────────────────
function renderCards(products, drops = {}) {
    const cardView = document.getElementById("card-view");
    if (!products || products.length === 0) {
        cardView.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <div class="empty-title">No results</div>
                <div class="empty-sub">Try adjusting your filters.</div>
            </div>`;
        return;
    }

    const prices     = products.map(p => p.price);
    const minPrice   = Math.min(...prices);
    const maxPrice   = Math.max(...prices);
    const priceRange = maxPrice - minPrice || 1;

    cardView.innerHTML = products.map((p, i) => {
        const isCheapest = p.price === minPrice;
        const badgeClass = siteBadgeClass(p.site);
        const barPct     = Math.round(((p.price - minPrice) / priceRange) * 100);
        const bestTag    = isCheapest ? `<span class="best-deal-tag">★ Best Deal</span>` : "";
        const amazonNote = p.currency === "KSh*" ? `<span class="amazon-note">*converted from USD</span>` : "";

        const drop    = drops[p.site];
        const dropTag = drop ? `<span class="price-drop-tag">↓ KSh ${drop.diff.toLocaleString()} drop</span>` : "";

        const imgHTML = p.image_url
            ? `<img src="${p.image_url}" alt="${p.name}" class="card-img" onerror="this.style.display='none'" />`
            : `<div class="card-img-placeholder">🛒</div>`;

        return `
        <div class="product-card card-${p.site.toLowerCase()}">
            <div class="card-glow"></div>
            ${imgHTML}
            <div class="card-body">
                <div class="card-top">
                    <span class="site-badge ${badgeClass}">${p.site}</span>
                    ${bestTag}${dropTag}${amazonNote}
                </div>
                <div class="card-name">${p.name}</div>
                <div class="price-bar-wrap" style="max-width:180px;">
                    <div class="price-bar" style="width:${barPct}%"></div>
                </div>
            </div>
            <div class="card-price-wrap">
                <div class="card-price">KSh ${Number(p.price).toLocaleString()}</div>
                <div class="card-currency">${p.currency || "KSh"}</div>
                <a href="${p.url}" target="_blank" class="btn btn-ghost btn-sm" style="margin-top:10px;">View →</a>
            </div>
        </div>`;
    }).join("");
}


// ── Render products (full) ─────────────────────────────────────────────────────
async function renderProducts(products, query = "") {
    const cardView    = document.getElementById("card-view");
    const tableView   = document.getElementById("table-view");
    const statsWrap   = document.getElementById("stats-wrap");
    const resultsWrap = document.getElementById("results-wrap");

    if (!products || products.length === 0) {
        resultsWrap.innerHTML = `
            <div class="empty-state fade-in">
                <div class="empty-icon">🔍</div>
                <div class="empty-title">No results found</div>
                <div class="empty-sub">Try a different search term or check your spelling.</div>
            </div>`;
        statsWrap.style.display = "none";
        return;
    }

    allProducts  = products;
    activeFilter = "all";
    activeSort   = "default";

    const prices   = products.map(p => p.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const savings  = maxPrice - minPrice;

    // Animated stats
    statsWrap.style.display = "grid";
    statsWrap.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon">📦</div>
            <div class="stat-info">
                <div class="stat-value" id="stat-count">0</div>
                <div class="stat-label">Products Found</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-info">
                <div class="stat-value" id="stat-min">KSh 0</div>
                <div class="stat-label">Lowest Price</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📊</div>
            <div class="stat-info">
                <div class="stat-value" id="stat-max">KSh 0</div>
                <div class="stat-label">Highest Price</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-info">
                <div class="stat-value" id="stat-save">KSh 0</div>
                <div class="stat-label">Max Savings</div>
            </div>
        </div>
    `;

    // Run counters after DOM update
    setTimeout(() => {
        animateCounter(document.getElementById("stat-count"), products.length);
        animateCounter(document.getElementById("stat-min"),   minPrice, "KSh ");
        animateCounter(document.getElementById("stat-max"),   maxPrice, "KSh ");
        animateCounter(document.getElementById("stat-save"),  savings,  "KSh ");
    }, 50);

    // Fetch price drops
    const drops = query ? await fetchPriceDrops(query) : {};

    // Update results count
    const countEl = document.getElementById("results-count");
    if (countEl) countEl.textContent = `(${products.length})`;

    // Filter + sort bar
    resultsWrap.style.display = "block";
    const filterBarEl = document.getElementById("filter-sort-bar");
    if (filterBarEl) {
        filterBarEl.innerHTML = renderFilterBar(products);
        initFilterBar();
    }

    // Cards
    renderCards(products, drops);

    // Table
    tableView.innerHTML = `
        <div class="table-wrap">
            <table class="results-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Product Name</th>
                        <th>Site</th>
                        <th>Price</th>
                        <th>Link</th>
                    </tr>
                </thead>
                <tbody>
                    ${products.map((p, i) => `
                    <tr>
                        <td style="color:var(--text-3);font-family:'DM Mono',monospace;font-size:0.78rem;">${i + 1}</td>
                        <td>${p.name}</td>
                        <td><span class="site-badge ${siteBadgeClass(p.site)}">${p.site}</span></td>
                        <td class="td-price">KSh ${Number(p.price).toLocaleString()}</td>
                        <td><a href="${p.url}" target="_blank">View →</a></td>
                    </tr>`).join("")}
                </tbody>
            </table>
        </div>`;

    initViewToggle();
}


// ── View toggle ────────────────────────────────────────────────────────────────
function initViewToggle() {
    const cardBtn   = document.getElementById("toggle-card");
    const tableBtn  = document.getElementById("toggle-table");
    const cardView  = document.getElementById("card-view");
    const tableView = document.getElementById("table-view");
    if (!cardBtn || !tableBtn) return;

    cardBtn.addEventListener("click", () => {
        cardView.style.display  = "flex";
        tableView.style.display = "none";
        cardBtn.classList.add("active");
        tableBtn.classList.remove("active");
    });
    tableBtn.addEventListener("click", () => {
        cardView.style.display  = "none";
        tableView.style.display = "block";
        tableBtn.classList.add("active");
        cardBtn.classList.remove("active");
    });
}


// ── Search (SSE streaming) ──────────────────────────────────────────────────
let activeEventSource = null;
let streamProducts    = [];

function updateStatsBar() {
    const statsWrap = document.getElementById("stats-wrap");
    if (!statsWrap || streamProducts.length === 0) return;
    const prices   = streamProducts.map(p => p.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const savings  = maxPrice - minPrice;
    statsWrap.style.display = "grid";
    statsWrap.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon">📦</div>
            <div class="stat-info">
                <div class="stat-value" id="stat-count">${streamProducts.length}</div>
                <div class="stat-label">Products Found</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-info">
                <div class="stat-value">KSh ${minPrice.toLocaleString()}</div>
                <div class="stat-label">Lowest Price</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📊</div>
            <div class="stat-info">
                <div class="stat-value">KSh ${maxPrice.toLocaleString()}</div>
                <div class="stat-label">Highest Price</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-info">
                <div class="stat-value">KSh ${savings.toLocaleString()}</div>
                <div class="stat-label">Max Savings</div>
            </div>
        </div>`;
}

function buildCard(p, minPrice, maxPrice, isNew) {
    const priceRange = maxPrice - minPrice || 1;
    const isCheapest = p.price === minPrice;
    const badgeClass = siteBadgeClass(p.site);
    const barPct     = Math.round(((p.price - minPrice) / priceRange) * 100);
    const bestTag    = isCheapest ? `<span class="best-deal-tag">★ Best Deal</span>` : "";
    const amazonNote = (p.site === "Amazon" && p.currency === "KSh*") ? `<span class="amazon-note">*USD converted</span>` : "";
    const imgHTML    = p.image_url
        ? `<img src="${p.image_url}" alt="${p.name}" class="card-img" onerror="this.style.display='none'" />`
        : `<div class="card-img-placeholder">🛒</div>`;
    const card = document.createElement("div");
    card.className = `product-card card-${p.site.toLowerCase()}${isNew ? " stream-card-in" : ""}`;
    card.innerHTML = `
        <div class="card-glow"></div>
        ${imgHTML}
        <div class="card-body">
            <div class="card-top">
                <span class="site-badge ${badgeClass}">${p.site}</span>
                ${bestTag}${amazonNote}
            </div>
            <div class="card-name">${p.name}</div>
            <div class="price-bar-wrap" style="max-width:180px;">
                <div class="price-bar" style="width:${barPct}%"></div>
            </div>
        </div>
        <div class="card-price-wrap">
            <div class="card-price">KSh ${Number(p.price).toLocaleString()}</div>
            <div class="card-currency">${p.currency || "KSh"}</div>
            <a href="${p.url}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-sm" style="margin-top:10px;">View →</a>
        </div>`;
    if (isNew) setTimeout(() => card.classList.remove("stream-card-in"), 400);
    return card;
}

function renderStreamCards(newSiteNames) {
    const cardView = document.getElementById("card-view");
    if (!cardView) return;

    const skel = cardView.querySelector(".skeleton");
    if (skel) skel.remove();

    const sorted    = [...streamProducts].sort((a, b) => a.price - b.price);
    const minPrice  = sorted.length ? sorted[0].price : 0;
    const maxPrice  = sorted.length ? sorted[sorted.length - 1].price : 0;

    cardView.innerHTML = "";
    sorted.forEach(p => {
        const isNew = newSiteNames.has(p.site);
        cardView.appendChild(buildCard(p, minPrice, maxPrice, isNew));
    });

    const countEl = document.getElementById("results-count");
    if (countEl) countEl.textContent = `(${streamProducts.length})`;

    allProducts = [...sorted];
    const filterBarEl = document.getElementById("filter-sort-bar");
    if (filterBarEl) {
        filterBarEl.innerHTML = renderFilterBar(streamProducts);
        initFilterBar();
    }
}

function initSearch() {
    const form  = document.getElementById("search-form");
    const input = document.getElementById("search-input");
    if (!form || !input) return;

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const query = input.value.trim();
        if (!query) return;

        if (activeEventSource) { activeEventSource.close(); activeEventSource = null; }
        streamProducts = [];

        document.getElementById("results-wrap")?.style && (document.getElementById("results-wrap").style.display = "none");
        document.getElementById("stats-wrap")?.style    && (document.getElementById("stats-wrap").style.display   = "none");
        document.getElementById("recent-dropdown")?.classList.remove("show");
        document.getElementById("empty-state") && (document.getElementById("empty-state").style.display = "none");

        showSkeletons(6);

        const resultsWrap = document.getElementById("results-wrap");
        const cardView    = document.getElementById("card-view");
        if (resultsWrap) {
            resultsWrap.style.display = "block";
            const sectionHeader = resultsWrap.querySelector(".section-header");
            if (sectionHeader) sectionHeader.style.display = "flex";
        }

        const url = `/api/search/stream?q=${encodeURIComponent(query)}&category=${activeCategory}`;
        const es  = new EventSource(url);
        activeEventSource = es;

        es.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.event === "chunk" && data.products.length > 0) {
                streamProducts.push(...data.products);
                renderStreamCards(new Set([data.site]));
                updateStatsBar();
                showToast(`${data.site}: ${data.count} product${data.count !== 1 ? "s" : ""} found`, "info");
            }

            if (data.event === "done") {
                es.close();
                activeEventSource = null;
                saveRecent(query);
                const wlQuery = document.getElementById("wl-query");
                if (wlQuery) wlQuery.value = query;
                if (streamProducts.length === 0) {
                    if (cardView) cardView.innerHTML = `
                        <div class="empty-state fade-in">
                            <div class="empty-icon">🔍</div>
                            <div class="empty-title">No results found</div>
                            <div class="empty-sub">Try a different search term.</div>
                        </div>`;
                    document.getElementById("stats-wrap").style.display = "none";
                }
            }
        };

        es.onerror = () => {
            es.close();
            activeEventSource = null;
            if (cardView && streamProducts.length === 0) {
                cardView.innerHTML = `
                    <div class="alert-box fade-in" style="grid-column:1/-1;">
                        <strong style="color:var(--orange);">Error:</strong>
                        <span style="color:var(--text-muted);margin-left:8px;">Search failed — please try again.</span>
                    </div>`;
            }
        };
    });

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") form.dispatchEvent(new Event("submit"));
    });
}


// ── Price history chart ────────────────────────────────────────────────────────
function initHistory() {
    const form  = document.getElementById("history-form");
    const input = document.getElementById("history-input");
    if (!form || !input) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const query = input.value.trim();
        if (!query) return;

        const wrap = document.getElementById("history-wrap");
        wrap.style.display = "none";

        const loader = document.getElementById("history-loader");
        if (loader) loader.classList.add("show");

        try {
            const res  = await fetch(`/api/history?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            if (!data.history || data.history.length === 0) {
                wrap.innerHTML = `
                    <div class="alert-box info fade-in">
                        <span style="color:var(--cyan);">No history found for "<strong>${query}</strong>". Search for it first.</span>
                    </div>`;
                wrap.style.display = "block";
                return;
            }

            renderHistoryChart(data.history, query);
            wrap.style.display = "block";

        } catch (err) {
            wrap.innerHTML = `<div class="alert-box fade-in"><span style="color:var(--orange);">${err.message}</span></div>`;
            wrap.style.display = "block";
        } finally {
            if (loader) loader.classList.remove("show");
        }
    });
}


function renderHistoryChart(history, query) {
    const wrap = document.getElementById("history-wrap");
    const sites = {};
    history.forEach(r => {
        if (!sites[r.site]) sites[r.site] = [];
        sites[r.site].push({ x: r.timestamp, y: r.price });
    });

    const colors = {
        Jumia: "#f97316", Avechi: "#22d3ee", Hotpoint: "#ef4444",
        Quickmart: "#e3000b", Kilimall: "#f59e0b", Carrefour: "#3b82f6", Amazon: "#ff9900"
    };
    const datasets = Object.entries(sites).map(([site, points]) => ({
        label: site,
        data: points,
        borderColor: colors[site] || "#ea580c",
        backgroundColor: `${colors[site] || "#ea580c"}14`,
        borderWidth: 2.5,
        pointRadius: 5,
        pointHoverRadius: 7,
        pointBackgroundColor: colors[site] || "#ea580c",
        pointBorderColor: "#0c0c14",
        pointBorderWidth: 2,
        tension: 0.3,
        fill: true,
    }));

    wrap.innerHTML = `
        <div class="chart-card">
            <div class="chart-title">Price History — <span style="color:var(--accent);">${query}</span></div>
            <div class="chart-container">
                <canvas id="history-chart"></canvas>
            </div>
        </div>
        <div id="history-summary"></div>`;

    const ctx = document.getElementById("history-chart").getContext("2d");
    new Chart(ctx, {
        type: "line",
        data: { datasets },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            parsing: { xAxisKey: "x", yAxisKey: "y" },
            plugins: {
                legend: { labels: { color: "#6b7280", font: { family: "DM Sans", size: 12 }, usePointStyle: true } },
                tooltip: {
                    backgroundColor: "rgba(12,12,20,0.95)",
                    borderColor: "rgba(255,255,255,0.08)",
                    borderWidth: 1,
                    titleColor: "#e2e8f0",
                    bodyColor: "#9ca3af",
                    padding: 12,
                    callbacks: { label: ctx => ` ${ctx.dataset.label}: KSh ${Number(ctx.parsed.y).toLocaleString()}` }
                }
            },
            scales: {
                x: {
                    type: "category",
                    ticks: { color: "#374151", font: { family: "DM Mono", size: 10 }, maxRotation: 30 },
                    grid: { color: "rgba(255,255,255,0.04)" },
                    border: { color: "rgba(255,255,255,0.06)" }
                },
                y: {
                    ticks: { color: "#374151", font: { family: "DM Mono", size: 10 }, callback: v => `KSh ${Number(v).toLocaleString()}` },
                    grid: { color: "rgba(255,255,255,0.04)" },
                    border: { color: "rgba(255,255,255,0.06)" }
                }
            }
        }
    });

    const summary = {};
    history.forEach(r => {
        if (!summary[r.site]) summary[r.site] = [];
        summary[r.site].push(r.price);
    });

    const rows = Object.entries(summary).map(([site, prices]) => {
        const min = Math.min(...prices);
        const max = Math.max(...prices);
        const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
        return `<tr>
            <td><span class="site-badge ${siteBadgeClass(site)}">${site}</span></td>
            <td class="td-price">KSh ${min.toLocaleString()}</td>
            <td class="td-price">KSh ${max.toLocaleString()}</td>
            <td class="td-price">KSh ${Math.round(avg).toLocaleString()}</td>
            <td style="color:var(--text-3);font-family:'DM Mono',monospace;font-size:0.8rem;">${prices.length}</td>
        </tr>`;
    }).join("");

    document.getElementById("history-summary").innerHTML = `
        <div class="table-wrap" style="margin-top:16px;">
            <table class="results-table">
                <thead><tr><th>Site</th><th>Lowest</th><th>Highest</th><th>Average</th><th>Records</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}


// ── Watchlist ──────────────────────────────────────────────────────────────────
async function loadWatchlist() {
    const wrap = document.getElementById("watchlist-wrap");
    if (!wrap) return;
    try {
        const res  = await fetch("/api/watchlist");
        const data = await res.json();
        renderWatchlist(data.watchlist || []);
    } catch (err) {
        wrap.innerHTML = `<div class="alert-box"><span style="color:var(--orange);">${err.message}</span></div>`;
    }
}

function renderWatchlist(items) {
    const wrap = document.getElementById("watchlist-wrap");
    if (!wrap) return;
    if (items.length === 0) {
        wrap.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔔</div>
                <div class="empty-title">No items yet</div>
                <div class="empty-sub">Add a product above to start monitoring prices.</div>
            </div>`;
        return;
    }
    wrap.innerHTML = `
        <div class="watchlist-table-wrap">
            <table class="watchlist-table">
                <thead>
                    <tr><th>Product</th><th>Alert Below</th><th>Email</th><th>Added</th><th></th></tr>
                </thead>
                <tbody>
                    ${items.map(item => `
                    <tr>
                        <td class="wl-query">${item.query}</td>
                        <td class="wl-threshold">KSh ${Number(item.alert_threshold).toLocaleString()}</td>
                        <td class="wl-email">${item.email}</td>
                        <td class="wl-date">${String(item.created_at).slice(0,10)}</td>
                        <td><button class="btn btn-danger" onclick="deleteWatchlistItem(${item.id})">Remove</button></td>
                    </tr>`).join("")}
                </tbody>
            </table>
        </div>`;
}

async function deleteWatchlistItem(id) {
    try {
        const res = await fetch(`/api/watchlist/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        showToast("Item removed from watchlist");
        loadWatchlist();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function initWatchlistForm() {
    const form = document.getElementById("watchlist-form");
    if (!form) return;
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const query     = document.getElementById("wl-query").value.trim();
        const threshold = document.getElementById("wl-threshold").value;
        const email     = document.getElementById("wl-email").value.trim();
        if (!query || !email) { showToast("Please fill in all fields", "error"); return; }
        try {
            const res  = await fetch("/api/watchlist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, threshold: parseFloat(threshold), email })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            showToast(`✓ "${query}" added to watchlist`);
            form.reset();
            loadWatchlist();
        } catch (err) {
            showToast(err.message, "error");
        }
    });
}

function initPriceCheck() {
    const btn = document.getElementById("price-check-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
        btn.disabled    = true;
        btn.textContent = "Checking…";
        const loader = document.getElementById("check-loader");
        if (loader) loader.classList.add("show");
        try {
            const res  = await fetch("/api/check-prices", { method: "POST" });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            showToast("Price check triggered successfully");
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            btn.disabled    = false;
            btn.textContent = "⚡ Run Check Now";
            if (loader) loader.classList.remove("show");
        }
    });
}


// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initThemeToggle();
    initCategoryBar();
    initSearch();
    initRecentSearches();
    initHistory();
    initWatchlistForm();
    initPriceCheck();
    loadWatchlist();
    initViewToggle();
});