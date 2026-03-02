import urllib.request
import json

class SearchAgent:
    def __init__(self):
        self.id = "agent_search"
        self.strength = 1.0
        self.stop_words = [
            "и", "в", "на", "с", "а", "но", "что", "это", "как",
            "для", "по", "из", "от", "до", "за", "при", "или",
            "также", "который", "которая", "которые", "его", "её",
            "они", "она", "оно", "он", "то", "же", "бы", "не",
            "является", "может", "быть", "был", "была", "были"
        ]

    def is_online(self):
        try:
            req = urllib.request.Request(
                'https://ru.wikipedia.org',
                headers={'User-Agent': 'PROMETEUS/0.2 (educational project)'}
            )
            urllib.request.urlopen(req, timeout=3)
            return True
        except:
            return False

    def search(self, word):
        try:
            url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{urllib.request.quote(word)}"
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'PROMETEUS/0.2 (educational project)'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Пропускаем страницы-disambig и топонимы
                if data.get('type') == 'disambiguation':
                    return None

                # Пропускаем если это явно фильм, населённый пункт, альбом
                skip_keywords = [
                    'кинофильм', 'фильм', 'деревня', 'село', 'город',
                    'альбом', 'песня', 'округ', 'район', 'провинци',
                    'уезд', 'may refer', 'может означать'
                ]
                extract = data.get('extract', '')
                if any(kw in extract.lower() for kw in skip_keywords):
                    return None

                if extract:
                    sentences = extract.split('.')
                    short = '. '.join(sentences[:2]) + '.'
                    return short

            return None
        except:
            return None

    def extract_unknown(self, explanation, graph):
        tokens = explanation.lower().split()
        unknown = []

        # Суффиксы грамматических форм — не концепты
        bad_suffixes = [
            'ого', 'ему', 'ому', 'ого', 'ых', 'ими', 'ами',
            'ого', 'ей', 'ого', 'ства', 'ению', 'ания', 'ения',
            'ости', 'ьных', 'ьные', 'ьной', 'ьного',
            'ымых', 'овых', 'евых', 'ивых'
        ]

        for token in tokens:
            clean = token.strip('.,;:()-—»«"\'')
            if (clean
                and len(clean) > 4
                and clean not in self.stop_words
                and not graph.find(clean)
                and clean.isalpha()
                and not any(clean.endswith(s) for s in bad_suffixes)
            ):
                unknown.append(clean)

        return list(set(unknown))

    def enrich(self, word, explanation, graph, learn_func, console, depth=2, visited=None):
        if visited is None:
            visited = set()

        if depth == 0 or word in visited:
            return

        visited.add(word)

        # Находим незнакомые слова в объяснении
        unknown = self.extract_unknown(explanation, graph)

        if unknown:
            console.print(f"[dim]Глубина {depth} — изучаю: {unknown}[/dim]")

        for token in unknown:
            if token in visited:
                continue

            result = self.search(token)
            if result:
                console.print(f"[dim]  → Нашёл '{token}': {result[:80]}...[/dim]")

                # Добавляем в граф
                graph.add_concept(token)
                result_tokens = result.lower().split()
                for t in result_tokens:
                    clean = t.strip('.,;:()-—»«"\'')
                    if graph.find(clean) and clean != token:
                        graph.add_relation(token, clean, "СВЯЗАН_С", weight=0.6)

                # Сохраняем
                learn_func(token, result, graph)

                # Рекурсивно идём глубже
                self.enrich(token, result, graph, learn_func, console, depth - 1, visited)