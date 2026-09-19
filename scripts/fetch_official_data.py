"""Download only PS1's public data. Never execute code from the source repository."""
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'aochinwen/NebulaX-Hackathon-ProblemStatement'
def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'PLiZ-Hackathon'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()

def main():
    commit = json.loads(fetch(f'https://api.github.com/repos/{REPO}/commits/main'))['sha']
    tree = json.loads(fetch(f'https://api.github.com/repos/{REPO}/git/trees/{commit}?recursive=1'))['tree']
    files = [item['path'] for item in tree if item['type'] == 'blob' and (
        item['path'].startswith('PS1/01_data/') or item['path'].startswith('PS1/03_submission_sample/')
        or item['path'] == 'PS1/PS1_README.md')]
    manifest = {'repository': f'https://github.com/{REPO}', 'commit': commit,
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'description': 'Official organiser-provided synthetic hackathon instance; not live railway operations.', 'files': []}
    for name in files:
        payload = fetch(f'https://raw.githubusercontent.com/{REPO}/{commit}/{name}')
        destination = ROOT / 'data' / 'official' / name.removeprefix('PS1/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        manifest['files'].append({'path': name, 'sha256': hashlib.sha256(payload).hexdigest()})
    (ROOT / 'data' / 'official' / 'provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Downloaded {len(files)} official PS1 files at {commit[:12]}')

if __name__ == '__main__': main()
