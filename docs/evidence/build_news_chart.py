"""Reproduce a chart of published CNA figures. No demo or app data is used.

Run with a Python environment containing matplotlib.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent
SOURCE = 'https://www.channelnewsasia.com/singapore/circle-line-ccl-disruption-3-month-shuttle-buses-train-faq-5863851'
DATA = [
    {'section': 'HarbourFront to Paya Lebar\n(peak hours)', 'usual_minutes': 2, 'reported_works_minutes': 3},
    {'section': 'Paya Lebar to Mountbatten\n(shuttle during works)', 'usual_minutes': 3, 'reported_works_minutes': 10},
    {'section': 'Mountbatten to Dhoby Ghaut\nor Marina Bay', 'usual_minutes': 6, 'reported_works_minutes': 10},
]

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.spines.left': False, 'axes.edgecolor': '#c9d3cf',
                     'text.color': '#213e34', 'axes.labelcolor': '#213e34',
                     'xtick.color': '#4f6259', 'ytick.color': '#213e34',
                     'svg.fonttype': 'none'})
fig, ax = plt.subplots(figsize=(12, 6.9), facecolor='white')
fig.subplots_adjust(left=.30, right=.93, top=.72, bottom=.24)
fig.text(.04, .94, 'Maintenance access has a passenger cost', fontsize=22, weight='bold')
fig.text(.04, .885, 'Circle Line service intervals announced for tunnel strengthening works', fontsize=13)
fig.text(.04, .835, 'Singapore | CNA, 17 January 2026 (updated 23 January)', fontsize=11, color='#586a61')
y = np.arange(len(DATA))
for offset, field, color, label in [(-.18, 'usual_minutes', '#216c59', 'Usual service'),
                                    (.18, 'reported_works_minutes', '#ba6b31', 'During works (reported)')]:
    bars = ax.barh(y + offset, [r[field] for r in DATA], height=.29, color=color, label=label)
    ax.bar_label(bars, labels=[f'{r[field]} min' for r in DATA], padding=8, fontsize=12)
ax.set_yticks(y, [r['section'] for r in DATA])
ax.invert_yaxis()
ax.tick_params(axis='y', length=0, pad=13)
ax.set_xlim(0, 11.5)
ax.set_xticks([0, 2, 4, 6, 8, 10])
ax.set_xlabel('Time between trains (minutes)', labelpad=10)
ax.set_axisbelow(True)
ax.xaxis.grid(True, color='#e5eae7', linewidth=.7)
ax.legend(frameon=False, loc='lower left', bbox_to_anchor=(-.01, 1.025), ncol=2, fontsize=11)
fig.text(.04, .13, 'Reported operating plan, not measured waiting times or current service conditions.', fontsize=10, color='#586a61')
fig.text(.04, .095, 'This illustrates the trade-off in allocating track access; it does not measure manual planning time.', fontsize=10, color='#586a61')
fig.text(.04, .05, 'Source: CNA, “Taking the Circle Line? What to expect during the scheduled 3-month disruption”.', fontsize=9, color='#586a61', url=SOURCE)
for ext in ['png', 'svg']:
    fig.savefig(OUT / f'cna-circle-line-access-impact.{ext}', dpi=180, facecolor='white')
plt.close(fig)
(OUT / 'news-chart-data.json').write_text(json.dumps({
    'source_url': SOURCE, 'published': '2026-01-17', 'updated': '2026-01-23',
    'data_type': 'Published expected service intervals during planned maintenance; not observed outcomes',
    'unit': 'minutes between trains', 'values': DATA,
    'caveats': ['Usual and works services differ; the central section uses a shuttle.',
                'This is a historical announced plan, not current service information.',
                'No PLiZ results or time savings are represented.']
}, indent=2), encoding='utf-8')
print('Created PNG, SVG and source data in', OUT)
