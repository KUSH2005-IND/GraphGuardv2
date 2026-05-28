/**
 * GraphGuard v2 — Dashboard Application
 * Real-time transaction monitoring, graph visualization, and investigation flow.
 */

// ── State ────────────────────────────────────────────────────────────
const state = {
    ws: null,
    network: null,
    selectedAlert: null,
    feedItems: [],
    maxFeedItems: 100,
    txCount: 0,
    reconnectAttempts: 0,
    maxReconnect: 10,
};

// ── DOM References ───────────────────────────────────────────────────
const dom = {
    loading: document.getElementById('loadingOverlay'),
    feedBody: document.getElementById('feedBody'),
    feedCount: document.getElementById('feedCount'),
    alertBody: document.getElementById('alertBody'),
    alertCount: document.getElementById('alertCount'),
    graphCanvas: document.getElementById('graphCanvas'),
    graphPlaceholder: document.getElementById('graphPlaceholder'),
    graphInfo: document.getElementById('graphInfo'),
    invPanel: document.getElementById('investigationPanel'),
    invContent: document.getElementById('invContent'),
    invClose: document.getElementById('invClose'),
    statProcessed: document.getElementById('statProcessed'),
    statAlerts: document.getElementById('statAlerts'),
    statAccounts: document.getElementById('statAccounts'),
};

// ── Initialize ───────────────────────────────────────────────────────
async function init() {
    console.log('[GraphGuard] Initializing...');

    // Wait for backend
    let ready = false;
    while (!ready) {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            ready = data.ready;
        } catch (e) { /* retry */ }
        if (!ready) await sleep(1000);
    }

    if (dom.loading) dom.loading.style.display = 'none';

    // Load initial data
    await loadStats();
    await loadAlerts();

    // Start WebSocket
    connectWebSocket();

    // Setup event listeners
    if (dom.invClose) {
        dom.invClose.addEventListener('click', (e) => {
            e.stopPropagation();
            togglePanel(false);
        });
    }

    // Mouse Tracker
    document.addEventListener('mousemove', (e) => {
        const glow = document.getElementById('cursor-glow');
        if (glow) {
            glow.style.left = e.clientX + 'px';
            glow.style.top = e.clientY + 'px';
        }
    });

    console.log('[GraphGuard] Ready.');
}

// ── Toggle Panel Function (Stitch UI) ────────────────────────────────
function togglePanel(forceOpen = null) {
    const panel = dom.invPanel;
    if (!panel) return;
    
    const isCollapsed = panel.classList.contains('translate-y-[160px]');
    const shouldOpen = forceOpen !== null ? forceOpen : isCollapsed;
    
    if (shouldOpen) {
        panel.style.display = 'flex';
        setTimeout(() => {
            panel.classList.remove('translate-y-[160px]');
        }, 10);
        triggerChartAnimations();
    } else {
        panel.classList.add('translate-y-[160px]');
        setTimeout(() => {
            panel.style.display = 'none';
        }, 300);
    }
}

// Make it global so HTML onclick can reach it
window.togglePanel = togglePanel;

// ── API Calls ────────────────────────────────────────────────────────
async function loadStats() {
    try {
        const res = await fetch('/api/stats', { headers: { 'X-API-Key': 'GG-SECRET-KEY-2026' } });
        const data = await res.json();
        
        if (dom.statAccounts) animateCounter(dom.statAccounts, data.total_accounts || 0);
        if (dom.statAlerts) animateCounter(dom.statAlerts, data.risk_stats?.total_alerts || 0);
    } catch (e) {
        console.error('[Stats]', e);
    }
}

async function loadAlerts() {
    try {
        const res = await fetch('/api/alerts', { headers: { 'X-API-Key': 'GG-SECRET-KEY-2026' } });
        const alerts = await res.json();
        renderAlerts(alerts);
        if (dom.alertCount) dom.alertCount.textContent = alerts.length;
        if (dom.statAlerts) animateCounter(dom.statAlerts, alerts.length);
    } catch (e) {
        console.error('[Alerts]', e);
    }
}

async function loadGraph(accountId) {
    try {
        if (dom.graphInfo) dom.graphInfo.textContent = `Loading ${escapeHtml(accountId)}...`;
        const res = await fetch(`/api/graph/${accountId}`, { headers: { 'X-API-Key': 'GG-SECRET-KEY-2026' } });
        const graph = await res.json();
        if (dom.graphPlaceholder) dom.graphPlaceholder.style.display = 'none';
        renderGraph(graph, accountId);
        if (dom.graphInfo) dom.graphInfo.textContent = `${escapeHtml(accountId)} — ${graph.nodes?.length || 0} nodes, ${graph.edges?.length || 0} edges`;
    } catch (e) {
        console.error('[Graph]', e);
        if (dom.graphInfo) dom.graphInfo.textContent = 'Error loading graph';
        if (dom.graphPlaceholder) dom.graphPlaceholder.style.display = 'flex';
    }
}

async function loadInvestigation(accountId) {
    try {
        const res = await fetch(`/api/investigation/${accountId}`, { headers: { 'X-API-Key': 'GG-SECRET-KEY-2026' } });
        const inv = await res.json();
        renderInvestigation(inv, accountId);
        togglePanel(true);
    } catch (e) {
        console.error('[Investigation]', e);
    }
}

// ── WebSocket ────────────────────────────────────────────────────────
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/ws/live`;

    state.ws = new WebSocket(url);

    state.ws.onopen = () => {
        console.log('[WS] Connected');
        state.reconnectAttempts = 0;
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };

    state.ws.onclose = () => {
        console.log('[WS] Disconnected');
        if (state.reconnectAttempts < state.maxReconnect) {
            state.reconnectAttempts++;
            setTimeout(connectWebSocket, 2000);
        }
    };

    state.ws.onerror = (e) => {
        console.error('[WS] Error:', e);
    };
}

function handleMessage(msg) {
    if (msg.type === 'transaction') {
        addTransactionToFeed(msg.data);
    } else if (msg.type === 'stats') {
        updateStats(msg.data);
    }
}

// ── Renderers ────────────────────────────────────────────────────────

function addTransactionToFeed(tx) {
    state.txCount++;
    const score = tx.edge_score || 0;
    const isHighRisk = score > 0.7;

    const row = document.createElement('tr');
    row.className = 'hover:bg-primary-container/5 transition-colors group cursor-pointer slide-in-alert';

    const senderShort = escapeHtml((tx.sender_id || '').slice(-6));
    const receiverShort = escapeHtml((tx.receiver_id || '').slice(-6));
    const amount = escapeHtml(formatCurrency(tx.amount));
    const time = escapeHtml(formatTime(tx.timestamp));
    const scoreText = escapeHtml(score.toFixed(2));

    row.innerHTML = `
        <td class="px-4 py-3 font-data-mono text-[12px] text-on-surface-variant">${time}</td>
        <td class="px-4 py-3">
            <div class="font-data-mono text-[11px] text-primary">${senderShort}</div>
            <div class="font-data-mono text-[11px] text-on-surface-variant">${receiverShort}</div>
        </td>
        <td class="px-4 py-3 text-right font-data-mono text-[12px] text-on-surface">${amount}</td>
        <td class="px-4 py-3 text-center font-data-mono">
            <span class="px-1.5 py-0.5 rounded-full ${isHighRisk ? 'bg-error/10 text-error border-error/20' : 'bg-surface-variant/30 text-on-surface-variant border-outline-variant/20'} text-[10px] font-bold border">${scoreText}</span>
        </td>
    `;

    // Prepend to feed
    if (dom.feedBody && dom.feedBody.querySelector('.empty-state')) {
        dom.feedBody.innerHTML = '';
    }
    if (dom.feedBody) {
        dom.feedBody.prepend(row);
        while (dom.feedBody.children.length > state.maxFeedItems) {
            dom.feedBody.removeChild(dom.feedBody.lastChild);
        }
    }

    if (dom.feedCount) dom.feedCount.textContent = state.txCount;
    if (dom.statProcessed) animateCounter(dom.statProcessed, state.txCount);
}

function renderAlerts(alerts) {
    if (!dom.alertBody) return;
    
    if (!alerts.length) {
        dom.alertBody.innerHTML = '<div class="text-[12px] text-on-surface-variant">No alerts</div>';
        return;
    }

    dom.alertBody.innerHTML = '';
    alerts.forEach(alert => {
        const el = document.createElement('div');
        
        const isCritical = alert.severity.toLowerCase() === 'critical';
        const borderColor = isCritical ? 'border-error/30' : 'border-tertiary/20';
        const hoverBorder = isCritical ? 'hover:border-error' : 'hover:border-tertiary';
        const textColor = isCritical ? 'text-error' : 'text-tertiary';
        const icon = isCritical ? 'warning' : 'info';
        const pulseClass = isCritical ? 'critical-pulse' : '';
        const pattern = alert.primary_pattern || 'Anomalous Transfer';
        
        el.className = `p-3 bg-surface-container-low border ${borderColor} rounded-lg group ${hoverBorder} transition-all cursor-pointer relative overflow-hidden ${pulseClass} alert-item`;
        el.dataset.accountId = alert.account_id;

        el.innerHTML = `
            <div class="flex justify-between items-start mb-2">
                <div>
                    <h3 class="font-data-mono text-primary text-xs uppercase">${escapeHtml(alert.account_id)}</h3>
                    <p class="font-arbutus text-[8px] ${textColor} uppercase mt-1">${escapeHtml(alert.severity)}</p>
                </div>
                <span class="material-symbols-outlined ${textColor} text-sm">${icon}</span>
            </div>
            <div class="text-[11px] text-on-surface-variant mb-4">Pattern: <span class="text-on-surface font-medium">${escapeHtml(pattern)}</span></div>
            <button class="w-full py-2 border border-outline-variant hover:border-primary text-on-surface-variant hover:text-primary font-arbutus text-[9px] uppercase rounded transition-all investigate-btn">Investigate</button>
        `;

        el.addEventListener('click', () => selectAlert(alert));
        dom.alertBody.appendChild(el);
    });
}

function selectAlert(alert) {
    // Deselect previous
    document.querySelectorAll('.alert-item').forEach(el => {
        el.classList.remove('ring-1', 'ring-primary');
    });

    // Select new
    const el = dom.alertBody.querySelector(`[data-account-id="${alert.account_id}"]`);
    if (el) el.classList.add('ring-1', 'ring-primary');

    state.selectedAlert = alert;

    // Load graph and investigation
    loadGraph(alert.account_id);
    loadInvestigation(alert.account_id);
}

function renderGraph(data, centerId) {
    if (!dom.graphCanvas) return;

    if (!data.nodes || !data.nodes.length) {
        if (dom.graphPlaceholder) dom.graphPlaceholder.style.display = 'flex';
        return;
    }

    const nodes = data.nodes.map(n => {
        let color, size, borderColor;
        const score = n.graph_score || 0;

        if (n.is_center) {
            color = '#ef4444'; // error
            size = 30;
            borderColor = '#ffb4ab';
        } else if (n.in_cycle) {
            color = '#f97316';
            size = 22;
            borderColor = '#f97316';
        } else if (n.in_chain) {
            color = '#eab308';
            size = 20;
            borderColor = '#eab308';
        } else if (n.is_hub) {
            color = '#8b5cf6';
            size = 25;
            borderColor = '#8b5cf6';
        } else if (n.is_dormant) {
            color = '#64748b';
            size = 15;
            borderColor = '#64748b';
        } else {
            color = score > 0.3 ? '#88c0d0' : '#2b4c68'; // primary-container or secondary-container
            size = 15;
            borderColor = score > 0.3 ? '#88c0d0' : '#40484b';
        }

        return {
            id: n.id,
            label: n.label,
            title: escapeHtml(`${n.id}\n${n.name}\nType: ${n.type}\nBranch: ${n.branch}\nGraph Score: ${(score * 100).toFixed(0)}%`),
            size: size,
            color: {
                background: color,
                border: borderColor,
                highlight: { background: '#a3dcec', border: '#a3dcec' },
                hover: { background: color, border: '#a3dcec' },
            },
            font: { color: '#e2e2ec', size: 11, face: 'Geist Mono' },
            borderWidth: n.is_center ? 3 : 1,
            shadow: n.is_center ? { enabled: true, color: 'rgba(239,68,68,0.4)', size: 15 } : false,
        };
    });

    const edges = data.edges.map((e, i) => ({
        id: `e${i}`,
        from: e.from,
        to: e.to,
        label: e.amount ? `₹${formatNumber(Math.round(e.amount))}` : '',
        title: escapeHtml(`TX: ${e.tx_id}\nAmount: ₹${formatNumber(Math.round(e.amount))}\nTime: ${formatTime(e.timestamp)}`),
        color: {
            color: e.is_fraud ? '#ef4444' : '#8a9295', // error or outline
            highlight: '#a3dcec', // primary
            hover: '#a3dcec',
        },
        width: e.is_fraud ? 2.5 : 1,
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        font: { color: '#c0c8cb', size: 9, face: 'Geist Mono', strokeWidth: 0, background: 'rgba(17,19,26,0.8)' },
        dashes: e.is_fraud ? false : [5, 5],
        smooth: { type: 'curvedCW', roundness: 0.2 },
    }));

    // ── Filter edges to only include nodes that exist ──
    const nodeIds = new Set(nodes.map(n => n.id));
    const safeEdges = edges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to));

    if (state.network) state.network.destroy();

    const options = {
        layout: { improvedLayout: true },
        physics: { 
            enabled: true,
            barnesHut: {
                gravitationalConstant: -2000,
                centralGravity: 0.3,
                springLength: 95,
                springConstant: 0.04,
                damping: 0.09,
                avoidOverlap: 0
            }
        },
        interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true }
    };

    state.network = new vis.Network(
        dom.graphCanvas,
        { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(safeEdges) },
        options
    );
} 

function renderInvestigation(inv, accountId) {
    if (!dom.invContent) return;

    const evidence = inv.evidence || {};
    const scores = evidence.scores || {};
    const temporal = evidence.temporal_profile || {};
    const patterns = evidence.detected_patterns || [];
    
    // Check if we need to update the title
    const panelTitle = dom.invPanel.querySelector('h2');
    if (panelTitle) {
        panelTitle.innerHTML = `Investigation Summary: <span class="font-data-mono">${escapeHtml(accountId)}</span>`;
    }

    const edgeW = ((scores.edge_score || 0) * 100).toFixed(1);
    const graphW = ((scores.graph_score || 0) * 100).toFixed(1);
    const tempW = ((scores.temporal_score || 0) * 100).toFixed(1);

    dom.invContent.innerHTML = `
        <div class="col-span-5 flex flex-col justify-center">
            <h3 class="font-arbutus text-[9px] text-on-surface-variant uppercase mb-4">Risk Fusion Breakdown</h3>
            <div class="space-y-4">
                <div class="space-y-1.5">
                    <div class="flex justify-between font-data-mono text-[11px] text-on-surface"><span>EDGE_RISK</span><span>${edgeW}%</span></div>
                    <div class="h-1 bg-surface-variant rounded-full overflow-hidden">
                        <div class="h-full bg-error progress-bar-fill" style="width: 0%" data-width="${edgeW}%"></div>
                    </div>
                </div>
                <div class="space-y-1.5">
                    <div class="flex justify-between font-data-mono text-[11px] text-on-surface"><span>GRAPH_TOPOLOGY</span><span>${graphW}%</span></div>
                    <div class="h-1 bg-surface-variant rounded-full overflow-hidden">
                        <div class="h-full bg-error progress-bar-fill" style="width: 0%" data-width="${graphW}%"></div>
                    </div>
                </div>
                <div class="space-y-1.5">
                    <div class="flex justify-between font-data-mono text-[11px] text-on-surface"><span>TEMPORAL_ANOMALIES</span><span>${tempW}%</span></div>
                    <div class="h-1 bg-surface-variant rounded-full overflow-hidden">
                        <div class="h-full bg-tertiary progress-bar-fill" style="width: 0%" data-width="${tempW}%"></div>
                    </div>
                </div>
            </div>
            
            <div class="mt-6 flex flex-col gap-2">
                <div class="font-arbutus text-[9px] text-on-surface-variant uppercase mb-1">Detected Patterns</div>
                <div class="flex flex-wrap gap-2">
                    ${patterns.map(p => `<span class="px-2 py-1 bg-surface-variant/50 text-on-surface text-[10px] font-data-mono rounded border border-outline-variant/30">${escapeHtml(p)}</span>`).join('')}
                    ${patterns.length === 0 ? '<span class="text-on-surface-variant text-[10px]">No specific patterns</span>' : ''}
                </div>
            </div>
        </div>
        <div class="col-span-1 border-r border-outline-variant/10"></div>
        <div class="col-span-6 flex flex-col h-full overflow-hidden">
            <div class="flex justify-between items-center mb-2">
                <h3 class="font-arbutus text-[9px] text-on-surface-variant uppercase">Generated STR Narrative</h3>
                <button class="text-[9px] text-primary hover:underline font-arbutus uppercase">Export PDF</button>
            </div>
            <div class="flex-1 glass-panel p-3 rounded-lg border border-primary/10 overflow-y-auto">
                <p class="font-body-md text-on-surface-variant leading-relaxed text-[12px] whitespace-pre-wrap">
<span class="text-primary font-bold font-data-mono">[AUTO-GENERATED_REPORT]</span> - ${escapeHtml(inv.str_narrative || 'No narrative generated.')}
                </p>
            </div>
        </div>
    `;
    
    dom.invContent.className = "flex-1 p-gutter grid grid-cols-12 gap-stack-lg overflow-y-auto animate-on-reveal";
}

function triggerChartAnimations() {
    document.querySelectorAll('.progress-bar-fill').forEach(bar => {
        setTimeout(() => {
            bar.style.width = bar.getAttribute('data-width');
        }, 50);
    });
}

function updateStats(data) {
    if (data.processed && dom.statProcessed) {
        animateCounter(dom.statProcessed, data.processed);
    }
    if (data.alerts !== undefined && dom.statAlerts) {
        animateCounter(dom.statAlerts, data.alerts);
    }
}

// ── Utilities ────────────────────────────────────────────────────────

function animateCounter(el, target) {
    if (!el) return;
    const duration = 1000;
    const current = parseFloat(el.textContent.replace(/,/g, '') || 0);
    const start = performance.now();

    const animate = (time) => {
        const elapsed = time - start;
        const progress = Math.min(elapsed / duration, 1);
        const easeOutQuad = progress * (2 - progress);
        const val = current + (target - current) * easeOutQuad;

        el.textContent = formatNumber(Math.round(val));

        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            el.textContent = formatNumber(target);
        }
    };
    requestAnimationFrame(animate);
}

function formatCurrency(amount) {
    if (!amount) return '$0';
    return `$${amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}

function formatNumber(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return Number(n).toLocaleString();
}

function formatTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date(ts);
        return d.toLocaleTimeString('en-GB', { hour12: false });
    } catch { return ''; }
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Start ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
