"""
Запусти один раз: python fix_knowledge.py
Дозаписывает description в base.json для концептов у которых его нет
"""
import json
import urllib.request

def fetch_wiki(word):
    try:
        url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{urllib.request.quote(word)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'PROMETEUS/0.2'})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode('utf-8'))
            if data.get('type') == 'disambiguation':
                return None
            extract = data.get('extract', '')
            skip = ['кинофильм', 'фильм', 'деревня', 'село', 'альбом', 'песня']
            if any(k in extract.lower() for k in skip):
                return None
            if extract:
                sentences = extract.split('.')
                return '. '.join(sentences[:2]) + '.'
    except:
        return None

with open("knowledge/base.json", "r", encoding="utf-8") as f:
    data = json.load(f)

fixed = 0
for concept in data["concepts"]:
    if "description" not in concept and "name" in concept:
        name = concept["name"]
        print(f"Ищу описание для '{name}'...", end=" ")
        desc = fetch_wiki(name)
        if desc:
            concept["description"] = desc
            print(f"✓")
            fixed += 1
        else:
            print(f"не найдено")

with open("knowledge/base.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\nГотово! Обновлено концептов: {fixed}")