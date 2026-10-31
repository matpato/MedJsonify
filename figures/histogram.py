"""
Histogram of drugs (active ingredients) per approval year, S5b subnetwork.
Input: Neo4j export of
    MATCH (d:Drug)-[:has_approved_year]->(y:ApprovalYear)
    RETURN y.year AS year, count(DISTINCT d) AS drugs ORDER BY year;
    python3 approval_histogram.py drugs_per_year.csv   # -> approval_histogram.pdf/.svg
"""
import csv, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

path = sys.argv[1] if len(sys.argv) > 1 else 'drugs_per_year.csv'
rows = [(int(r['year']), int(r['drugs'])) for r in csv.DictReader(open(path))]
years, counts = zip(*rows)
print(f"{len(rows)} years, {sum(counts)} drug-year pairs, max {max(counts)} in {years[counts.index(max(counts))]}")

fig, ax = plt.subplots(figsize=(7.2, 2.8))
colors = ['#E84393' if y < 2025 else '#F5A3C7' for y in years]
ax.bar(years, counts, width=0.85, color=colors, edgecolor='none')
ax.axvline(1981.5, color='#555555', ls='--', lw=0.8)
ax.text(1981.0, max(counts) * 0.93, 'Orange Book dates\nstart in 1982', ha='right',
        va='top', fontsize=7.5, color='#555555')
ax.annotate('2025: January–May only', xy=(2025, counts[-1] + 2), xytext=(2008, max(counts) * 0.97),
            ha='center', va='top', fontsize=7.5, color='#555555',
            arrowprops=dict(arrowstyle='-', color='#999999', lw=0.6))
ax.set_xlim(min(years) - 1.5, max(years) + 1.5)
ax.set_xlabel('Approval year', fontsize=9)
ax.set_ylabel('Drugs', fontsize=9)
ax.tick_params(labelsize=8)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
ax.grid(axis='y', color='#DDDDDD', lw=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
for ext in ('pdf', 'svg'):
    fig.savefig(f'approval_histogram.{ext}', bbox_inches='tight', pad_inches=0.03)
print('saved approval_histogram.pdf and .svg')