# Bitácora de Opiniones OECE

Buscador web de las opiniones de la Dirección Técnico Normativa del OSCE y del OECE (2023 en adelante), clasificadas por etapa, tema y marco normativo.

Elaborado por **J. Rodolfo Mercado Pajares** · [LinkedIn](https://www.linkedin.com/in/j-rodolfo-mercado-pajares-aab7101ba/)
Con información pública del portal oficial gob.pe.

## Ver el sitio

- En GitHub Pages: https://jrmp1709.github.io/bitacora-opiniones-oece/
- En claude.ai: https://claude.ai/artifact/CmToMKGB5f1CDha4Ff1gTX
- Se puede buscar por palabra, o preguntarle a **CriterIA** desde la portada o desde el robot de abajo a la derecha: se le cuenta el caso y dice qué opiniones lo tratan, con su número, fecha, régimen normativo, por qué son pertinentes y el enlace al documento oficial.
- Se actualiza sola cada 5 días en GitHub Actions: busca opiniones nuevas en gob.pe, las clasifica, valida sus referencias y publica.
- En local: abrir `index.html` en el navegador.
- La base completa en hoja de cálculo: `base_opiniones.xlsx` (se genera con el script).

## Requisitos (solo la primera vez)

```
pip install -r requirements.txt
```

## Actualizar

**Automático, cada 5 días (sin hacer nada):** GitHub Actions corre `scripts/actualizar.py` los días 1, 6, 11, 16, 21 y 26 a las 9:00 de Lima. Busca opiniones nuevas en gob.pe, las clasifica, valida sus referencias antes de publicarlas y sube el sitio regenerado. No depende de Claude ni de que la PC esté encendida. El resumen de cada ejecución está en la pestaña **Actions** del repositorio; para correrla a mano: Actions → *Actualizar bitácora* → *Run workflow*.

**A mano, el mismo ciclo:** `python scripts/actualizar.py` (sin publicar) o `python scripts/actualizar.py --publicar`.

**Excel nuevo de la bitácora (cada quincena):**
1. `git pull` (la actualización automática también sube cambios).
2. Copiar el nuevo `.xlsx` en la carpeta `data/` y ejecutar `python scripts/build.py`.
3. Revisar los avisos que imprime (temas nuevos, filas incompletas, enlaces corregidos).
4. `git add -A && git commit -m "Excel del …" && git push`. El Excel no se sube: queda fuera por el `.gitignore`, y lo leído de él va en `data/excel.json`.

**Otras herramientas:** `python scripts/validar.py todo` revisa todas las referencias; `python scripts/clasificador.py evaluar` mide la precisión de la clasificación automática.

## Con Claude Code

Abrir esta carpeta en la terminal y ejecutar `claude`. El archivo `CLAUDE.md` le da todo el contexto del proyecto.
