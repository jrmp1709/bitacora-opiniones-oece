#!/usr/bin/env python3
"""Validación antes de publicar.

1. Referencias de cada opinión nueva, comprobadas en gob.pe:
   - el título de su página trae el mismo número oficial que su clave (año, serie y número);
   - la página y el PDF son de gob.pe, responden, y el PDF es de verdad un PDF;
   - si el nombre del PDF trae número y año, son los de la opinión, y su prefijo es el id de la página;
   - la fecha existe, no es futura y es del año de la opinión;
   - tiene al menos una consulta legible (o su asunto) y una clasificación con códigos válidos;
   - el marco es coherente con la fecha: no hay consultas sobre la Ley 32069 antes de su publicación (24.06.2024).
   La que no pasa queda retenida en data/retenidas.json: build.py no la publica hasta que pase.
2. El conjunto generado (data/opiniones.json e index.html): campos completos, enlaces de gob.pe,
   fechas válidas, marcos conocidos, sin duplicados. Si algo falla, no se publica nada.

Uso:
    python scripts/validar.py nuevas CLAVE [CLAVE …]   # referencias de esas opiniones (en línea)
    python scripts/validar.py conjunto                  # el sitio generado (sin conexión)
    python scripts/validar.py todo [--en-linea]         # todas las opiniones de gob.pe (en línea: lento)
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build  # noqa: E402
import gobpe  # noqa: E402

GOBPE = os.path.join(ROOT, "data", "gobpe.json")
CLASIF = os.path.join(ROOT, "data", "clasificacion.json")
RETENIDAS = os.path.join(ROOT, "data", "retenidas.json")
OPINIONES = os.path.join(ROOT, "data", "opiniones.json")
INDEX = os.path.join(ROOT, "index.html")
PUBLICACION_32069 = "2024-06-24"  # antes de esa fecha la Ley 32069 no existía; entre su publicación y su vigencia
                                  # (22.04.2025) ya hubo consultas sobre ella, como la D000014-2025-OSCE-DTN
MARCOS = {"32069", "30225", "1017"}


def pedir(url, solo_inicio=False):
    """(código HTTP, primeros bytes) con las mismas reglas de gobpe.py: una solicitud por segundo,
    User-Agent del proyecto y, ante un bloqueo, se detiene sin intentar esquivarlo."""
    espera = gobpe.PAUSA - (time.time() - gobpe._ultima[0])
    if espera > 0:
        time.sleep(espera)
    gobpe._ultima[0] = time.time()
    cab = {"User-Agent": gobpe.UA}
    if solo_inicio:
        cab["Range"] = "bytes=0-2047"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=60) as r:
            return r.status, r.read(4096 if solo_inicio else 400000)
    except urllib.error.HTTPError as e:
        if e.code in (403, 418, 429):
            raise gobpe.Bloqueo(f"gob.pe respondió {e.code} en {url}; se detiene la validación")
        return e.code, b""
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return 0, str(e).encode()


def numero_oficial(key):
    anio, serie, op = key.split("-")
    return f"{op[0]}{int(op[1:]):06d}-{anio}-{serie}-DTN" if op.startswith("D") else f"{int(op):03d}-{anio}/DTN"


def problemas_opinion(key, g, cl, en_linea=True, con_clasif=True):
    """Lista de problemas de una opinión de gob.pe (vacía si está en orden). Sin clasificación que revisar
    (con_clasif=False) cuando la opinión la registra el Excel, que manda."""
    p = []
    anio, serie, op = key.split("-")
    esperado = numero_oficial(key)
    hoy = datetime.date.today().isoformat()
    # --- datos extraídos ---
    if g.get("oficial") != esperado:
        p.append(f"número oficial {g.get('oficial')!r} no coincide con {esperado!r}")
    if esperado not in (g.get("titulo") or ""):
        p.append(f"el título de la página ({g.get('titulo')!r}) no trae el número {esperado}")
    f = g.get("fecha")
    if not f or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f):
        p.append("sin fecha de la opinión")
    else:
        if f > hoy:
            p.append(f"fecha futura ({f})")
        if f[:4] != anio:
            p.append(f"fecha {f} fuera del año de la opinión ({anio})")
    pdf, url = g.get("pdf") or "", g.get("url") or ""
    if not pdf.startswith("https://cdn.www.gob.pe/uploads/document/file/"):
        p.append(f"el PDF no es de gob.pe: {pdf[:80]!r}")
    if not url.startswith("https://www.gob.pe/institucion/oece/informes-publicaciones/"):
        p.append(f"la página no es de gob.pe: {url[:80]!r}")
    pid = re.search(r"/informes-publicaciones/(\d+)-", url)
    nombre = pdf.rsplit("/", 1)[-1].split("?")[0].lower()
    m = re.match(r"(\d+)-opinion-(?:n-)?d?0*(\d+)-(\d{4})", nombre)
    if m:  # los PDF del OECE siguen el patrón; muchos de 2023 tienen nombres libres y no se exigen
        if pid and m.group(1) != pid.group(1):
            p.append(f"el PDF ({nombre}) no lleva el id de la página ({pid.group(1)})")
        if int(m.group(2)) != int(re.sub(r"\D", "", op)) or m.group(3) != anio:
            p.append(f"el nombre del PDF ({nombre}) corresponde a otra opinión")
    if not (g.get("consultas") or g.get("asunto")):
        p.append("sin consultas legibles ni asunto")
    # --- clasificación ---
    if not con_clasif:
        pass
    elif cl is None:
        p.append("sin clasificación")
    else:
        filas = [cl["asunto"]] if isinstance(cl, dict) else [c for c in cl if not c.get("omitir")]
        if not isinstance(cl, dict) and len(cl) != max(1, len(g.get("consultas") or [])):
            p.append("clasificaciones y consultas desalineadas")
        for c in filas:
            if c.get("c") not in build.CAT or c.get("t") not in build.TEMA:
                p.append(f"clasificación con códigos desconocidos: {c}")
            marco = c.get("m") or g.get("marco")
            if marco not in MARCOS:
                p.append(f"marco desconocido: {marco!r}")
            elif marco == "32069" and f and f < PUBLICACION_32069:
                p.append(f"marco Ley 32069 en una opinión del {f}, anterior a la publicación de esa ley")
    # --- en línea: que las referencias respondan de verdad ---
    if en_linea and pdf and url:
        cod, cuerpo = pedir(url)
        if cod != 200:
            p.append(f"la página de gob.pe responde {cod}")
        elif esperado not in cuerpo.decode("utf-8", "replace"):
            p.append("la página de gob.pe no menciona el número de la opinión")
        cod, cuerpo = pedir(pdf, solo_inicio=True)
        if cod not in (200, 206):
            p.append(f"el PDF responde {cod}")
        elif not cuerpo.startswith(b"%PDF"):
            p.append("el enlace del PDF no devuelve un PDF")
    return p


def nuevas(claves, en_linea=True):
    """Valida esas opiniones y actualiza data/retenidas.json. Devuelve {clave: [problemas]} de las retenidas."""
    gob = json.load(open(GOBPE, encoding="utf-8"))["opiniones"]
    clas = json.load(open(CLASIF, encoding="utf-8")) if os.path.exists(CLASIF) else {}
    ret = json.load(open(RETENIDAS, encoding="utf-8")) if os.path.exists(RETENIDAS) else {}
    malas = {}
    for k in claves:
        if k not in gob:
            continue
        prob = problemas_opinion(k, gob[k], clas.get(k), en_linea)
        if prob:
            malas[k] = prob
            ret[k] = {"desde": ret.get(k, {}).get("desde") or datetime.date.today().isoformat(), "problemas": prob}
            print(f"  RETENIDA {gob[k].get('oficial') or k}: " + "; ".join(prob))
        else:
            if k in ret:
                print(f"  liberada {gob[k]['oficial']}: ya pasa la validación")
            ret.pop(k, None)
            print(f"  válida   {gob[k]['oficial']}")
    with open(RETENIDAS, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dict(sorted(ret.items())), fh, ensure_ascii=False, indent=1)
    return malas


def conjunto():
    """Problemas del sitio generado. Sin conexión: revisa data/opiniones.json e index.html."""
    p = []
    d = json.load(open(OPINIONES, encoding="utf-8"))
    rows = d.get("rows") or []
    if len(rows) < 500:
        p.append(f"solo {len(rows)} consultas: el sitio quedaría incompleto")
    vistos, cats = set(), {k for k, _ in d.get("cats", [])}
    for r in rows:
        ident = f"{r.get('y')}-{r.get('s')}-{r.get('op')}"
        for campo in ("op", "y", "s", "o", "u", "f", "c", "t", "g", "q", "m", "src"):
            if not r.get(campo):
                p.append(f"{ident}: falta el campo {campo!r}")
        if r.get("m") not in MARCOS:
            p.append(f"{ident}: marco desconocido {r.get('m')!r}")
        if not str(r.get("u", "")).startswith("https://cdn.www.gob.pe/"):
            p.append(f"{ident}: PDF fuera de gob.pe")
        if r.get("h") and not str(r["h"]).startswith("https://www.gob.pe/"):
            p.append(f"{ident}: página fuera de gob.pe")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("f", ""))) or str(r.get("f")) > datetime.date.today().isoformat():
            p.append(f"{ident}: fecha no válida {r.get('f')!r}")
        if r.get("c") not in cats or r.get("t") not in d.get("temas", {}):
            p.append(f"{ident}: categoría o tema sin etiqueta")
        firma = (ident, r.get("q"), r.get("c"), r.get("t"))
        if firma in vistos:
            p.append(f"{ident}: consulta duplicada")
        vistos.add(firma)
    html = open(INDEX, encoding="utf-8").read()
    if "{{" in html:
        p.append("index.html tiene placeholders sin reemplazar")
    if '"rows":[' not in html:
        p.append("index.html no trae los datos")
    return p[:40]


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a[:1] == ["nuevas"] and len(a) > 1:
            sys.exit(1 if nuevas(a[1:]) else 0)
        elif a[:1] == ["conjunto"]:
            prob = conjunto()
            print("Conjunto: en orden" if not prob else "Conjunto con problemas:\n  " + "\n  ".join(prob))
            sys.exit(1 if prob else 0)
        elif a[:1] == ["todo"]:
            gob = json.load(open(GOBPE, encoding="utf-8"))["opiniones"]
            clas = json.load(open(CLASIF, encoding="utf-8"))
            n = 0
            for k, g in gob.items():
                prob = problemas_opinion(k, g, clas.get(k), en_linea="--en-linea" in a, con_clasif=k in clas)
                if prob:
                    n += 1
                    print(f"{g.get('oficial') or k}: " + "; ".join(prob))
            print(f"Opiniones con observaciones: {n} de {len(gob)}")
        else:
            sys.exit(__doc__)
    except gobpe.Bloqueo as b:
        sys.exit(f"DETENIDO: {b}")
