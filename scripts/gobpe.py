#!/usr/bin/env python3
"""Descarga y extrae las opiniones de la DTN (OSCE / OECE) publicadas en gob.pe.

Uso:
    python scripts/gobpe.py actualizar            # descubrir + descargar + extraer, y cuántas faltan clasificar
                                                  # (el ciclo completo con validación: scripts/actualizar.py)
    python scripts/gobpe.py descubrir             # nuevas opiniones: primera página de la colección del OECE
    python scripts/gobpe.py descubrir --sitemaps  # todas: recorre los sitemaps de gob.pe (lento, solo la carga inicial)
    python scripts/gobpe.py descargar 2023 2024   # páginas y PDF pendientes de esos años (sin años: todos los del índice)
    python scripts/gobpe.py extraer               # arma data/gobpe.json con lo descargado
    python scripts/gobpe.py pendientes [N]        # opiniones sin clasificar, con los códigos de categoría y tema
    python scripts/gobpe.py clasificar lote.txt   # guarda en data/clasificacion.json las líneas "CLAVE: C?/T? ; …"

Buenas prácticas con gob.pe: se respeta su robots.txt (no se recorren las páginas "?sheet="), se hace
una solicitud por segundo con un User-Agent que identifica al proyecto, y todo queda en caché
(cache/paginas y cache/texto) para no descargar dos veces. De cada PDF solo se guarda el texto.
Si gob.pe responde con un bloqueo (403, 418, 429), el script se detiene: no se intenta esquivarlo.

Requiere: pip install pypdf
"""
import datetime
import gzip
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")
INDICE = os.path.join(ROOT, "data", "gobpe_indice.json")
SALIDA = os.path.join(ROOT, "data", "gobpe.json")
UA = "BitacoraOpiniones/1.0 (indice publico de opiniones de la DTN; +https://jrmp1709.github.io/bitacora-opiniones-oece/)"
COLECCION = "https://www.gob.pe/institucion/oece/colecciones/66839-opiniones-de-la-direccion-tecnico-normativa-oece"
PAUSA = 1.0  # segundos entre solicitudes
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "setiembre": 9, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}

# Slug de la página: 7626891-opinion-n-d000001-2026-oece-dtn | 3828057-opinion-n-001-2023-dtn
SLUG = re.compile(r"/informes-publicaciones/(\d+)-opinion-n-(d?)0*(\d+)-(20\d\d)-(?:(oece|osce)-)?dtn$")


class Bloqueo(Exception):
    pass


_ultima = [0.0]


def get(url):
    espera = PAUSA - (time.time() - _ultima[0])
    if espera > 0:
        time.sleep(espera)
    for intento in range(3):
        _ultima[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 418, 429):
                raise Bloqueo(f"gob.pe respondió {e.code} en {url}; se detiene la descarga")
            if e.code == 404:
                return None
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        time.sleep(5 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {err}")


def entrada(url, pid=None):
    """Datos de una opinión a partir de la URL de su página, o None si no es una opinión de la DTN."""
    m = SLUG.search(url)
    if not m:
        return None
    pid, d, num, anio, inst = m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5)
    serie = (inst or "osce").upper()
    if d:
        codigo, oficial = f"D{num:03d}", f"D{num:06d}-{anio}-{serie}-DTN"
    else:  # formato del OSCE hasta 2024: Opinión N° 001-2023/DTN
        codigo, oficial = f"{num:03d}", f"{num:03d}-{anio}/DTN"
    url = "https://www.gob.pe" + url[url.index("/institucion/"):]
    return {"id": int(pid), "url": url, "anio": anio, "serie": serie, "num": num, "op": codigo, "oficial": oficial}


def clave(e):
    return f"{e['anio']}-{e['serie']}-{e['op']}"


def cargar_indice():
    return json.load(open(INDICE, encoding="utf-8")) if os.path.exists(INDICE) else {}


def guardar_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)


def descubrir(sitemaps=False):
    indice = cargar_indice()
    antes = len(indice)
    urls = []
    if sitemaps:
        raiz = get("https://www.gob.pe/sitemaps/sitemap.xml.gz")
        partes = re.findall(rb"<loc>([^<]+)</loc>", gzip.decompress(raiz))
        for i, loc in enumerate(partes, 1):
            data = gzip.decompress(get(loc.decode()))
            urls += [u.decode() for u in re.findall(rb"<loc>([^<]*/informes-publicaciones/\d+-opinion-n-[^<]+)</loc>", data)]
            print(f"  sitemap {i}/{len(partes)}", end="\r", flush=True)
        print()
    else:
        pagina = get(COLECCION).decode("utf-8", "replace")
        urls = re.findall(r'href="([^"]*/informes-publicaciones/\d+-opinion-n-[^"#?]+)"', pagina)
    for u in urls:
        e = entrada(u)
        if e and clave(e) not in indice:
            indice[clave(e)] = e
    guardar_json(INDICE, dict(sorted(indice.items())))
    print(f"Índice: {len(indice)} opiniones ({len(indice) - antes} nuevas)")
    return len(indice) - antes


def fecha(texto):
    m = re.search(r"(\d{1,2}) de ([a-záéíóú]+) de (\d{4})", texto, re.I)
    if m and m.group(2).lower() in MESES:
        return datetime.date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1))).isoformat()
    return None


def leer_pagina(e):
    """Título, fecha y enlace al PDF de la página de la opinión (la sumilla no se usa: nombra al solicitante)."""
    ruta = os.path.join(CACHE, "paginas", f"{e['id']}.json")
    if os.path.exists(ruta):
        return json.load(open(ruta, encoding="utf-8"))
    crudo = get(e["url"])
    if crudo is None:
        return None
    s = crudo.decode("utf-8", "replace")
    titulo = re.search(r"<title>\s*(.*?)\s*-\s*Informes y publicaciones", s, re.S)
    texto = html.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"<(script|style).*?</\1>", "", s, flags=re.S)))
    lineas = [x.strip() for x in texto.splitlines() if x.strip()]
    # La fecha va justo después del tipo de documento ("Opinión") en la cabecera de la publicación
    f = None
    for i, x in enumerate(lineas):
        if x == "Opinión" and i + 1 < len(lineas) and fecha(lineas[i + 1]):
            f = fecha(lineas[i + 1])
            break
    pdfs = re.findall(r'href="(https://cdn\.www\.gob\.pe/uploads/document/file/[^"]+\.pdf[^"]*)"', s)
    datos = {"titulo": html.unescape(titulo.group(1)).strip() if titulo else None, "fecha": f,
             "pdf": html.unescape(pdfs[0]) if pdfs else None}
    guardar_json(ruta, datos)
    return datos


def leer_pdf(e, pdf_url):
    ruta = os.path.join(CACHE, "texto", f"{e['id']}.txt")
    if os.path.exists(ruta):
        return open(ruta, encoding="utf-8").read()
    from pypdf import PdfReader
    crudo = get(pdf_url)
    if crudo is None:
        return None
    texto = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(crudo)).pages)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)
    return texto


def descargar(anios):
    indice = cargar_indice()
    # lo ya extraído en data/gobpe.json no se vuelve a bajar, aunque falte la caché (p. ej. en otra PC)
    hechas = json.load(open(SALIDA, encoding="utf-8"))["opiniones"] if os.path.exists(SALIDA) else {}
    pendientes = [e for e in indice.values() if (not anios or e["anio"] in anios) and clave(e) not in hechas
                  and not os.path.exists(os.path.join(CACHE, "texto", f"{e['id']}.txt"))]
    print(f"Por descargar: {len(pendientes)} opiniones")
    for i, e in enumerate(sorted(pendientes, key=lambda x: x["id"]), 1):
        p = leer_pagina(e)
        if not p or not p["pdf"]:
            print(f"  {clave(e)}: sin página o sin PDF")
            continue
        leer_pdf(e, p["pdf"])
        print(f"  {i}/{len(pendientes)} {e['oficial']}", flush=True)


# ---------- extracción del texto del PDF ----------
# Cabeceras y pies que se repiten en cada página del PDF (firma digital, n.° de página, clave de verificación)
RUIDO = re.compile(
    r"^\s*(Pág\. \d+ de \d+|Esta es una copia auténtica.*|Contrataciones Públicas Eficientes\s+aplicando.*|"
    r"Organismo Supervisor de las Contrataciones del Estado\s+aplicando.*|"
    r"Complementaria Final del D\.S\..*|dirección web: https?://\S+.*|Documento electrónico firmado.*|"
    r"integridad del documento y la autoría.*|.*validador.*|Dirección Técnico Normativa|Opinión|[A-Z0-9]{7}|"
    r"Firmado digitalmente por.*|.*\bFAU\b.*|\d{11} (?:soft|hard)|Motivo: .*|Fecha: \d\d\.\d\d\.\d{4}.*|"
    r"(?:del Estado\s+)?aplicando lo dispuesto por el Art\. ?25 de D\.S\..*|.*Su autenticidad e integridad pueden ser.*|"
    r"026-\s?2016-PCM.*|dirección web:.*)\s*$")
# Encabezados de sección, en mayúsculas y solos en su línea ("2. CONSULTAS1 Y ANÁLISIS", "3. CONCLUSIONES";
# a veces sin número o con el número errado, y con la llamada a pie de página pegada o separada)
SEC2 = re.compile(r"(?m)^[ \t]*(?:\d\.?[ \t]+)?CONSULTAS?[ \t]*\d*[ \t]*Y[ \t]+AN[AÁ]LISIS[^\n]*\n")
SEC3 = re.compile(r"(?m)^[ \t]*(?:(?:\d|[IVX]{1,4})\.?[ \t]+)?CONCLUSI[OÓ]N(?:ES)?\.?[ \t]*\d*[ \t]*\n")
TOP = re.compile(r"(?m)^[ \t]*2\.(\d{1,2})\.?(?:[ \t]+(?=\S)|[ \t]*\n|(?=[“\"]))")  # 2.1  2.2  … (una consulta cada uno)
SUB = re.compile(r"(?m)^[ \t]*2\.\d{1,2}\.\d{1,2}\.?(?:[ \t]+|(?=[A-ZÁÉÍÓÚ¿“\"]))")  # 2.1.1 … (análisis)
# "la consulta formulada es la siguiente:" / "las consultas formuladas son las siguientes:"
INTRO = re.compile(r"consultas?\s+(?:formulad[ao]s?|planteadas?|realizadas?)?\s*(?:es|son)\s+las?\s+siguientes?\s*:?", re.I)


def limpiar(texto):
    return "\n".join(ln for ln in texto.splitlines() if not RUIDO.match(ln))


def espacios(s):
    return re.sub(r"\s+", " ", s).strip()


def extraer_asunto(t):
    m = (re.search(r"\bAsunto\s*:\s*(.+?)\n\s*Referencia\s*:", t, re.S | re.I)
         or re.search(r"\bAsunto\s*:\s*(.+?)\n\s*\n", t, re.S | re.I))
    return espacios(m.group(1)) if m else None


def texto_consulta(s):
    """Texto de la consulta tal como la cita la opinión: solo se normalizan espacios y se quitan las comillas.
    La cita termina en la comilla de cierre que sigue a "?" o "." (lo que viene después, como "(sic)",
    una llamada a pie de página o el inicio del análisis, no es parte de la consulta)."""
    s = espacios(s).lstrip(" “\"'‘")
    # Nota con la que la DTN explica que no absuelve una consulta sobre un caso concreto: no es parte de la consulta
    s = re.split(r"[\s”\"’.]*Sobre el particular,? debe (?:mencionarse|reiterarse|indicarse|precisarse) que las opiniones", s)[0]
    # …y el análisis de la DTN, cuando el PDF lo pega a la consulta sin el número de apartado. Se cortan solo
    # las fórmulas en tercera persona con las que la DTN empieza a analizar, no las del solicitante
    # ("Al respecto, solicitamos…"), que sí son parte de la consulta.
    s = re.split(r"\s+[”\"]?\s*(?:Como se (?:anotó|indicó|ha indicado|mencionó|señaló|ha señalado)\b"
                 r"|(?:Al respecto|Sobre el particular),?\s+(?:se debe tener en cuenta|cabe (?:señalar|indicar|precisar|mencionar)"
                 r"|debe (?:señalarse|indicarse|precisarse|tenerse|mencionarse))\b)", s)[0]
    m = (re.search(r"^(.*?)\s?[”\"’]+\s*[(\[](?:sic|Sic|SIC)\.?[)\]]", s)  # “…” (sic) cierra la cita
         or re.search(r"^(.*?[?.])\s?(?:[”\"]|’’)", s))
    if m:
        s = m.group(1)
    elif "?" in s:  # consulta sin comillas: si tras la última pregunta sigue un texto largo, es el análisis
        m = re.search(r"^(.*\?)\s+(.*)$", s)
        if m and len(m.group(2)) > 200 and "?" not in m.group(2):
            s = m.group(1)
    s = re.sub(r"[\s”\"’]*[(\[](?:sic|Sic|SIC)\.?[)\]]\.?$", "", s).rstrip(" ”\"'’")
    return s if 10 < len(s) < 3000 else None


def extraer_consultas(t):
    """Las consultas abren los apartados 2.1, 2.2… del análisis; si hay una sola, va citada tras "la consulta
    formulada es la siguiente" y los apartados 2.1, 2.2… son el análisis."""
    a = SEC2.search(t)
    if not a:
        return []
    b = SEC3.search(t, a.end())
    bloque = t[a.end():b.start() if b else len(t)]
    # Notas al pie que el PDF intercala en el texto al cambiar de página: van entre líneas en blanco y empiezan
    # con su número y un espacio ("1 Realizadas mediante…"), a diferencia de los apartados ("2.1.")
    bloque = re.sub(r"\n[ \t]*\n[ \t]*\d{1,2}[ \t]+\S[^\n]*(?:\n(?![ \t]*\n)(?![ \t]*(?:\d{1,2}[ \t]*\n|2\.\d))[^\n]*)*",
                    "\n", bloque)
    bloque = re.sub(r"(?m)^[ \t]*\d{1,2}[ \t]*\n", "", bloque)  # números de página
    intro = INTRO.search(bloque)
    tops = list(TOP.finditer(bloque, intro.end() if intro else 0))
    unica = bool(intro) and "consultas" not in intro.group(0).lower()
    if intro:
        pre = bloque[intro.end():tops[0].start() if tops else len(bloque)]
        if len(pre.strip()) > 20:
            # Las consultas van citadas antes de los apartados, que entonces son el análisis (2.1, 2.2…)
            partes = re.split(r"[”\"’]+\s*(?:[(\[](?:sic|Sic|SIC)\.?[)\]]\.?)?\s*\n\s*(?=[“\"‘])", pre)
            cs = [c for c in (texto_consulta(p) for p in partes) if c]
            return cs[:1] if unica else cs
        # si no, cada consulta abre un apartado 2.1, 2.2… (y su análisis, 2.1.1…)
    consultas = []
    for i, m in enumerate(tops):
        if int(m.group(1)) != len(consultas) + 1:
            continue
        fin = min([x for x in (SUB.search(bloque, m.end()), tops[i + 1] if i + 1 < len(tops) else None) if x],
                  key=lambda x: x.start(), default=None)
        c = texto_consulta(bloque[m.end():fin.start() if fin else len(bloque)])
        if c:
            consultas.append(c)
        if unica:
            break
    return consultas


def extraer_conclusiones(t):
    b = SEC3.search(t)
    if not b:
        return []
    resto = t[b.end():]
    corte = re.search(r"\n\s*(Firmado por|Atentamente|Jesús María,|Lima,)", resto)
    resto = resto[:corte.start()] if corte else resto
    partes = re.split(r"(?m)^[ \t]*3\.(\d{1,2})\.?[ \t]+", resto)
    return [espacios(partes[i + 1]) for i in range(1, len(partes) - 1, 2)] or ([espacios(resto)] if resto.strip() else [])


def marco_probable(texto, e, umbral=2):
    """Marco normativo que aplica la opinión o la consulta. Hasta abril de 2025 (OSCE) rige la Ley 30225, salvo que
    se trate de contratos del D.L. 1017; en el OECE, la consulta puede referirse a la Ley 32069 o a la anterior Ley.
    `umbral`: menciones del D.L. 1017 que bastan (en el texto de una consulta, una sola)."""
    if len(re.findall(r"Decreto Legislativo N[°º.]*\s*1017|D\.\s?L\.\s*N?[°º.]*\s*1017", texto)) >= umbral:
        return "1017"
    if e["serie"] == "OSCE":
        return "30225"
    viejo = len(re.findall(r"30225|344-\s?2018|anterior\s+(?:Ley|Reglamento|normativa)", texto, re.I))
    nuevo = len(re.findall(r"32069|009-\s?2025|Ley General de Contrataciones", texto, re.I))
    return "30225" if viejo > nuevo else "32069"


def extraer():
    indice = cargar_indice()
    previas = json.load(open(SALIDA, encoding="utf-8"))["opiniones"] if os.path.exists(SALIDA) else {}
    salida = {}
    for k, e in sorted(indice.items()):
        pag = os.path.join(CACHE, "paginas", f"{e['id']}.json")
        txt = os.path.join(CACHE, "texto", f"{e['id']}.txt")
        if not (os.path.exists(pag) and os.path.exists(txt)):
            if k in previas:  # sin caché (p. ej. en otra PC): se conserva lo ya extraído
                salida[k] = previas[k]
            continue
        p = json.load(open(pag, encoding="utf-8"))
        t = limpiar(open(txt, encoding="utf-8").read())
        concl = extraer_conclusiones(t)
        salida[k] = dict(e, fecha=p["fecha"], pdf=p["pdf"], titulo=p["titulo"], asunto=extraer_asunto(t),
                         consultas=[{"q": q, "m": marco_probable(q, e, umbral=1) if re.search(
                             r"30225|32069|344-\s?2018|009-\s?2025|anterior|1017", q, re.I) else None}
                             for q in extraer_consultas(t)],
                         conclusiones=len(concl), concl=concl, marco=marco_probable(" ".join(concl) or t, e))
    guardar_json(SALIDA, {"actualizado": datetime.date.today().isoformat(), "opiniones": salida})
    sin = [k for k, v in salida.items() if not v["consultas"]]
    print(f"Extraídas: {len(salida)} opiniones, {sum(len(v['consultas']) for v in salida.values())} consultas")
    if sin:
        print(f"Sin consultas reconocidas ({len(sin)}): {', '.join(sin[:30])}{' …' if len(sin) > 30 else ''}")
    return salida


# ---------- clasificación (etapa, categoría y tema, con la taxonomía de la bitácora) ----------
CLASIF = os.path.join(ROOT, "data", "clasificacion.json")


def codigos():
    """Códigos cortos para clasificar: C1… (categorías, en el orden del ciclo) y T1… (temas)."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build
    cats = list(build.CAT)
    temas = [t for t in build.TEMA if t != "Evaluac.Propuest"]  # variante duplicada de "Evaluac.Propuest."
    return ({f"C{i}": k for i, k in enumerate(cats, 1)}, {f"T{i}": k for i, k in enumerate(temas, 1)},
            build.CAT, build.TEMA, build.OBRAS)


def pendientes(lote=None):
    """Imprime las opiniones de gob.pe que aún no tienen clasificación, en un formato compacto para clasificarlas."""
    datos = json.load(open(SALIDA, encoding="utf-8"))["opiniones"]
    hechas = json.load(open(CLASIF, encoding="utf-8")) if os.path.exists(CLASIF) else {}
    cc, tt, CAT, TEMA, OBRAS = codigos()
    # Las opiniones que ya están en el Excel de la bitácora no se clasifican: el Excel manda
    previas = os.path.join(ROOT, "data", "opiniones.json")
    en_excel = {f"{r['y']}-{r.get('s', 'OECE')}-{r['op']}" for r in json.load(open(previas, encoding="utf-8"))["rows"]
                if r.get("src", "x") == "x"} if os.path.exists(previas) else set()
    faltan = [k for k in datos if k not in hechas and k not in en_excel]
    print("CATEGORÍAS: " + " | ".join(f"{c}={CAT[k]}" for c, k in cc.items()))
    print("TEMAS (obras): " + " | ".join(f"{c}={TEMA[k]}" for c, k in tt.items() if k in OBRAS))
    print("TEMAS (selección, bienes y servicios): " + " | ".join(f"{c}={TEMA[k]}" for c, k in tt.items() if k not in OBRAS))
    print(f"\nPENDIENTES: {len(faltan)}. Formato de respuesta, una línea por opinión y un par por consulta:")
    print("  CLAVE: C?/T? ; C?/T? …   (X en lugar de C?/T? si el texto no es una consulta; CLAVE: =C?/T? si")
    print("                            ninguna consulta se leyó bien y la opinión se muestra con su asunto;")
    print("                            opcional al final: | m=30225,32069 para fijar el marco de cada consulta)\n")
    for k in faltan[:lote] if lote else faltan:
        d = datos[k]
        qs = d["consultas"] or [{"q": d["asunto"] or d["titulo"], "m": None}]
        print(f"{k} [{d['fecha']}] marco≈{d['marco']} · ASUNTO: {d['asunto']}")
        for i, q in enumerate(qs, 1):
            print(f"   {i}. {q['q'][:420]}{'…' if len(q['q']) > 420 else ''}{'  [m≈' + q['m'] + ']' if q['m'] else ''}")


def clasificar(archivo):
    """Lee líneas "CLAVE: C?/T? ; C?/T? [| m=…]" y las guarda en data/clasificacion.json (valida códigos y cantidades)."""
    datos = json.load(open(SALIDA, encoding="utf-8"))["opiniones"]
    hechas = json.load(open(CLASIF, encoding="utf-8")) if os.path.exists(CLASIF) else {}
    cc, tt, *_ = codigos()
    errores, n = [], 0
    for linea in open(archivo, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        k, _, resto = linea.partition(":")
        k = k.strip()
        # "CLAVE: =C?/T?": el texto extraído no es legible; la opinión se muestra con su asunto, en una sola ficha
        m = re.fullmatch(r"\s*=\s*(C\d+)\s*/\s*(T\d+)\s*(?:\|\s*m=(30225|32069|1017))?\s*", resto)
        if m and k in datos and m.group(1) in cc and m.group(2) in tt:
            hechas[k] = {"asunto": {"c": cc[m.group(1)], "t": tt[m.group(2)], **({"m": m.group(3)} if m.group(3) else {})}}
            n += 1
            continue
        pares, _, marcos = resto.partition("|")
        pares = [p.strip() for p in pares.split(";") if p.strip()]
        marcos = re.findall(r"30225|32069|1017|-", marcos)
        if k not in datos:
            errores.append(f"{k}: no está en data/gobpe.json")
            continue
        esperadas = max(1, len(datos[k]["consultas"]))
        if len(pares) != esperadas or (marcos and len(marcos) != esperadas):
            errores.append(f"{k}: {len(pares)} clasificaciones para {esperadas} consultas")
            continue
        fila = []
        for i, p in enumerate(pares):
            if p.upper() == "X":  # la extracción tomó por consulta un texto que no lo es: no se publica
                fila.append({"omitir": True})
                continue
            m = re.fullmatch(r"(C\d+)\s*/\s*(T\d+)", p)
            if not m or m.group(1) not in cc or m.group(2) not in tt:
                errores.append(f"{k}: código no válido {p!r}")
                break
            fila.append({"c": cc[m.group(1)], "t": tt[m.group(2)], **({"m": marcos[i]} if marcos and marcos[i] != "-" else {})})
        else:
            hechas[k] = fila
            n += 1
    guardar_json(CLASIF, dict(sorted(hechas.items())))
    print(f"Clasificadas: {n}. Total en data/clasificacion.json: {len(hechas)}")
    for e in errores:
        print("ERROR:", e)


def actualizar():
    """Actualización periódica: opiniones nuevas de la colección del OECE, su descarga y extracción."""
    nuevas = descubrir()
    descargar([])
    extraer()
    previas = os.path.join(ROOT, "data", "opiniones.json")
    datos = json.load(open(SALIDA, encoding="utf-8"))["opiniones"]
    hechas = json.load(open(CLASIF, encoding="utf-8")) if os.path.exists(CLASIF) else {}
    en_excel = {f"{r['y']}-{r.get('s', 'OECE')}-{r['op']}" for r in json.load(open(previas, encoding="utf-8"))["rows"]
                if r.get("src", "x") == "x"} if os.path.exists(previas) else set()
    faltan = [k for k in datos if k not in hechas and k not in en_excel]
    print(f"Opiniones nuevas en gob.pe: {nuevas}. Por clasificar: {len(faltan)}"
          f"{' (' + ', '.join(faltan) + ')' if faltan else ''}")
    return faltan


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if not args or args[0] not in ("descubrir", "descargar", "extraer", "pendientes", "clasificar", "actualizar"):
            sys.exit(__doc__)
        if args[0] == "actualizar":
            actualizar()
        elif args[0] == "descubrir":
            descubrir(sitemaps="--sitemaps" in args)
        elif args[0] == "descargar":
            descargar([a for a in args[1:] if re.fullmatch(r"20\d\d", a)])
        elif args[0] == "extraer":
            extraer()
        elif args[0] == "pendientes":
            pendientes(int(args[1]) if len(args) > 1 else None)
        else:
            clasificar(args[1])
    except Bloqueo as b:
        sys.exit(f"DETENIDO: {b}")
