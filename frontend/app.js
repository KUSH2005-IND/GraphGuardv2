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
    graphMode: 'overview',         // 'overview' or 'investigation'
    currentAccountId: null,        // currently selected account
    cachedOverviewGraph: null,     // cached overview graph data
    cachedInvestigationGraph: null, // cached investigation graph data
    legendVisible: false,
    allAlerts: [],                  // cached alerts for search filtering
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
    graphModeToggle: document.getElementById('graphModeToggle'),
    btnOverview: document.getElementById('btnOverview'),
    btnInvestigation: document.getElementById('btnInvestigation'),
    graphLegend: document.getElementById('graphLegend'),
    legendPathEdge: document.getElementById('legendPathEdge'),
    fraudPatternPanel: document.getElementById('fraudPatternPanel'),
    fraudPatternList: document.getElementById('fraudPatternList'),
    searchInput: document.getElementById('searchInput'),
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

    // Search functionality
    if (dom.searchInput) {
        dom.searchInput.addEventListener('input', () => {
            const query = dom.searchInput.value.trim().toLowerCase();
            if (!query) {
                renderAlerts(state.allAlerts);
                return;
            }
            const filtered = state.allAlerts.filter(a =>
                (a.account_id && a.account_id.toLowerCase().includes(query)) ||
                (a.holder_name && a.holder_name.toLowerCase().includes(query)) ||
                (a.primary_pattern && a.primary_pattern.toLowerCase().includes(query))
            );
            renderAlerts(filtered);
        });
    }

    console.log('[GraphGuard] Ready.');
}

// ── Toggle Panel Function (Stitch UI) ────────────────────────────────
function togglePanel(forceOpen = null) {
    const panel = dom.invPanel;
    if (!panel) return;
    
    const isCollapsed = panel.classList.contains('translate-y-[360px]');
    const shouldOpen = forceOpen !== null ? forceOpen : isCollapsed;
    
    if (shouldOpen) {
        panel.style.display = 'flex';
        setTimeout(() => {
            panel.classList.remove('translate-y-[360px]');
        }, 10);
        triggerChartAnimations();
    } else {
        panel.classList.add('translate-y-[360px]');
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
        state.allAlerts = alerts;
        renderAlerts(alerts);
        if (dom.alertCount) dom.alertCount.textContent = `${alerts.length} Pending`;
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
        state.cachedOverviewGraph = graph;
        if (dom.graphPlaceholder) dom.graphPlaceholder.style.display = 'none';
        if (state.graphMode === 'overview') {
            renderGraph(graph, accountId);
            if (dom.graphInfo) dom.graphInfo.textContent = `${escapeHtml(accountId)} — ${graph.nodes?.length || 0} nodes, ${graph.edges?.length || 0} edges`;
        }
    } catch (e) {
        console.error('[Graph]', e);
        if (dom.graphInfo) dom.graphInfo.textContent = 'Error loading graph';
        if (dom.graphPlaceholder) dom.graphPlaceholder.style.display = 'flex';
    }
}

async function loadInvestigationGraph(accountId) {
    try {
        const res = await fetch(`/api/graph/${accountId}/investigation`, { headers: { 'X-API-Key': 'GG-SECRET-KEY-2026' } });
        const graph = await res.json();
        state.cachedInvestigationGraph = graph;
        if (state.graphMode === 'investigation') {
            renderInvestigationGraph(graph, accountId);
            renderFraudPatterns(graph.fraud_classifications || []);
        }
        return graph;
    } catch (e) {
        console.error('[InvestigationGraph]', e);
        return null;
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
    const score = tx.edge_score || tx.risk_pct/100 || 0;
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
        const pattern = alert.pattern || alert.primary_pattern || 'Anomalous Transfer';
        
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

async function selectAlert(alert) {
    // Deselect previous
    document.querySelectorAll('.alert-item').forEach(el => {
        el.classList.remove('ring-1', 'ring-primary');
    });

    // Select new
    const el = dom.alertBody.querySelector(`[data-account-id="${alert.account_id}"]`);
    if (el) el.classList.add('ring-1', 'ring-primary');

    state.selectedAlert = alert;
    state.currentAccountId = alert.account_id;

    // Show mode toggle
    if (dom.graphModeToggle) dom.graphModeToggle.style.display = 'flex';

    // Load both graph modes in parallel
    loadGraph(alert.account_id);
    loadInvestigation(alert.account_id);
    const graphData = await loadInvestigationGraph(alert.account_id);

    // Animate suspicious path after graph renders
    setTimeout(() => {
        if (graphData?.suspicious_path?.length > 1) {
            animateFraudPath(graphData.suspicious_path);
        }
    }, 600);  // wait for graph to settle
}

function animateFraudPath(pathNodes) {
    if (!state.network) return;
    const pathSet = new Set(pathNodes);
    const allNodeIds = state.network.body.data.nodes.getIds();

    // Step 1: Dim everything
    state.network.body.data.nodes.update(
        allNodeIds.map(id => ({
            id,
            opacity: pathSet.has(id) ? 1.0 : 0.2
        }))
    );

    // Step 2: Light up path nodes one by one
    pathNodes.forEach((nodeId, i) => {
        setTimeout(() => {
            if (allNodeIds.includes(nodeId)) {
                state.network.body.data.nodes.update([{
                    id: nodeId,
                    color: {
                        background: i === 0 ? '#ef4444' : '#f97316',
                        border: '#fbbf24'
                    },
                    borderWidth: 4,
                    size: 32
                }]);
            }

            // Highlight the edge to next node
            if (i < pathNodes.length - 1) {
                const allEdges = state.network.body.data.edges.get();
                const pathEdge = allEdges.find(
                    e => e.from === nodeId && e.to === pathNodes[i + 1]
                );
                if (pathEdge) {
                    state.network.body.data.edges.update([{
                        id: pathEdge.id,
                        color: { color: '#ef4444' },
                        width: 5
                    }]);
                }
            }
        }, i * 500);
    });

    // Step 3: Fit view to path nodes after animation
    setTimeout(() => {
        const existingPathNodes = pathNodes.filter(n => allNodeIds.includes(n));
        if (existingPathNodes.length > 0) {
            state.network.fit({
                nodes: existingPathNodes,
                animation: { duration: 600, easingFunction: 'easeInOutQuad' }
            });
        }
    }, pathNodes.length * 500 + 200);
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
            is_center: n.is_center,
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

    // Hide investigation-mode overlays in overview
    if (dom.fraudPatternPanel) dom.fraudPatternPanel.style.display = 'none';
    if (dom.legendPathEdge) dom.legendPathEdge.style.display = 'none';
    if (dom.graphCanvas) dom.graphCanvas.classList.remove('investigation-active');

    state.network = new vis.Network(
        dom.graphCanvas,
        { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(safeEdges) },
        options
    );
}

// ── Investigation Mode Graph ─────────────────────────────────────────
function renderInvestigationGraph(data, centerId) {
    if (!dom.graphCanvas) return;

    if (!data.nodes || !data.nodes.length) {
        if (dom.graphPlaceholder) dom.graphPlaceholder.style.display = 'flex';
        return;
    }

    const patternType = data.pattern_type || 'unknown';
    const patternLabels = {
        'circular_flow': '🔄 Circular Flow',
        'layering': '📊 Layering Chain',
        'mule_network': '🕸️ Mule Network',
        'dormant_activation': '💤 Dormant Activation',
        'temporal_burst': '⚡ Temporal Burst',
        'suspicious_activity': '⚠️ Suspicious Activity',
        'unknown': '🔍 Under Investigation',
    };

    if (dom.graphInfo) {
        const nodeCount = data.nodes.length;
        const edgeCount = data.edges.length;
        const label = patternLabels[patternType] || patternLabels['unknown'];
        dom.graphInfo.textContent = `${escapeHtml(centerId)} — ${label} — ${nodeCount} nodes, ${edgeCount} edges`;
    }

    const nodes = data.nodes.map(n => {
        let color, size, borderColor, borderWidth;
        const score = n.graph_score || 0;
        const onPath = n.on_suspicious_path;

        if (n.is_center) {
            color = '#ef4444';
            size = onPath ? 35 : 30;
            borderColor = '#ffb4ab';
            borderWidth = 4;
        } else if (onPath && n.in_cycle) {
            color = '#f97316';
            size = 28;
            borderColor = '#fb923c';
            borderWidth = 3;
        } else if (onPath && n.in_chain) {
            color = '#eab308';
            size = 26;
            borderColor = '#facc15';
            borderWidth = 3;
        } else if (onPath && n.is_hub) {
            color = '#8b5cf6';
            size = 30;
            borderColor = '#a78bfa';
            borderWidth = 3;
        } else if (onPath) {
            color = '#f97316';
            size = 24;
            borderColor = '#fb923c';
            borderWidth = 2;
        } else if (n.is_dormant) {
            color = '#334155';
            size = 12;
            borderColor = '#475569';
            borderWidth = 1;
        } else {
            // Context node — very dim
            color = '#1e293b';
            size = 10;
            borderColor = '#334155';
            borderWidth = 1;
        }

        const nodeLabel = onPath ? n.label : '';

        return {
            id: n.id,
            label: nodeLabel,
            title: escapeHtml(`${n.id}\n${n.name}\nType: ${n.type}\nBranch: ${n.branch}\nGraph Score: ${(score * 100).toFixed(0)}%${onPath ? '\n★ ON SUSPICIOUS PATH' : ''}`),
            size: size,
            color: {
                background: color,
                border: borderColor,
                highlight: { background: '#a3dcec', border: '#a3dcec' },
                hover: { background: color, border: '#a3dcec' },
            },
            font: {
                color: onPath ? '#ffffff' : '#475569',
                size: onPath ? 13 : 9,
                face: 'Geist Mono',
                bold: onPath ? { color: '#ffffff' } : undefined,
            },
            borderWidth: borderWidth,
            shadow: onPath ? { enabled: true, color: `rgba(${n.is_center ? '239,68,68' : '249,115,22'},0.5)`, size: 20 } : false,
            opacity: onPath ? 1.0 : 0.25,
        };
    });

    const edges = data.edges.map((e, i) => {
        const onPath = e.on_suspicious_path;
        return {
            id: `e${i}`,
            from: e.from,
            to: e.to,
            label: onPath && e.amount ? `₹${formatNumber(Math.round(e.amount))}` : '',
            title: escapeHtml(`TX: ${e.tx_id}\nAmount: ₹${formatNumber(Math.round(e.amount))}\nTime: ${formatTime(e.timestamp)}${onPath ? '\n★ SUSPICIOUS PATH' : ''}`),
            color: {
                color: onPath ? '#ef4444' : '#1e293b',
                highlight: '#a3dcec',
                hover: '#a3dcec',
            },
            width: onPath ? 4 : 0.5,
            arrows: { to: { enabled: true, scaleFactor: onPath ? 0.8 : 0.4 } },
            font: {
                color: onPath ? '#fca5a5' : '#334155',
                size: onPath ? 11 : 8,
                face: 'Geist Mono',
                strokeWidth: 0,
                background: onPath ? 'rgba(17,19,26,0.9)' : 'rgba(17,19,26,0.5)',
            },
            dashes: onPath ? false : [3, 3],
            smooth: { type: 'curvedCW', roundness: 0.15 },
            opacity: onPath ? 1.0 : 0.15,
        };
    });

    // Filter edges to only include nodes that exist
    const nodeIds = new Set(nodes.map(n => n.id));
    const safeEdges = edges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to));

    if (state.network) state.network.destroy();

    // Use hierarchical layout for chains/layering, physics for cycles/hubs
    const useHierarchical = (patternType === 'layering' || patternType === 'dormant_activation');

    const options = {
        layout: useHierarchical ? {
            hierarchical: {
                direction: 'LR',
                sortMethod: 'directed',
                levelSeparation: 150,
                nodeSpacing: 80,
                treeSpacing: 100,
            }
        } : {
            improvedLayout: true,
        },
        physics: useHierarchical ? {
            enabled: false,
        } : {
            enabled: true,
            barnesHut: {
                gravitationalConstant: -3000,
                centralGravity: 0.5,
                springLength: 120,
                springConstant: 0.06,
                damping: 0.12,
                avoidOverlap: 0.3,
            }
        },
        interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true },
    };

    // Show investigation overlays
    if (dom.graphCanvas) dom.graphCanvas.classList.add('investigation-active');
    if (dom.legendPathEdge) dom.legendPathEdge.style.display = 'flex';

    state.network = new vis.Network(
        dom.graphCanvas,
        { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(safeEdges) },
        options
    );

    // Auto-focus on center node after stabilization
    state.network.once('stabilized', () => {
        state.network.focus(centerId, { scale: 1.2, animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
    });
}

function renderFraudPatterns(classifications) {
    if (!dom.fraudPatternList) return;

    if (!classifications || classifications.length === 0) {
        if (dom.fraudPatternPanel) dom.fraudPatternPanel.style.display = 'none';
        return;
    }

    dom.fraudPatternList.innerHTML = '';
    if (dom.fraudPatternPanel) dom.fraudPatternPanel.style.display = 'block';

    classifications.forEach(cls => {
        const confPct = Math.round(cls.confidence * 100);
        const confClass = confPct >= 80 ? 'high' : confPct >= 60 ? 'medium' : 'low';

        const badge = document.createElement('div');
        badge.className = 'pattern-badge';
        badge.title = cls.evidence || '';
        badge.innerHTML = `
            <div class="pattern-name">
                <span class="check material-symbols-outlined">check_circle</span>
                ${escapeHtml(cls.name)}
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill ${confClass}" style="width: 0%" data-width="${confPct}%"></div>
            </div>
            <div class="confidence-text">Confidence: ${confPct}%</div>
        `;
        dom.fraudPatternList.appendChild(badge);
    });

    // Animate confidence bars
    setTimeout(() => {
        document.querySelectorAll('.pattern-badge .confidence-fill').forEach(bar => {
            bar.style.width = bar.getAttribute('data-width');
        });
    }, 100);
}

// ── Graph Mode Switching ─────────────────────────────────────────────
function switchGraphMode(mode) {
    if (mode === state.graphMode) return;
    state.graphMode = mode;

    // Update toggle buttons
    if (dom.btnOverview) {
        dom.btnOverview.classList.toggle('graph-mode-active', mode === 'overview');
    }
    if (dom.btnInvestigation) {
        dom.btnInvestigation.classList.toggle('graph-mode-active', mode === 'investigation');
    }

    const accountId = state.currentAccountId;
    if (!accountId) return;

    if (mode === 'overview' && state.cachedOverviewGraph) {
        renderGraph(state.cachedOverviewGraph, accountId);
        if (dom.graphInfo) {
            const g = state.cachedOverviewGraph;
            dom.graphInfo.textContent = `${escapeHtml(accountId)} — ${g.nodes?.length || 0} nodes, ${g.edges?.length || 0} edges`;
        }
        if (dom.fraudPatternPanel) dom.fraudPatternPanel.style.display = 'none';
    } else if (mode === 'investigation' && state.cachedInvestigationGraph) {
        renderInvestigationGraph(state.cachedInvestigationGraph, accountId);
        renderFraudPatterns(state.cachedInvestigationGraph.fraud_classifications || []);
    } else if (mode === 'investigation') {
        loadInvestigationGraph(accountId);
    }
}
window.switchGraphMode = switchGraphMode;

function recenterGraph() {
    if (state.network && state.currentAccountId) {
        state.network.focus(state.currentAccountId, {
            scale: 1.0,
            animation: { duration: 600, easingFunction: 'easeInOutQuad' }
        });
    }
}
window.recenterGraph = recenterGraph;

function toggleLegend() {
    state.legendVisible = !state.legendVisible;
    if (dom.graphLegend) {
        dom.graphLegend.style.display = state.legendVisible ? 'block' : 'none';
    }
}
window.toggleLegend = toggleLegend;

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
                <button onclick="exportPDF()" class="text-[9px] text-primary hover:underline font-arbutus uppercase">Export PDF</button>
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
    if (!amount) return '₹0';
    return `₹${amount.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
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

// ── Sidebar Toggle ───────────────────────────────────────────────────
let sidebarOpen = true;
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const main = document.getElementById('mainContent');
    if (!sidebar || !main) return;
    
    sidebarOpen = !sidebarOpen;
    if (sidebarOpen) {
        sidebar.style.transform = 'translateX(0)';
        main.style.marginLeft = '240px';
    } else {
        sidebar.style.transform = 'translateX(-100%)';
        main.style.marginLeft = '0';
    }
}

// ── Export PDF ───────────────────────────────────────────────────────
function exportPDF() {
    const invContent = document.getElementById('invContent');
    if (!invContent) {
        alert('No investigation data to export. Select an alert first.');
        return;
    }
    
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
        alert('Please allow pop-ups to export PDF.');
        return;
    }
    
    const accountId = state.currentAccountId || 'Unknown';
    const now = new Date().toLocaleString('en-IN');
    
    printWindow.document.write(`
        <!DOCTYPE html>
        <html><head>
            <title>GraphGuard v2 — STR Report — ${accountId}</title>
            <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; color: #1a1a2e; background: #fff; }
                h1 { font-size: 22px; color: #0c4f5d; border-bottom: 2px solid #88c0d0; padding-bottom: 8px; margin-bottom: 4px; }
                .meta { font-size: 11px; color: #666; margin-bottom: 24px; }
                .section { margin-bottom: 20px; }
                .section-title { font-size: 13px; font-weight: 600; color: #0c4f5d; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
                .content { font-size: 12px; line-height: 1.7; white-space: pre-wrap; }
                .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; }
                .footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #ddd; font-size: 10px; color: #999; text-align: center; }
                @media print {
                    body { padding: 20px; }
                    .no-print { display: none; }
                }
            </style>
        </head><body>
            <h1>\u{1f6e1} GraphGuard v2 — Suspicious Transaction Report</h1>
            <div class="meta">Account: <strong>${accountId}</strong> &nbsp;|&nbsp; Generated: ${now}</div>
            <div class="section">
                <div class="section-title">Investigation Details</div>
                <div class="content">${invContent.innerText}</div>
            </div>
            <div class="footer">
                GraphGuard v2 Fraud Intelligence Platform — Confidential — Auto-generated Report
            </div>
            <script>window.onload = function() { window.print(); }<\/script>
        </body></html>
    `);
    printWindow.document.close();
}

// ── Start ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
