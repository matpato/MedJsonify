"""
Top drugs by number of linked diseases (degree in the S5a drug-disease
subnetwork), split into has_indication (green) and has_contraindication (red).
Input: Neo4j export of the query
    MATCH (d:Drug)-[r:has_indication|has_contraindication]->(:Disease)
    RETURN d.name AS drug, d.id AS id,
      sum(CASE type(r) WHEN 'has_indication' THEN 1 ELSE 0 END) AS indications,
      sum(CASE type(r) WHEN 'has_contraindication' THEN 1 ELSE 0 END) AS contraindications,
      count(r) AS degree ORDER BY degree DESC LIMIT 20;
    python3 degree_barchart.py drug_degrees.csv   # -> degree_barchart.pdf/.svg
"""
import csv, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

path = sys.argv[1] if len(sys.argv) > 1 else 'drug_degrees.csv'
rows = list(csv.DictReader(open(path)))
rows.sort(key=lambda r: (-int(r['degree']), r['drug']))
names = [f"{r['drug'].lower()} ({r['id']})" for r in rows]
ind = [int(r['indications']) for r in rows]
ci = [int(r['contraindications']) for r in rows]

fig, ax = plt.subplots(figsize=(7.0, 4.6))
y = list(range(len(rows)))[::-1]
ax.barh(y, ind, height=0.72, color='#27AE60', edgecolor='none')
ax.barh(y, ci, left=ind, height=0.72, color='#C0392B', edgecolor='none')
for yi, a, b in zip(y, ind, ci):
    ax.text(a + b + 0.6, yi, str(a + b), va='center', fontsize=7, color='#333333')
ax.set_yticks(y)
ax.set_yticklabels(names, fontsize=7.5)
ax.set_xlabel('Linked diseases (degree)', fontsize=8.5)
ax.tick_params(axis='x', labelsize=7.5)
ax.set_xlim(0, max(a + b for a, b in zip(ind, ci)) * 1.08)
ax.set_ylim(-0.6, len(rows) - 0.4)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
ax.grid(axis='x', color='#DDDDDD', lw=0.6)
ax.set_axisbelow(True)
ax.legend(handles=[Patch(color='#27AE60', label='has_indication'),
                   Patch(color='#C0392B', label='has_contraindication')],
          loc='lower right', fontsize=7.5, frameon=False)
fig.tight_layout()
for ext in ('pdf', 'svg'):
    fig.savefig(f'degree_barchart.{ext}', bbox_inches='tight', pad_inches=0.03)
print('saved degree_barchart.pdf and .svg')