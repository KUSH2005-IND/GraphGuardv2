import re

with open('stitch_graphguard_fraud_intelligence_platform/code.html', 'r') as f:
    code_html = f.read()

# Replace the style block
code_html = re.sub(r'<style>.*?</style>', '<link rel="stylesheet" href="/static/styles.css">\n<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>', code_html, flags=re.DOTALL)

# Add loading overlay
loading_overlay = """
<div class="loading-overlay" id="loadingOverlay" style="display: flex;">
    <div class="loading-spinner"></div>
    <div class="loading-text">Initializing fraud intelligence pipeline...</div>
</div>
<div id="cursor-glow"></div>
"""
code_html = code_html.replace('<div id="cursor-glow"></div>', loading_overlay)

# Stats IDs
code_html = code_html.replace('data-target="14520"', 'id="statProcessed" data-target="0"')
code_html = code_html.replace('data-target="82.4"', 'id="statAccounts" data-target="0"')
code_html = code_html.replace('data-target="14"', 'id="statAlerts" data-target="0"')
code_html = code_html.replace('>Network Velocity</a>', '>Processed</a>')
code_html = code_html.replace('>Risk Aggregation</a>', '>Accounts</a>')
code_html = code_html.replace('>Active Alerts</a>', '>Alerts</a>')

code_html = code_html.replace('Live Transaction Feed</h2>', 'Live Transaction Feed</h2>\n<span class="panel-badge" id="feedCount" style="display:none;">0</span>')
code_html = code_html.replace('<tbody class="divide-y divide-outline-variant/10" id="feed-body">', '<tbody class="divide-y divide-outline-variant/10" id="feedBody">')

# Graph container
graph_html = """
<div class="absolute inset-0 flex items-center justify-center pointer-events-none opacity-60" id="graphPlaceholder">
    <div class="relative w-full h-full overflow-hidden flex flex-col items-center justify-center">
        <span class="material-symbols-outlined text-[48px] text-outline-variant mb-4 breathing-node">hub</span>
        <p class="font-arbutus text-[10px] uppercase tracking-[0.1em] text-on-surface-variant">Click an alert to visualize subgraph</p>
    </div>
</div>
<div id="graphCanvas" class="absolute inset-0 w-full h-full z-10"></div>
"""
code_html = re.sub(r'<div class="absolute inset-0 flex items-center justify-center pointer-events-none opacity-60">.*?</div>\n</div>', graph_html, code_html, flags=re.DOTALL)
code_html = code_html.replace('<span class="material-symbols-outlined text-sm">remove</span>\n</button>\n</div>\n</div>', '<span class="material-symbols-outlined text-sm">remove</span>\n</button>\n</div>\n</div>\n<div class="absolute top-4 left-4 z-20"><div id="graphInfo" class="bg-surface-container-high/80 backdrop-blur-md px-3 py-1.5 rounded border border-outline-variant/30 font-data-mono text-[10px] text-primary">Select an alert</div></div>')

# Alert Queue
code_html = code_html.replace('<h2 class="font-arbutus text-[10px] text-on-surface tracking-wide uppercase">Active Alert Queue</h2>', '<h2 class="font-arbutus text-[10px] text-on-surface tracking-wide uppercase">Active Alert Queue</h2>\n<span class="panel-badge" id="alertCount" style="display:none;">0</span>')
code_html = re.sub(r'<div class="flex-1 overflow-y-auto p-3 space-y-3">.*?</div>\n</section>', '<div class="flex-1 overflow-y-auto p-3 space-y-3" id="alertBody"></div>\n</section>', code_html, flags=re.DOTALL)

# Bottom panel
panel_html = """
<section class="h-[200px] mt-auto border-t border-outline-variant/30 bg-surface-container-lowest/80 backdrop-blur-2xl flex flex-col translate-y-[160px]" id="investigationPanel" style="display: none;">
<div class="px-container-padding py-2 flex justify-between items-center bg-surface-container-high/30 border-b border-outline-variant/10 cursor-pointer" onclick="togglePanel()">
<div class="flex items-center gap-3">
<span class="material-symbols-outlined text-primary text-sm">analytics</span>
<h2 class="font-arbutus text-[10px] text-on-surface tracking-wide uppercase">Investigation Summary</h2>
</div>
<div class="flex items-center gap-4">
<button class="text-on-surface-variant hover:text-on-surface transition-all" id="invClose">
<span class="material-symbols-outlined text-sm">close</span>
</button>
</div>
</div>
<div class="flex-1 p-gutter overflow-hidden animate-on-reveal" id="invContent">
</div>
</section>
"""
code_html = re.sub(r'<section class="h-\[200px\] mt-auto.*?<!-- Bottom Panel -->', '<!-- Bottom Panel -->\n' + panel_html, code_html, flags=re.DOTALL)
# The above regex might be tricky, let's just do a simple replacement for the investigation panel.
