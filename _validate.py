import yaml
with open('sources.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
print(f"Valid YAML ✓ — {len(data['sources'])} sources:")
for s in data['sources']:
    print(f"  {s['name']:15s} | {s['type']:3s} | {s['language']:2s} | {s['url']}")
