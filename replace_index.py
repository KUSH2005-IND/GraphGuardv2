with open('stitch_graphguard_fraud_intelligence_platform/code.html', 'r') as f:
    code = f.read()

# Replace Style
import re
code = re.sub(r'<style>.*?</style>', '<link rel="stylesheet" href="/static/styles.css">\n<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>', code, flags=re.DOTALL)

# Cursor-glow -> Loading overlay
loading = """<div class="loading-overlay" id="loadingOverlay" style="display: flex;">
    <div class="loading-spinner"></div>
    <div class="loading-text">Initializing fraud intelligence pipeline...</div>
</div>
<div id="cursor-glow"></div>"""
code = code.replace('<div id="cursor-glow"></div>', loading)

# App.js at the end
code = code.replace('</body>', '<script src="/static/app.js"></script>\n</body>')
# Remove dummy JS
code = re.sub(r'<script>\s*// Toggle Panel.*?// Init.*?</script>', '', code, flags=re.DOTALL)

# Replace Stats
code = code.replace('data-target="14520">0</span>\n<a class="font-arbutus text-[9px] text-primary border-b border-primary pb-0.5 uppercase" href="#">Network Velocity</a>', 'id="statProcessed">0</span>\n<a class="font-arbutus text-[9px] text-primary border-b border-primary pb-0.5 uppercase" href="#">Processed</a>')
code = code.replace('data-target="82.4">0</span>\n<a class="font-arbutus text-[9px] text-on-surface-variant hover:text-primary transition-all duration-300 uppercase" href="#">Risk Aggregation</a>', 'id="statAccounts">0</span>\n<a class="font-arbutus text-[9px] text-on-surface-variant hover:text-primary transition-all duration-300 uppercase" href="#">Accounts</a>')
code = code.replace('data-target="14">0</span>\n<a class="font-arbutus text-[9px] text-on-surface-variant hover:text-primary transition-all duration-300 uppercase" href="#">Active Alerts</a>', 'id="statAlerts">0</span>\n<a class="font-arbutus text-[9px] text-on-surface-variant hover:text-primary transition-all duration-300 uppercase" href="#">Alerts</a>')

# Feed
code = code.replace('id="feed-body"', 'id="feedBody"')

# Alerts
code = re.sub(r'<div class="flex-1 overflow-y-auto p-3 space-y-3">.*?</div>\n</section>', '<div class="flex-1 overflow-y-auto p-3 space-y-3" id="alertBody">\n</div>\n</section>', code, flags=re.DOTALL)

# Graph
code = re.sub(r'<div class="absolute inset-0 flex items-center justify-center pointer-events-none opacity-60">.*?</div>\n</div>', """<div class="absolute inset-0 flex items-center justify-center pointer-events-none opacity-60" id="graphPlaceholder">
<div class="relative w-full h-full overflow-hidden flex flex-col items-center justify-center">
<span class="material-symbols-outlined text-[48px] text-outline-variant mb-4 breathing-node">hub</span>
<p class="font-arbutus text-[10px] uppercase tracking-[0.1em] text-on-surface-variant">Click an alert to visualize subgraph</p>
</div>
</div>
<div id="graphCanvas" class="absolute inset-0 w-full h-full z-10"></div>""", code, flags=re.DOTALL)

code = code.replace('<div class="absolute top-4 right-4 flex flex-col gap-2">', '<div class="absolute top-4 left-4 z-20"><div id="graphInfo" class="bg-surface-container-high/80 backdrop-blur-md px-3 py-1.5 rounded border border-outline-variant/30 font-data-mono text-[10px] text-primary">Select an alert</div></div>\n<div class="absolute top-4 right-4 flex flex-col gap-2 z-20">')

# Bottom panel
code = re.sub(r'<section class="h-\[200px\] mt-auto.*?</section>', """<section class="h-[200px] mt-auto border-t border-outline-variant/30 bg-surface-container-lowest/80 backdrop-blur-2xl flex flex-col translate-y-[160px]" id="investigationPanel" style="display:none; z-index: 50;">
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
<div class="flex-1 p-gutter overflow-y-auto animate-on-reveal" id="invContent">
</div>
</section>""", code, flags=re.DOTALL)

with open('frontend/index.html', 'w') as f:
    f.write(code)

