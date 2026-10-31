"""
Ranked bar chart of drugs per administration route, S5c subnetwork.
Input: Neo4j export of
    MATCH (d:Drug)-[:has_administration]->(a:AdminRoute)
    RETURN a.name AS route, count(DISTINCT d) AS drugs ORDER BY drugs DESC;
    python3 route_barchart.py routes_per_drug.csv   # -> route_barchart.pdf/.svg
"""
import csv, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

path = sys.argv[1] if len(sys.argv) > 1 else 'routes_per_drug.csv'
rows = sorted(((r['route'], int(r['drugs'])) for r in csv.DictReader(open(path))),
              key=lambda r: (-r[1], r[0]))
routes, counts = zip(*rows)
print(f"{len(rows)} routes, {sum(counts)} drug-route pairs")

fig, ax = plt.subplots(figsize=(7.2, 3.1))
x = range(len(routes))
bars = ax.bar(x, counts, width=0.75, color='#E67E22', edgecolor='none')
ax.set_yscale('log')
ax.set_ylim(0.8, max(counts) * 2.2)
for i, c in enumerate(counts[:3]):
    ax.text(i, c * 1.12, f'{c:,}', ha='center', va='bottom', fontsize=6.5, color='#333333')
ax.set_xticks(list(x))
ax.set_xticklabels(routes, rotation=70, ha='right', rotation_mode='anchor', fontsize=6.5)
ax.set_xlim(-1.2, len(routes) - 0.3)
ax.set_ylabel('Drugs (log scale)', fontsize=8.5)
ax.tick_params(axis='y', labelsize=7.5)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
ax.grid(axis='y', color='#DDDDDD', lw=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
for ext in ('pdf', 'svg'):
    fig.savefig(f'route_barchart.{ext}', bbox_inches='tight', pad_inches=0.03)
print('saved route_barchart.pdf and .svg')