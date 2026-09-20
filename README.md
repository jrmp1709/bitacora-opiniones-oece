# Bitácora de Opiniones OECE

Buscador web de las opiniones de la Dirección Técnico Normativa del OSCE y del OECE (2023 en adelante), clasificadas por etapa, tema y marco normativo.

Elaborado por **J. Rodolfo Mercado Pajares** · [LinkedIn](https://www.linkedin.com/in/j-rodolfo-mercado-pajares-aab7101ba/)
Con información pública del portal oficial gob.pe.

## Ver el sitio

- En GitHub Pages: https://jrmp1709.github.io/bitacora-opiniones-oece/
- En claude.ai: https://claude.ai/artifact/CmToMKGB5f1CDha4Ff1gTX
- Se puede buscar por palabra, o preguntarle a **CriterIA** (el robot de abajo a la derecha): se le cuenta el caso y dice qué opiniones lo tratan.
- En local: abrir `index.html` en el navegador.
- La base completa en hoja de cálculo: `base_opiniones.xlsx` (se genera con el script).

## Requisitos (solo la primera vez)

```
pip install openpyxl pypdf
```

## Actualizar

**Automático, cada lunes:** la tarea programada "Actualizar Bitácora de Opiniones OECE" de la app de Claude busca opiniones nuevas en gob.pe, las clasifica y republica el sitio. Funciona mientras la app está abierta.

**A mano, opiniones nuevas de gob.pe:**
1. `python scripts/gobpe.py actualizar` (descarga lo nuevo e indica cuántas faltan clasificar).
2. Si faltan: `python scripts/gobpe.py pendientes`, clasificarlas y guardarlas con `python scripts/gobpe.py clasificar archivo.txt` (el formato está en `CLAUDE.md`).
3. `python scripts/build.py`.

**Excel nuevo de la bitácora (cada quincena):**
1. Copiar el nuevo `.xlsx` en la carpeta `data/`.
2. Ejecutar `python scripts/build.py`.
3. Revisar los avisos que imprime (temas nuevos, filas incompletas, enlaces que no coinciden).

## Publicar gratis en GitHub Pages

1. Crear un repositorio **público** en GitHub y subir esta carpeta. El Excel, la caché y los archivos generados para el Artifact quedan fuera por el `.gitignore`.
2. En el repositorio: Settings → Pages → Source: rama `main`, carpeta `/ (root)`.
3. En unos minutos el sitio queda disponible en `https://<usuario>.github.io/<repositorio>/`.

## Con Claude Code

Abrir esta carpeta en la terminal y ejecutar `claude`. El archivo `CLAUDE.md` le da todo el contexto del proyecto.
