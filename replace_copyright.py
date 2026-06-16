from pathlib import Path

root = Path('c:\\Users\\Bi\\Desktop\\Weather App')
patterns = [
    ('Copyright &copy; 2014-2026', 'Copyright &copy; 2026'),
    ('Copyright © 2014-2026', 'Copyright © 2026'),
]
changed = []
for path in root.rglob('*.html'):
    text = path.read_text(encoding='utf-8')
    new_text = text
    for old, new in patterns:
        new_text = new_text.replace(old, new)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        changed.append(path)
        print(f'Updated: {path}')
print(f'Files updated: {len(changed)}')
