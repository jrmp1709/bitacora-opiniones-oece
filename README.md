# Bitácora de Opiniones OECE

Buscador web de las opiniones de la Dirección Técnico Normativa del OSCE y del OECE (2023 en adelante), clasificadas por etapa, tema y marco normativo.

Elaborado por **J. Rodolfo Mercado Pajares** · [LinkedIn](https://www.linkedin.com/in/j-rodolfo-mercado-pajares-aab7101ba/)
Con información pública del portal oficial gob.pe.

## Ver el sitio

- En GitHub Pages: https://jrmp1709.github.io/bitacora-opiniones-oece/
- En claude.ai: https://claude.ai/artifact/CmToMKGB5f1CDha4Ff1gTX
- Se puede buscar por palabra, o preguntarle a **CriterIA** desde la portada o desde el robot de abajo a la derecha: se le cuenta el caso y dice qué opiniones lo tratan, con su número, fecha, régimen normativo, por qué son pertinentes, **lo que concluyó la DTN en texto literal** y el enlace al documento oficial.
- CriterIA entiende filtros dichos en la misma frase ("penalidades en obras del 2024"), seguimientos ("¿y con la ley nueva?"), preguntas sobre la base ("¿cuál es la última opinión?") y palabras mal escritas.
- Cada 5 días Claude la actualiza: busca opiniones nuevas en gob.pe, las clasifica, valida sus referencias y publica.
- En local: abrir `index.html` en el navegador.
- La base completa en hoja de cálculo: `base_opiniones.xlsx` (se genera con el script).

## Requisitos (solo la primera vez)

```
pip install -r requirements.txt
```

## Actualizar

**Cada 5 días, con Claude:** la tarea programada "Actualizar Bitácora de Opiniones OECE" de la app de Claude (días 1, 6, 11, 16, 21 y 26 a las 9:00) busca opiniones nuevas en gob.pe, Claude las clasifica, se validan sus referencias y se publica. Funciona mientras la app de Claude está abierta (si está cerrada, corre al abrirla).

**A mano, el mismo ciclo:** `python scripts/actualizar.py` (si hay opiniones por clasificar, se detiene y lo dice), clasificarlas con `python scripts/gobpe.py pendientes` y `python scripts/gobpe.py clasificar archivo.txt`, y luego `python scripts/actualizar.py --publicar`.

**Excel nuevo de la bitácora (cada quincena):**
1. `git pull` (la tarea de Claude también sube cambios).
2. Copiar el nuevo `.xlsx` en la carpeta `data/` y ejecutar `python scripts/build.py`.
3. Revisar los avisos que imprime (temas nuevos, filas incompletas, enlaces corregidos).
4. `git add -A && git commit -m "Excel del …" && git push`. El Excel no se sube: queda fuera por el `.gitignore`, y lo leído de él va en `data/excel.json`.

**Otras herramientas:** `python scripts/validar.py todo` revisa todas las referencias; `python scripts/clasificador.py sugerir` da una segunda opinión sobre la clasificación (no guarda nada).

## Con Claude Code

Abrir esta carpeta en la terminal y ejecutar `claude`. El archivo `CLAUDE.md` le da todo el contexto del proyecto.
