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

    dom.loading.classList.add('hidden');

    // Load initial data
    await loadStats();
    await loadAlerts();

    // Start WebSocket
    connectWebSocket();

    // Setup event listeners
    dom.invClose.addEventListener('click', closeInvestigation);

    console.log('[GraphGuard] Ready.');
}

// ── API Calls ────────────────────────────────────────────────────────
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        dom.statAccounts.textContent = formatNumber(data.total_accounts || 0);
        dom.statAlerts.textContent = data.risk_stats?.total_alerts || 0;
    } catch (e) {
        console.error('[Stats]', e);
    }
}

async function loadAlerts() {
    try {
        const res = await fetch('/api/alerts');
        const alerts = await res.json();
        renderAlerts(alerts);
        dom.alertCount.textContent = alerts.length;
        dom.statAlerts.textContent = alerts.length;
    } catch (e) {
        console.error('[Alerts]', e);
    }
}

async function loadGraph(accountId) {
    try {
        dom.graphInfo.textContent = `Loading ${accountId}...`;
        const res = await fetch(`/api/graph/${accountId}`);
        const graph = await res.json();
        renderGraph(graph, accountId);
        dom.graphPlaceholder.style.display = 'none';
        dom.graphInfo.textContent = `${accountId} — ${graph.nodes?.length || 0} nodes, ${graph.edges?.length || 0} edges`;
    } catch (e) {
        console.error('[Graph]', e);
        dom.graphInfo.textContent = 'Error loading graph';
    }
}

async function loadInvestigation(accountId) {
    try {
        const res = await fetch(`/api/investigation/${accountId}`);
        const inv = await res.json();
        renderInvestigation(inv);
        dom.invPanel.classList.add('open');
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
    const riskClass = getRiskClass(score);

    const item = document.createElement('div');
    item.className = `tx-item ${riskClass}`;

    const senderShort = (tx.sender_id || '').slice(-6);
    const receiverShort = (tx.receiver_id || '').slice(-6);
    const amount = formatCurrency(tx.amount);
    const time = formatTime(tx.timestamp);

    item.innerHTML = `
        <div class="tx-direction">→</div>
        <div class="tx-details">
            <div class="tx-accounts">${senderShort} → ${receiverShort}</div>
            <div class="tx-meta">${tx.tx_type || 'transfer'} · ${tx.channel || ''} · ${time}</div>
        </div>
        <div class="tx-amount">${amount}</div>
        <div class="tx-score ${riskClass}">${(score * 100).toFixed(0)}%</div>
    `;

    // Prepend to feed
    if (dom.feedBody.querySelector('.empty-state')) {
        dom.feedBody.innerHTML = '';
    }
    dom.feedBody.prepend(item);

    // Limit feed size
    while (dom.feedBody.children.length > state.maxFeedItems) {
        dom.feedBody.removeChild(dom.feedBody.lastChild);
    }

    dom.feedCount.textContent = state.txCount;
    dom.statProcessed.textContent = formatNumber(state.txCount);
}

function renderAlerts(alerts) {
    if (!alerts.length) {
        dom.alertBody.innerHTML = '<div class="empty-state"><span class="icon">✓</span><p>No alerts</p></div>';
        return;
    }

    dom.alertBody.innerHTML = '';
    alerts.forEach(alert => {
        const el = document.createElement('div');
        el.className = `alert-item ${alert.severity}`;
        el.dataset.accountId = alert.account_id;

        const edgeW = (alert.edge_score * 100).toFixed(0);
        const graphW = (alert.graph_score * 100).toFixed(0);
        const tempW = (alert.temporal_score * 100).toFixed(0);

        el.innerHTML = `
            <div class="alert-header">
                <span class="alert-account">${alert.account_id?.slice(-8) || ''}</span>
                <span class="alert-severity ${alert.severity}">${alert.severity}</span>
            </div>
            <div class="alert-name">${alert.holder_name || 'Unknown'} · ${alert.branch || ''}</div>
            <div class="alert-scores">
                <div class="alert-score-bar edge"><div class="fill" style="width:${edgeW}%"></div></div>
                <div class="alert-score-bar graph"><div class="fill" style="width:${graphW}%"></div></div>
                <div class="alert-score-bar temporal"><div class="fill" style="width:${tempW}%"></div></div>
            </div>
            <div class="alert-score-labels">
                <span class="alert-score-label text-cyan">E:${edgeW}%</span>
                <span class="alert-score-label text-teal">G:${graphW}%</span>
                <span class="alert-score-label text-violet">T:${tempW}%</span>
                <span class="alert-score-label" style="color:var(--text-primary);font-weight:600;">
                    ${(alert.fused_score * 100).toFixed(0)}%
                </span>
            </div>
        `;

        el.addEventListener('click', () => selectAlert(alert));
        dom.alertBody.appendChild(el);
    });
}

function selectAlert(alert) {
    // Deselect previous
    document.querySelectorAll('.alert-item.selected').forEach(el => el.classList.remove('selected'));

    // Select new
    const el = dom.alertBody.querySelector(`[data-account-id="${alert.account_id}"]`);
    if (el) el.classList.add('selected');

    state.selectedAlert = alert;

    // Load graph and investigation
    loadGraph(alert.account_id);
    loadInvestigation(alert.account_id);
}

function renderGraph(data, centerId) {
    if (!data.nodes || !data.nodes.length) {
        dom.graphPlaceholder.style.display = 'flex';
        return;
    }

    const nodes = data.nodes.map(n => {
        let color, size, borderColor;
        const score = n.graph_score || 0;

        if (n.is_center) {
            color = '#ef4444';
            size = 35;
            borderColor = '#fbbf24';
        } else if (n.in_cycle) {
            color = '#f97316';
            size = 25;
            borderColor = '#f97316';
        } else if (n.in_chain) {
            color = '#eab308';
            size = 22;
            borderColor = '#eab308';
        } else if (n.is_hub) {
            color = '#8b5cf6';
            size = 28;
            borderColor = '#8b5cf6';
        } else if (n.is_dormant) {
            color = '#64748b';
            size = 18;
            borderColor = '#64748b';
        } else {
            color = score > 0.3 ? '#0ea5e9' : '#1e3a5f';
            size = 18;
            borderColor = score > 0.3 ? '#0ea5e9' : '#334155';
        }

        return {
            id: n.id,
            label: n.label,
            title: `${n.id}\n${n.name}\nType: ${n.type}\nBranch: ${n.branch}\nGraph Score: ${(score*100).toFixed(0)}%`,
            size: size,
            color: {
                background: color,
                border: borderColor,
                highlight: { background: '#06d6a0', border: '#06d6a0' },
                hover: { background: color, border: '#06d6a0' },
            },
            font: { color: '#f1f5f9', size: 11, face: 'JetBrains Mono' },
            borderWidth: n.is_center ? 3 : 1,
            shadow: n.is_center ? { enabled: true, color: 'rgba(239,68,68,0.4)', size: 15 } : false,
        };
    });

    const edges = data.edges.map((e, i) => ({
        id: `e${i}`,
        from: e.from,
        to: e.to,
        label: e.amount ? `₹${formatNumber(Math.round(e.amount))}` : '',
        title: `TX: ${e.tx_id}\nAmount: ₹${formatNumber(Math.round(e.amount))}\nTime: ${formatTime(e.timestamp)}`,
        color: {
            color: e.is_fraud ? '#ef4444' : '#334155',
            highlight: '#06d6a0',
            hover: '#0ea5e9',
        },
        width: e.is_fraud ? 2.5 : 1,
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        font: { color: '#64748b', size: 9, face: 'JetBrains Mono', strokeWidth: 0 },
        dashes: e.is_fraud ? false : [5, 5],
        smooth: { type: 'curvedCW', roundness: 0.2 },
    }));

    const options = {
        physics: {
            forceAtlas2Based: {
                gravitationalConstant: -40,
                centralGravity: 0.005,
                springLength: 150,
                springConstant: 0.08,
                damping: 0.4,
            },
            solver: 'forceAtlas2Based',
            stabilization: { iterations: 100 },
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            zoomView: true,
            dragView: true,
        },
        layout: { improvedLayout: true },
    };

    if (state.network) {
        state.network.destroy();
    }

    state.network = new vis.Network(
        dom.graphCanvas,
        { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) },
        options
    );
}

function renderInvestigation(inv) {
    const evidence = inv.evidence || {};
    const scores = evidence.scores || {};
    const temporal = evidence.temporal_profile || {};
    const patterns = evidence.detected_patterns || [];
    const actions = inv.recommended_actions || [];

    const fusedPct = ((scores.fused_score || 0) * 100).toFixed(1);
    const circumference = 2 * Math.PI * 34;
    const offset = circumference * (1 - (scores.fused_score || 0));

    dom.invContent.innerHTML = `
        <!-- Score & Patterns -->
        <div class="inv-section">
            <div class="inv-section-title">⚠️ Risk Assessment</div>
            <svg class="score-ring" viewBox="0 0 80 80">
                <circle class="bg" cx="40" cy="40" r="34"/>
                <circle class="fg" cx="40" cy="40" r="34"
                    stroke-dasharray="${circumference}"
                    stroke-dashoffset="${offset}"
                    style="stroke:${getScoreColor(scores.fused_score || 0)}"/>
                <text class="score-ring-value" x="40" y="40">${fusedPct}%</text>
            </svg>
            <div class="inv-metric">
                <span class="inv-metric-label">Edge Score</span>
                <span class="inv-metric-value text-cyan">${((scores.edge_score||0)*100).toFixed(1)}%</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Graph Score</span>
                <span class="inv-metric-value text-teal">${((scores.graph_score||0)*100).toFixed(1)}%</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Temporal Score</span>
                <span class="inv-metric-value text-violet">${((scores.temporal_score||0)*100).toFixed(1)}%</span>
            </div>
            <div style="margin-top:12px;">
                <div class="inv-section-title" style="margin-bottom:6px">🔍 Detected Patterns</div>
                <ul class="inv-patterns">
                    ${patterns.map(p => `
                        <li class="inv-pattern-item">
                            <span class="inv-pattern-dot"></span>${p}
                        </li>
                    `).join('') || '<li class="inv-pattern-item" style="color:var(--text-muted)">No specific patterns</li>'}
                </ul>
            </div>
            ${actions.length ? `
            <div style="margin-top:12px;">
                <div class="inv-section-title" style="margin-bottom:6px">📋 Recommended Actions</div>
                <ul class="inv-actions">
                    ${actions.map(a => `
                        <li class="inv-action-item">
                            <span class="inv-action-icon">▸</span>${a}
                        </li>
                    `).join('')}
                </ul>
            </div>` : ''}
        </div>

        <!-- Temporal Profile -->
        <div class="inv-section">
            <div class="inv-section-title">⏱️ Temporal Behavior</div>
            <div class="inv-metric">
                <span class="inv-metric-label">Avg Propagation</span>
                <span class="inv-metric-value">${temporal.avg_propagation_speed_hrs ?? 'N/A'} hrs</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Min Retention</span>
                <span class="inv-metric-value">${temporal.min_retention_hrs ?? 'N/A'} hrs</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Peak Density</span>
                <span class="inv-metric-value">${temporal.peak_hop_density_per_hr ?? 'N/A'}/hr</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Burst Events</span>
                <span class="inv-metric-value">${temporal.burst_redistribution_count ?? 0}</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Unique Beneficiaries</span>
                <span class="inv-metric-value">${temporal.unique_beneficiaries ?? 0}</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Total Outflows</span>
                <span class="inv-metric-value">${temporal.total_outflows ?? 0}</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Total Inflows</span>
                <span class="inv-metric-value">${temporal.total_inflows ?? 0}</span>
            </div>
            <div class="inv-metric">
                <span class="inv-metric-label">Dormant Activation</span>
                <span class="inv-metric-value">${temporal.dormant_activation ? '⚠️ YES' : 'No'}</span>
            </div>
        </div>

        <!-- STR Narrative -->
        <div class="inv-section">
            <div class="inv-section-title">📄 STR Narrative</div>
            <div class="str-text">${escapeHtml(inv.str_narrative || 'No narrative generated.')}</div>
        </div>
    `;
}

function closeInvestigation() {
    dom.invPanel.classList.remove('open');
    state.selectedAlert = null;
    document.querySelectorAll('.alert-item.selected').forEach(el => el.classList.remove('selected'));
}

function updateStats(data) {
    if (data.processed) {
        dom.statProcessed.textContent = formatNumber(data.processed);
    }
    if (data.alerts !== undefined) {
        dom.statAlerts.textContent = data.alerts;
    }
}

// ── Utilities ────────────────────────────────────────────────────────
function getRiskClass(score) {
    if (score >= 0.85) return 'critical';
    if (score >= 0.70) return 'high';
    if (score >= 0.50) return 'medium';
    return 'low';
}

function getScoreColor(score) {
    if (score >= 0.85) return '#ef4444';
    if (score >= 0.70) return '#f97316';
    if (score >= 0.50) return '#eab308';
    return '#22c55e';
}

function formatCurrency(amount) {
    if (!amount) return '₹0';
    if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
    if (amount >= 1000) return `₹${(amount / 1000).toFixed(1)}K`;
    return `₹${Math.round(amount)}`;
}

function formatNumber(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
}

function formatTime(ts) {
    if (!ts) return '';
    try {
        const d = new Date(ts);
        return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    } catch { return ''; }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Start ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
