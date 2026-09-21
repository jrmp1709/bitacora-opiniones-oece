# Bitácora de Opiniones OECE

Sitio web estático (una sola página) para buscar las opiniones que emite la Dirección Técnico Normativa (DTN): la del OSCE hasta abril de 2025 y la del OECE, el organismo que lo reemplazó con la Ley 32069. Cubre desde 2023. Público: abogados, ingenieros y funcionarios de contratación pública en el Perú. Todo el texto visible está en español del Perú; los meses se abrevian "set", no "sep".

## Autoría (obligatorio)

- El sitio lo elabora **J. Rodolfo Mercado Pajares**. LinkedIn: https://www.linkedin.com/in/j-rodolfo-mercado-pajares-aab7101ba/
  El crédito "Elaborado por J. Rodolfo Mercado Pajares" con enlace a LinkedIn va en la cabecera y en el pie. No se quita.
- Es el **único crédito** del sitio. No se agregan créditos, firmas ni menciones a terceros.
- Los datos provienen de un Excel de base usado con autorización (2026, clasificado a mano) y de las publicaciones oficiales en gob.pe (2023 en adelante, clasificadas automáticamente).
- Los textos de las consultas **no se reescriben ni se corrigen**: solo se normalizan espacios y saltos de línea, para no alterar el registro.

## Estructura

```
index.html               Sitio generado. No se edita a mano: se regenera con el script.
artifact.html            La misma página sin doctype, <head> ni <body>, para el Artifact de claude.ai. En .gitignore.
base_opiniones.xlsx      Toda la base en una hoja de cálculo (para Excel o Google Sheets). La genera build.py. En .gitignore.
src/template.html        Plantilla (HTML + CSS + JS en un solo archivo). Placeholders: {{DATA}}, {{LINKEDIN}}, {{AVATAR}}, {{MASCOTA}}
scripts/build.py         Une el Excel (o su copia, data/excel.json) y las opiniones de gob.pe y genera data/opiniones.json,
                         index.html, artifact.html y base_opiniones.xlsx
scripts/gobpe.py         Descarga, extrae y ayuda a clasificar las opiniones publicadas en gob.pe
scripts/clasificador.py  Sugerencias de clasificación (segunda opinión para Claude; no guarda nada) y su precisión
scripts/validar.py       Validación de referencias de las opiniones nuevas y del sitio generado, antes de publicar
scripts/actualizar.py    El ciclo de actualización: buscar, validar, regenerar y publicar (se detiene si falta clasificar)
requirements.txt         openpyxl y pypdf
assets/                  La mascota de CriterIA: criteria-original.webp (la imagen que dio el autor, 1254 px)
                         y sus dos recortes, criteria-avatar.webp (cabeza, 168 px) y criteria-mascota.webp (cuerpo, 380 px).
data/*.xlsx              Excel de la bitácora. Está en .gitignore y no se sube a GitHub.
data/gobpe_indice.json   Índice de opiniones de gob.pe (id, URL, año, serie, número)
data/gobpe.json          Lo extraído de cada opinión: fecha, asunto, consultas, PDF, página
data/clasificacion.json  Etapa/categoría/tema (y marco) de cada consulta de gob.pe
data/opiniones.json      Datos limpios generados (lo que se incrusta en la página)
data/excel.json          Lo leído del Excel (filas, enlaces a normas, fecha): permite regenerar el sitio sin el Excel. Lo escribe build.py
data/retenidas.json      Opiniones que no pasaron la validación de referencias: no se publican hasta que pasen
cache/                   Páginas y texto de los PDF descargados de gob.pe. En .gitignore.
```

Requisitos: `pip install openpyxl pypdf` (y `pillow` solo si hay que rehacer los recortes de la mascota: avatar = `crop((250,15,900,665))` a 168 px; cuerpo = `crop((69,20,1176,1000))` a 380 px de ancho, ambos con el fondo transparente del original). Para regenerar el sitio: `python scripts/build.py` (toma el .xlsx más reciente de `data/`). Las salidas se escriben con saltos de línea LF, así que regenerar en Windows no produce diferencias falsas en git.

## Datos

### Excel de la bitácora (2026)

- Hoja `Bitacora`. Encabezados en la fila 4 y datos desde la fila 5. Columnas: C categoría, D tema, E casuística, F marco normativo, G n.° de opinión, H enlace al PDF, I enlace a la ley, J enlace al reglamento.
- La fecha de actualización se lee de la cabecera ("Actualizad0: 15 de setiembre del 2026").
- La hoja `Apoyo` tiene las listas oficiales de categorías (en orden del ciclo de contratación) y de temas, en dos grupos: obras, y selección/bienes/servicios. Están replicadas en los diccionarios `CAT`, `TEMA` y `OBRAS` de `build.py`. Si aparece un tema o una categoría nueva, el script avisa; hay que agregarle una etiqueta legible.
- Si una fila tiene tema, casuística, opinión o enlace pero le falta alguno de los campos obligatorios, el script avisa ("Fila N: incompleta…") y no la incluye. Las filas de relleno ("…..") y las notas del pie no generan aviso.
- **El Excel manda** en las opiniones que registra: de gob.pe solo se toman su fecha y su asunto.
- **Conclusiones:** el sufijo "- C2, C3" (o "_C14, 15", ", C1") al final de la casuística se convierte en `k: [2,3]` y se muestra como "Conclusiones 2 y 3".
- `normas` (nivel superior del JSON): enlaces a la ley y al reglamento por marco, leídos de las columnas I y J. El Excel los actualiza cada quincena (p. ej. "Ley … con modificaciones posteriores hasta el 19-07-2026"), por eso no se escriben a mano en la plantilla. El sitio toma la fecha "texto al …" del propio enlace y rotula "TUO" cuando el enlace es el D.S. 082-2019-EF. Si un marco trae enlaces distintos en distintas filas, el script avisa y usa el más frecuente.

### Opiniones de gob.pe (2023 en adelante): `scripts/gobpe.py`

- Fuente: las páginas `https://www.gob.pe/institucion/oece/informes-publicaciones/<id>-opinion-n-…` (las del OSCE también están bajo `/oece/`). El índice inicial se armó con los sitemaps de gob.pe (`descubrir --sitemaps`, lento); las nuevas se toman de la primera página de la colección del OECE (`descubrir`).
- Buenas prácticas: se respeta el robots.txt de gob.pe (no se recorren las páginas `?sheet=`), una solicitud por segundo, un User-Agent que identifica al proyecto y caché en `cache/`. Si gob.pe responde con un bloqueo (403, 418, 429), el script se detiene: **no se intenta esquivarlo**. Desde la PC del autor gob.pe responde normalmente; desde servidores en la nube (WebFetch) y desde el navegador integrado de la app, no.
- De cada página se toma el título (número oficial), la **fecha de la opinión** y el enlace al PDF. La sumilla no se usa porque nombra al solicitante. Del PDF (con `pypdf`) se extraen el **asunto**, las **consultas** (apartados 2.1, 2.2… o la cita tras "la consulta formulada es la siguiente") y el número de conclusiones. Se limpian cabeceras de página, bandas de firma digital, notas al pie intercaladas y el análisis que el PDF a veces pega a la consulta.
- Series y números: hasta 2024 el OSCE numeraba "Opinión N.° 045-2024/DTN" (forma corta "045"); en 2025 hubo una serie del OSCE ("D000010-2025-OSCE-DTN") y otra del OECE que reinició la numeración ("D000010-2025-OECE-DTN"). Una opinión se identifica por año + serie + número (`key` en el JS).
- Resultado a 18.09.2026: 383 opiniones (2023: 128, 2024: 61, 2025: 27 del OSCE + 68 del OECE, 2026: 99) y 758 consultas publicadas. Solo 2025-OSCE-D017 no tiene consultas legibles y se muestra con su asunto.

### Clasificación automática (`data/clasificacion.json`)

Las consultas de gob.pe se clasifican con la misma taxonomía de la bitácora y el sitio las marca como "clasificación automática". **Las clasifica Claude**, leyendo cada consulta: se probó una clasificación sin intervención y el autor la descartó (21.09.2026) para evitar errores, porque acierta bastante menos.

`scripts/clasificador.py sugerir` queda como segunda opinión: para cada consulta sin clasificar muestra el tema y la categoría de sus nueve vecinas más parecidas (TF-IDF sobre la consulta y el asunto), con su confianza, y **no guarda nada**. Reglas encima: si la consulta habla de una obra ("obra", "valorización", "residente", "metrado") no puede quedar en Bienes y servicios, y la obra se separa por marco. Su precisión, dejando fuera cada opinión (`python scripts/clasificador.py evaluar`, 21.09.2026): tema 67 %, categoría 72 %. No aprende de entradas con el campo `auto` (clasificaciones sin revisar), por si alguna vez las hubiera.

Flujo de Claude:
1. `python scripts/gobpe.py pendientes > cache/pendientes.txt`: lista lo que falta, con los códigos C1… (categorías) y T1… (temas).
2. Se escribe una línea por opinión: `CLAVE: C?/T? ; C?/T? …` (un par por consulta, en orden). `X` omite un texto que no es consulta; `CLAVE: =C?/T?` muestra la opinión con su asunto cuando el PDF no se leyó bien; al final, `| m=30225,32069,…` fija el marco de cada consulta cuando la pista "m≈" no es correcta.
3. `python scripts/gobpe.py clasificar archivo.txt` valida los códigos y la cantidad de consultas, y guarda.

Convenciones: obra con Ley 30225 → C6 Solo construcción; obra con Ley 32069 → C8; supervisión/consultoría de obra → C5 (tema T1 para todo lo del contrato de supervisión, como hace la bitácora); diseño y construcción / concurso oferta / llave en mano → C7; expediente técnico → C2; estudios de preinversión → C1; procedimiento de selección → C4; actos preparatorios, valor estimado/referencial, PAC y ámbito de aplicación → C3 (T51 o T6); bienes y servicios → C11; acuerdos marco y compras corporativas → C10 (T46 si no hay un tema más preciso); arbitraje y temas generales de la entidad → C12. Desde el 22.04.2025 conviven la anterior Ley 30225 y la Ley 32069: el marco se fija por consulta. Las consultas sobre contratos del D.L. 1017 (D.S. 184-2008-EF, D.S. 138-2012-EF) van con marco 1017.

### Validación antes de publicar (`scripts/validar.py`)

- **Cada opinión nueva**, contra gob.pe: el título de su página trae el mismo número oficial que su clave; la página y el PDF son de gob.pe y responden, y el PDF es de verdad un PDF (empieza por `%PDF`); si el nombre del PDF trae número y año, son los de la opinión y su prefijo es el id de la página; la fecha existe, no es futura y es del año de la opinión; tiene consultas (o asunto) y una clasificación con códigos válidos; y el marco es coherente con la fecha (no hay consultas sobre la Ley 32069 antes de su publicación, el 24.06.2024; entre su publicación y su vigencia sí las hubo, como la D000014-2025-OSCE-DTN). La que no pasa queda en `data/retenidas.json`, `build.py` no la publica y se vuelve a probar en la siguiente ejecución.
- **El sitio generado**, sin conexión: campos completos, enlaces de gob.pe, fechas válidas, marcos conocidos, sin duplicados (la misma casuística en dos categorías no es duplicado: el Excel lo hace a propósito, p. ej. D069–D071) y sin placeholders sin reemplazar. Si algo falla, no se publica nada.
- `python scripts/validar.py todo [--en-linea]` revisa todas las opiniones (en línea es lento: dos solicitudes por opinión, una por segundo).

### Campos del JSON (`data/opiniones.json`)

- Por consulta: `n` orden, `op` forma corta (D092 / 045), `y` año, `s` serie (OSCE / OECE), `o` número oficial, `u` URL del PDF, `h` página en gob.pe, `lk` código que realmente abre el enlace (si no coincide con `op`), `f` fecha, `c` categoría, `t` tema, `g` grupo (obras/seleccion), `q` texto, `k` conclusiones, `m` marco (32069 / 30225 / 1017), `src` origen (`x` Excel, `g` gob.pe).
- Nivel superior: `updated`, `rows`, `cats`, `temas`, `normas` y `asuntos` (asunto de cada opinión, por `key`).
- **Fecha:** la de la opinión según su página en gob.pe. Si no está disponible, la de carga del PDF (parámetro `?v=`, en hora de Lima).
- **Página en gob.pe (`h`):** para las filas del Excel se deduce del PDF: el número inicial de su nombre es el id de la publicación (`…/file/9299678/7626891-opinion-d001-2026-oece-dtn.pdf` → `…/informes-publicaciones/7626891-opinion-n-d000001-2026-oece-dtn`). El autor lo verificó a mano.
- **Número oficial:** "Opinión N.° D000001-2026-OECE-DTN" (6 dígitos) u "Opinión N.° 045-2024/DTN". El sitio muestra la forma corta en grande y el número oficial en la línea inferior de la ficha y en la cabecera de la vista por opinión. Nunca se muestra la forma mixta "D001-2026-OECE-DTN", que no es oficial.

### Enlaces cruzados del Excel (se resuelven solos)

De cuando en cuando una fila lleva el número de una opinión y el enlace de otra: es un copiar-pegar entre filas vecinas. `build.py` ya no se limita a avisar: lo resuelve contra lo publicado en gob.pe, con tres criterios en orden de contundencia (`resolver_cruce`).

1. **Las conclusiones citadas.** Una fila que cita las conclusiones 6 y 7 no puede ser de una opinión que solo tiene una.
2. **El parecido del texto** de la casuística con las consultas y el asunto de cada candidata (coeficiente de Dice, que pesa las dos longitudes; contar solo las palabras compartidas premiaría a la consulta más larga). Decide únicamente si una gana con holgura.
3. **El orden del Excel**, que va por número de opinión: si el número rotulado encaja entre sus filas vecinas y el del enlace no, el rótulo manda y el enlace vino de otra fila. Es lo que distingue dos opiniones del mismo tema, donde el texto no alcanza.

Según quién acierte, se corrige el enlace (y se toma el PDF y la página oficiales de gob.pe) o se reasigna la fila a la opinión que abre el enlace. **Nada de esto es silencioso:** cada corrección sale como AVISO al correr el script. Si ningún criterio decide, la ficha se muestra con el aviso ámbar ("Este enlace abre la Opinión …") y el script lo dice.

Con el Excel del 15.09.2026 se resolvieron cuatro filas:
- **D002** (mayores metrados): el enlace abría la D003; el rótulo era correcto.
- **D064** y **D065** (retraso injustificado, conclusiones 4 a 7): son de la **D063**, que tiene nueve conclusiones; las verdaderas D064 y D065 ya tienen sus propias filas.
- **D098** (pronunciamiento sobre el ET de adicional observado): el enlace abría la D092; el rótulo era correcto.

### Otras observaciones del Excel

- La columna "LINK REGLAMENTO" de la Ley 30225 apunta al TUO (D.S. 082-2019-EF); en el sitio se rotula "TUO".

## Marco normativo

- Ley N.° 32069, Ley General de Contrataciones Públicas, y su Reglamento, D.S. N.° 009-2025-EF (vigentes desde el 22.04.2025).
- Ley N.° 30225, modificada por el D.L. 1444, y su Reglamento, D.S. N.° 344-2018-EF (vigentes desde el 30.01.2019). Es el marco de casi todas las opiniones de 2023 y 2024.
- D.L. N.° 1017 y su Reglamento, D.S. N.° 184-2008-EF (consultas sobre contratos antiguos).
- Las opiniones se publican en gob.pe, en la colección "Opiniones de la Dirección Técnico Normativa – OECE", y en Pladicop (Reglamento, art. 11.3).

## Funciones del sitio (no romper)

- Dos formas de buscar: el **buscador** de la barra, que filtra en vivo por lo que se escribe, y **CriterIA**, que responde en lenguaje natural desde la portada o desde su chat flotante (ver la sección siguiente). Son cosas distintas a propósito y no se mezclan.
- **Cobertura, en un solo lugar** (JS, objeto `COB`): desde qué año hay opiniones, el último pronunciamiento incorporado (la consulta con la fecha más reciente) y la fecha de actualización completa. Se usa en la línea superior ("desde 2023"), la bajada, las cifras ("Cobertura desde 2023"), la línea bajo las cifras, el pie y la nota de CriterIA. No se escribe a mano en ningún lado.
- **Régimen normativo:** cada ficha lleva "Ley N.° 32069 · vigente" (azul) o "Ley N.° 30225 · régimen anterior" / "D.L. N.° 1017 · régimen anterior" (ámbar, con el detalle al pasar el cursor). Encima de los resultados, un aviso dice cuántas opiniones son del régimen anterior y ofrece "Ver solo las de la Ley N.° 32069"; en la vista por opinión, la nota va en la cabecera de cada opinión anterior. El texto es informativo: esos criterios siguen valiendo para los contratos y procedimientos regidos por la norma anterior.
- Búsqueda insensible a tildes y mayúsculas. Varias palabras funcionan como AND. Buscan la opinión exacta: "D092", "d92", "D092-2026", "D000010-2025-OSCE-DTN", "045-2024/DTN" o el número oficial pegado tal cual ("Opinión N.° D000092-2026-OECE-DTN"); con un número de opinión, las palabras "opinión" y "N.°" se ignoran. También se busca en el asunto de cada opinión. Los términos se resaltan con `<mark>`.
- Filtros con conteos que se recalculan según los demás filtros: año (radio), etapa (radio), marco normativo (radio), categoría (múltiple), tema (múltiple, con buscador y barras) y mes.
- Gráfico de la cabecera: opiniones por año; al elegir un año (en el gráfico o en el filtro), opiniones por mes de ese año, con clic en el mes para filtrar y "Ver todos los años" para volver.
- Dos vistas: por consulta o agrupada por opinión (con su asunto). La vista elegida se guarda en localStorage. Los resultados se muestran por tandas (60 consultas o 25 opiniones) con "Mostrar más".
- Orden: más recientes, más antiguas, por tema y, durante una consulta, más pertinentes.
- Atajos: "/" enfoca la búsqueda y Esc la limpia; Esc también cierra CriterIA. Al hacer clic en el tema de una ficha, se filtra por ese tema.
- Cada ficha enlaza al PDF ("Ver opinión") y a la página de la opinión en gob.pe ("Página en gob.pe"). Las fichas de gob.pe llevan la marca "clasificación automática".
- Accesibilidad: solo el conteo de resultados es región viva (`role="status"`), no la lista entera; la conversación de CriterIA es la otra excepción (`role="log"`), porque es un chat. Al abrir el chat el foco va al campo de texto y al cerrarlo vuelve al botón. Como los filtros se vuelven a pintar en cada cambio, quien usa el teclado conserva el foco en la opción que activó; al quitar un filtro activo, el foco pasa al siguiente.
- Móvil: los filtros se pliegan detrás del botón "Filtros" (Esc los cierra). La página no debe tener scroll horizontal a 400 px de ancho.

## CriterIA (el chat consultor)

El asistente del sitio se llama **CriterIA** (criterio + IA) y se escribe siempre así, con "IA" en mayúsculas. Tiene mascota: el robot con casco de obra que dio el autor. Vive en un chat flotante y se mantiene **aparte del buscador** para que nadie confunda la búsqueda exacta con la consulta en lenguaje natural.

Dónde se le ve (la idea es que salte a la vista, no que haya que buscarlo):
- **Portada:** un formulario propio, "Pregúntele a CriterIA", debajo de la bajada: campo blanco sobre la banda azul, botón latón "Consultar" y tres ejemplos. Al enviar, se abre el chat con la pregunta ya respondida; no hace falta tocar los filtros.
- **Botón flotante** abajo a la derecha, con la mascota y el mismo llamado.
- **Aviso de enganche:** a los 4,5 segundos de llegar aparece una viñeta junto al botón ("¿Busca una opinión de la DTN? Pregúntele a CriterIA…"). Sale **una sola vez por navegador** (`localStorage: bitacora-criteria`), se cierra con la × y desaparece sola a los 16 segundos. Si alguien ya abrió el chat, no vuelve a salir.
- **En el chat:** la mascota completa encabeza el saludo y su cabeza va como avatar en cada respuesta.

Las imágenes se incrustan como `data:` URI (placeholders `{{AVATAR}}` y `{{MASCOTA}}`, que `build.py` rellena desde `assets/`), así el sitio sigue siendo un solo archivo. Suman unos 120 KB.

El tono: usted, frases cortas y directas ("Encontré 34 opiniones sobre eso. Estas son las que más se parecen a su caso:"). Antes de cada respuesta se muestran tres puntitos durante 0,4 s: la búsqueda es instantánea, pero leerla de golpe se siente brusco.

Identidad: el nombre se escribe "Criter" + "IA" en latón (`<span class="ia">`), como en su logo; su avatar va en un círculo con filete latón; la cabecera del chat es la banda azul con el filete latón inferior, como la cabecera del sitio.

Cada opinión que muestra lleva: número oficial (enlazado al PDF), régimen (vigente o anterior), fecha, tema y marco, el texto de la consulta, **"Por qué es pertinente"** (función `porQue`: las frases y palabras de la pregunta que contiene, tal como están escritas en la consulta, y las que coinciden por una variante, p. ej. «pluviales» (por «lluvias»); si solo coincide por su tema, lo dice) y los enlaces "Documento oficial (PDF)" y "Página en gob.pe". El resumen avisa cuántas de las opiniones halladas son del régimen anterior. En la página, mientras hay una consulta, cada ficha muestra la misma línea como "Pertinencia".

Qué hace con cada pregunta (`src/template.html`, bloques "consultor" y "el chat"):

1. Si reconoce un número de opinión ("D092", "045-2024/DTN"), no calcula pertinencia: lo pone en el buscador de la página, que ya lo encuentra.
2. Si no, limpia los filtros, puntúa las 758 consultas y responde con cuántas opiniones se relacionan, las cuatro más pertinentes (una por opinión, con su código, fecha, tema y el texto de la consulta, enlazadas al PDF) y botones para "Ver las N opiniones" en la página o acotar ("Solo obras", "Solo Ley 30225"). Si no hay nada, sugiere temas cercanos.
3. La pregunta queda proyectada en la página: la lista se ordena por pertinencia y aparece el filtro "Consulta: «…»", que se quita como cualquier otro filtro. Los demás filtros, vistas y conteos siguen funcionando igual.

Cómo puntúa: BM25 sobre tres campos con distinto peso —texto de la consulta (1), asunto (0,9), tema + categoría + etapa (2) y año + marco (1,2)—. El índice se arma la primera vez que alguien pregunta, no al cargar la página. Todo ocurre en el navegador: sin servidor ni clave de API, la pregunta no sale de la página.

- **Conceptos, no palabras:** cada palabra de la pregunta forma un concepto con sus variantes (`SYN`: sinónimos del rubro y verbos conjugados, porque la gente escribe "aprueba" y la opinión dice "aprobación"). De un concepto cuenta su mejor coincidencia, no cuántas variantes aparecen. Si la palabra preguntada no existe en la bitácora pero sí una variante (subcontratar → subcontratación), la variante vale casi lo mismo.
- **Frases** (`PHR`: las de la lista más las etiquetas de tema): si la pregunta trae "ampliación de plazo", las consultas con esa frase suben.
- Se descartan las palabras vacías (`STOP`, que incluye "opinión", "consulta" y los verbos de preguntar) y las que aparecen en más de la mitad de las consultas ("obra", "servicio", "contrato"): para eso están los filtros. Las que no figuran en ninguna consulta se avisan ("La bitácora no registra «…»").
- Se muestran las consultas con puntaje ≥ 33 % del mejor, con tope de 120.
- **CriterIA no dice qué respondió la DTN:** la bitácora guarda lo que se preguntó, no las conclusiones. Los textos de la conversación se redactan así a propósito ("tratan lo que me pregunta", "las más pertinentes").
- **Explicación con IA (opcional):** si el visor del Artifact concede la capacidad `sample`, aparece "Explicar con IA", que le pide a Claude un resumen de las ocho consultas más pertinentes con la instrucción expresa de no inventar la respuesta de la DTN. Lo paga quien lo usa y pide su permiso la primera vez; después de la primera vez se redacta solo en cada respuesta. Si no está disponible, el botón no aparece y el chat funciona igual. Al republicar hay que pasar `capabilities: {sample: {}}` (o no pasar `capabilities`, que conserva lo declarado).

## Diseño (mantener)

Estilo sobrio y formal, hermanado con el otro sitio del autor, https://radar-normativo-peru.zemidata.chatgpt.site (misma tipografía y misma familia de logo).
- Cabecera y pie en banda azul noche `#0F1C2E` con filete latón `#CDAB68`. El acento latón en fondo claro es `#8C6A2C`. Fondo `#F4F4F1`, superficie `#FFFFFF`, texto `#151A21`.
- Tipografías (Google Fonts): **Geist** para todo el texto y **Geist Mono** para los números de opinión, los conteos y las cifras. Geist no tiene cursiva: donde antes había cursivas se usa peso (500/600) y color. Títulos en peso 780 con `letter-spacing:-.035em`; el texto general lleva `-.011em`.
- **Logo:** emblema circular de la misma familia que la marca "radar" del otro sitio: un anillo abierto (`stroke-dasharray`, abertura a la derecha) con tres líneas de un registro dentro; la del medio, en latón, sale por la abertura. Está definido una sola vez como `<symbol id="mk">` al inicio del `<body>` y se reutiliza con `<use href="#mk">` en la cabecera, el pie, el botón de CriterIA y la cabecera del chat (los colores viajan por `currentColor` y `--band-accent`, en `style=` dentro del símbolo, porque el CSS del documento no entra en el `<use>`). El favicon es el mismo dibujo en un `data:` URI: si se cambia el emblema, hay que cambiarlo en el símbolo y en el favicon.
- Botones con borde fino y esquinas casi rectas (2–3 px), sin rellenos de color vivos. Nada de emojis ni sombras duras.
- Modo oscuro completo mediante tokens CSS (`prefers-color-scheme` y `[data-theme]`).
- Colores del marco normativo: 32069 azul `#2C4A7C`, 30225 latón `#8C6A2C`, 1017 vino `#7C2D3B`. Las alertas de régimen anterior usan el ámbar de aviso (`--warn`); lo vigente, el azul de la 32069.

## Publicación y actualización

- **La dirección oficial del sitio es la de GitHub Pages** (ver más abajo). También hay una copia como Artifact de claude.ai, https://claude.ai/artifact/CmToMKGB5f1CDha4Ff1gTX, que desde el 21.09.2026 ya no se actualiza sola: quedó con los datos del 19.09.2026 y solo cambia si se republica a mano.
- Para actualizar el Artifact: correr `python scripts/build.py` y publicar `artifact.html` (no `index.html`) en esa misma URL, con la herramienta Artifact, el parámetro `url` y `capabilities: {sample: {}}` (la capacidad que habilita la explicación con IA; si se omite `capabilities` se conserva la declarada). Desde otra conversación, primero `action: "read"` con esa URL. El servicio agrega su propio doctype, `<head>` y `<body>`, por eso `artifact.html` no los trae.
- **Actualización cada 5 días, a cargo de Claude:** la tarea programada "Actualizar Bitácora de Opiniones OECE" (`actualizar-bitacora-oece`, días 1, 6, 11, 16, 21 y 26 a las 9:00). Corre `python scripts/actualizar.py`; si hay opiniones nuevas se detiene (salida 5) para que Claude las clasifique con `gobpe.py pendientes` / `gobpe.py clasificar`, y después `python scripts/actualizar.py --publicar` valida sus referencias en gob.pe, regenera el sitio, valida el conjunto y hace commit y push. Lo que no pasa la validación queda retenido y no se publica. Corre en la PC del autor mientras la app de Claude está abierta (si está cerrada, al abrirla). Los permisos que se aprueban en una ejecución quedan guardados para las siguientes; si una ejecución queda "en curso" sin avanzar, está esperando un permiso.
- **Decisión del autor (21.09.2026): nada se publica sin que Claude clasifique.** Se armó y probó una actualización desatendida en GitHub Actions (gob.pe sí responde desde los servidores de GitHub) con clasificación automática, y se desmontó para prevenir errores de clasificación. No volver a proponerla salvo que el autor lo pida.
- **Excel nuevo (cada quincena):** `git pull`, copiar el Excel en `data/`, correr `python scripts/build.py`, revisar los avisos y subir con `git add -A && git commit && git push`. Así se actualiza `data/excel.json`, y sus filas reemplazan a las automáticas de las mismas opiniones.
- **GitHub Pages:** el proyecto vive en https://github.com/jrmp1709/bitacora-opiniones-oece y el sitio se publica solo desde la rama `main` (carpeta raíz) en https://jrmp1709.github.io/bitacora-opiniones-oece/. Para cambios a mano: `git pull` (la nube también sube cambios), `python scripts/build.py` y luego `git add -A && git commit && git push`. El Excel de origen, `artifact.html`, `base_opiniones.xlsx` y `cache/` están en .gitignore y no se suben.
- Se descartó Google Sheets como base: el conector de Drive crea archivos pero no puede actualizar su contenido. La base vive en `data/` (sincronizada por OneDrive) y `base_opiniones.xlsx` sirve para abrirla en Excel o subirla a Sheets.

## Ideas pendientes (opcionales)

- Automatizar la descarga del Excel desde Google Drive. Falta saber cómo se comparte: si es siempre el mismo archivo, basta su id; si cada quincena llega un archivo nuevo, hay que leer la carpeta.
