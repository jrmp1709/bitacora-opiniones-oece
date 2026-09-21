#!/usr/bin/env python3
"""Sugerencias de clasificación para las consultas nuevas (segunda opinión; no guarda nada).

La clasificación de la bitácora la hace Claude en la tarea programada: se descartó publicar
clasificaciones automáticas sin revisión para evitar errores. Este módulo solo sugiere.

Aprende de lo ya clasificado —las filas del Excel de la bitácora (hechas a mano) y las consultas de
gob.pe clasificadas antes— y a cada consulta nueva le asigna el tema y la categoría de sus vecinas
más parecidas (k vecinos más cercanos sobre TF-IDF del texto de la consulta y del asunto). La
categoría de obra se ajusta al marco, como en la bitácora: Ley 30225 → "Solo construcción" y
Ley 32069 → "Solo Constr/Diseño Constr.". Cada sugerencia trae su confianza (de 0 a 1).

Uso:
    python scripts/clasificador.py evaluar   # precisión, dejando fuera cada opinión (validación cruzada)
    python scripts/clasificador.py sugerir   # sugerencias para las opiniones sin clasificar (no guarda nada)
"""
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build  # noqa: E402  (diccionarios CAT, TEMA, OBRAS y la lectura del Excel)

GOBPE = os.path.join(ROOT, "data", "gobpe.json")
CLASIF = os.path.join(ROOT, "data", "clasificacion.json")
OPINIONES = os.path.join(ROOT, "data", "opiniones.json")
K = 9          # vecinas que votan
REVISAR = .45  # umbral de confianza que reporta la evaluación
OBRA_30225, OBRA_32069 = "Solo construcción", "Solo Constr/Diseño Constr."
OBRA = {"obra", "obras", "valori", "reside", "metrad"}  # raíces que delatan un contrato de obra

VACIAS = set("""a al algo ante antes asi aun cada como con contra cual cuales cuando de del desde donde
dos el ella ellas ello ellos en entre era es esa esas ese eso esos esta estas este esto estos fue ha han
hasta hay la las le les lo los mas me mi muy no nos o otra otras otro otros para pero por porque que quien
se sea segun ser si sin sino sobre son su sus tal tambien tan tanto un una unas uno unos y ya dicho dicha
dichos dichas debe deben puede pueden podria resulta corresponde caso casos forma respecto mismo misma
articulo numeral literal reglamento ley decreto supremo aprobado mediante modificatorias consulta
consultas entidad entidades normativa contrataciones estado publicas publica""".split())


def palabras(txt):
    """Raíces de seis letras sin palabras vacías: 'penalidades' y 'penalidad' cuentan igual."""
    t = unicodedata.normalize("NFD", txt or "").encode("ascii", "ignore").decode().lower()
    return [w[:6] for w in re.findall(r"[a-z]+", t) if len(w) >= 4 and w not in VACIAS]


def texto(consulta, asunto):
    """El asunto resume el tema de la opinión: pesa algo más que cada palabra suelta de la consulta."""
    return palabras(consulta) + palabras(asunto) * 2


def ejemplos():
    """Consultas ya clasificadas: (opinión, palabras, categoría, tema). Excel primero, luego gob.pe."""
    gob = json.load(open(GOBPE, encoding="utf-8"))["opiniones"]
    clas = json.load(open(CLASIF, encoding="utf-8")) if os.path.exists(CLASIF) else {}
    out = []
    if os.path.exists(OPINIONES):
        for r in json.load(open(OPINIONES, encoding="utf-8"))["rows"]:
            if r.get("src") == "x":
                key = f"{r['y']}-{r.get('s', 'OECE')}-{r['op']}"
                out.append((key, texto(r["q"], (gob.get(key) or {}).get("asunto")), r["c"], r["t"]))
    for key, cl in clas.items():
        g = gob.get(key)
        if not g:
            continue
        if isinstance(cl, dict):  # opinión ilegible: una sola ficha con su asunto
            out.append((key, texto("", g.get("asunto")), cl["asunto"]["c"], cl["asunto"]["t"]))
            continue
        for q, c in zip(g["consultas"] or [], cl):
            if c.get("omitir") or "auto" in c:  # solo aprende de lo revisado, no de sus propias conjeturas
                continue
            out.append((key, texto(q["q"], g.get("asunto")), c["c"], c["t"]))
    return out


class Modelo:
    def __init__(self, ejs):
        self.ejs = ejs
        df = Counter()
        for _, ws, _, _ in ejs:
            df.update(set(ws))
        self.n = len(ejs)
        self.idf = {w: math.log((1 + self.n) / (1 + d)) + 1 for w, d in df.items()}
        self.vecs = [self.vector(ws) for _, ws, _, _ in ejs]

    def vector(self, ws):
        tf = Counter(ws)
        v = {w: (1 + math.log(c)) * self.idf.get(w, math.log(1 + self.n) + 1) for w, c in tf.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norma for w, x in v.items()}

    def predecir(self, ws, marco, excluir=None):
        """(categoría, tema, confianza) por votación de las K vecinas más parecidas."""
        v = self.vector(ws)
        sims = []
        for i, u in enumerate(self.vecs):
            if excluir and self.ejs[i][0] == excluir:
                continue
            s = sum(x * u.get(w, 0.0) for w, x in v.items())
            if s > 0:
                sims.append((s, i))
        sims.sort(reverse=True)
        vecinas = sims[:K]
        if not vecinas:
            return OBRA_32069 if marco == "32069" else OBRA_30225, "Otros obras", 0.0
        votos_t = defaultdict(float)
        for s, i in vecinas:
            votos_t[self.ejs[i][3]] += s * s
        tema, peso = max(votos_t.items(), key=lambda x: x[1])
        conf = peso / sum(votos_t.values())
        # la categoría, entre las vecinas del mismo grupo (obras / selección) que el tema elegido
        obra = tema in build.OBRAS
        votos_c = defaultdict(float)
        for s, i in vecinas:
            if (self.ejs[i][3] in build.OBRAS) == obra:
                votos_c[self.ejs[i][2]] += s * s
        cat = max(votos_c.items(), key=lambda x: x[1])[0] if votos_c else self.ejs[vecinas[0][1]][2]
        if cat == "Bienes y Servicios" and OBRA & set(ws):  # la consulta habla de una obra: no es de bienes ni servicios
            cat = OBRA_30225
        if cat in (OBRA_30225, OBRA_32069):  # convención de la bitácora: la obra se separa por marco
            cat = OBRA_32069 if marco == "32069" else OBRA_30225
        return cat, tema, round(conf, 2)


def evaluar():
    """Deja fuera cada opinión de gob.pe clasificada, la predice con el resto y compara."""
    ejs = ejemplos()
    gob = json.load(open(GOBPE, encoding="utf-8"))["opiniones"]
    modelo = Modelo(ejs)
    ok_t = ok_c = n = seguras = ok_seguras = 0
    for key, ws, c, t in ejs:
        if key not in gob or key.startswith("2026-OECE") and not gob[key].get("consultas"):
            continue
        cat, tema, conf = modelo.predecir(ws, gob[key].get("marco"), excluir=key)
        n += 1
        ok_t += tema == t
        ok_c += cat == c
        if conf >= REVISAR:
            seguras += 1
            ok_seguras += tema == t
    print(f"Consultas evaluadas: {n} (cada opinión se predice sin verse a sí misma)")
    print(f"Tema acertado: {ok_t / n:.0%} · Categoría acertada: {ok_c / n:.0%}")
    print(f"Con confianza ≥ {REVISAR}: {seguras / n:.0%} de las consultas, y en ellas el tema acierta {ok_seguras / max(seguras, 1):.0%}")


def sugerir():
    """Imprime una sugerencia para cada consulta de las opiniones sin clasificar. No guarda nada."""
    gob = json.load(open(GOBPE, encoding="utf-8"))["opiniones"]
    clas = json.load(open(CLASIF, encoding="utf-8")) if os.path.exists(CLASIF) else {}
    en_excel = set()
    if os.path.exists(OPINIONES):
        en_excel = {f"{r['y']}-{r.get('s', 'OECE')}-{r['op']}" for r in json.load(open(OPINIONES, encoding="utf-8"))["rows"]
                    if r.get("src") == "x"}
    faltan = [k for k in gob if k not in clas and k not in en_excel]
    if not faltan:
        print("No hay opiniones sin clasificar.")
        return
    modelo = Modelo(ejemplos())
    print("Sugerencias (segunda opinión, no se guardan):")
    for k in faltan:
        g = gob[k]
        qs = g["consultas"] or [{"q": "", "m": None}]
        print(f"{k} · {g.get('asunto')}")
        for n, q in enumerate(qs, 1):
            cat, tema, conf = modelo.predecir(texto(q["q"], g.get("asunto")), q.get("m") or g.get("marco"))
            print(f"   {n}. {build.CAT[cat]} / {build.TEMA[tema]} (confianza {conf:.0%})")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("evaluar", "sugerir"):
        sys.exit(__doc__)
    evaluar() if sys.argv[1] == "evaluar" else sugerir()
