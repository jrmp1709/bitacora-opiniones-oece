#!/usr/bin/env python3
"""Actualización automática de la bitácora, sin intervención (la corre GitHub Actions cada 5 días).

1. Busca opiniones nuevas en gob.pe y descarga solo esas (gobpe.py).
2. Clasifica automáticamente las que falten (clasificador.py).
3. Valida sus referencias en gob.pe (validar.py): la que no pasa queda retenida y no se publica.
4. Regenera el sitio (build.py) y valida el conjunto: si algo falla, no se publica nada.
5. Con --publicar: commit y push de los archivos generados; GitHub Pages publica el sitio.

Uso:
    python scripts/actualizar.py             # todo, menos publicar
    python scripts/actualizar.py --publicar  # y además commit + push

Salida: 0 si terminó bien (con o sin novedades), 2 si gob.pe bloqueó el acceso, 3 si la validación
del conjunto falló, 4 si no se pudo subir a GitHub.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build  # noqa: E402
import clasificador  # noqa: E402
import gobpe  # noqa: E402
import validar  # noqa: E402

GENERADOS = ["data/gobpe_indice.json", "data/gobpe.json", "data/clasificacion.json", "data/retenidas.json",
             "data/opiniones.json", "data/excel.json", "index.html"]


def git(*args, ok=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if ok and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r


def informe(lineas):
    """Resumen para el registro de GitHub Actions (y para la consola)."""
    texto = "\n".join(lineas)
    print("\n" + texto)
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write("## Actualización de la bitácora\n\n" + texto.replace("\n", "\n\n") + "\n")


def salida_gh(nombre, valor):
    destino = os.environ.get("GITHUB_OUTPUT")
    if destino:
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write(f"{nombre}={valor}\n")


def main():
    publicar = "--publicar" in sys.argv
    salida_gh("publicado", "false")
    try:
        faltan = gobpe.actualizar()
    except gobpe.Bloqueo as b:
        informe([f"DETENIDO: {b}. No se intentó esquivar el bloqueo ni se publicó nada."])
        return 2

    nuevas, dudosas = clasificador.pendientes() if faltan else ([], [])
    previas = list(json.load(open(validar.RETENIDAS, encoding="utf-8"))) if os.path.exists(validar.RETENIDAS) else []
    por_validar = sorted(set(nuevas) | set(previas))
    try:
        retenidas = validar.nuevas(por_validar) if por_validar else {}
    except gobpe.Bloqueo as b:
        informe([f"DETENIDO durante la validación: {b}. No se publicó nada."])
        return 2

    data = build.generar(build.excel_reciente())
    problemas = validar.conjunto()
    if problemas:
        informe(["La validación del sitio generado falló; no se publicó nada:"] + [f"- {p}" for p in problemas])
        return 3

    gob = json.load(open(validar.GOBPE, encoding="utf-8"))["opiniones"]
    publicadas = [k for k in nuevas if k not in retenidas]
    lineas = [f"Bitácora: {len({(r['y'], r['s'], r['op']) for r in data['rows']})} opiniones y "
              f"{len(data['rows'])} consultas, actualizada al {data['updated']}."]
    if publicadas:
        lineas.append(f"Opiniones nuevas publicadas: {len(publicadas)}")
        lineas += [f"- {gob[k]['oficial']} ({gob[k]['fecha']}): {gob[k]['asunto']}" for k in publicadas]
    else:
        lineas.append("No hay opiniones nuevas en gob.pe.")
    if dudosas:
        lineas.append("Clasificación con confianza baja (conviene revisarla): " + ", ".join(dudosas))
    if retenidas:
        lineas.append("Retenidas por la validación (no se publican hasta que pasen):")
        lineas += [f"- {gob[k].get('oficial') or k}: {'; '.join(p)}" for k, p in retenidas.items()]

    cambios = git("status", "--porcelain", "--", *GENERADOS).stdout.strip()
    if not cambios:
        informe(lineas + ["Sin cambios que publicar."])
        return 0
    if not publicar:
        informe(lineas + ["Cambios listos; no se publicaron (falta --publicar)."])
        return 0

    git("add", "--", *[f for f in GENERADOS if os.path.exists(os.path.join(ROOT, f))])
    titulo = (f"Actualización: {len(publicadas)} opinión{'es' if len(publicadas) != 1 else ''} nueva"
              f"{'s' if len(publicadas) != 1 else ''}" if publicadas else "Actualización de datos")
    cuerpo = "\n".join(f"- {gob[k]['oficial']}: {gob[k]['asunto']}" for k in publicadas) or "Sin opiniones nuevas."
    git("commit", "-m", titulo, "-m", cuerpo)
    for intento in range(2):
        r = git("push", "origin", "HEAD:main", ok=False)
        if r.returncode == 0:
            break
        if intento == 0:  # el remoto avanzó mientras tanto: se trae y se reintenta una vez
            if git("pull", "--rebase", "origin", "main", ok=False).returncode:
                git("rebase", "--abort", ok=False)
                informe(lineas + ["No se pudo subir: hay cambios en GitHub que chocan con estos."])
                return 4
    else:
        informe(lineas + [f"No se pudo subir a GitHub: {r.stderr.strip()}"])
        return 4
    salida_gh("publicado", "true")
    informe(lineas + ["Publicado en https://jrmp1709.github.io/bitacora-opiniones-oece/"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
