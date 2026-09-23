# CriterIA con análisis: cómo encenderlo

El sitio funciona sin esto. Esto agrega el botón **"Analice mi caso"**: el visitante cuenta su caso,
y Claude analiza, opinión por opinión, las más pertinentes que encontró el buscador.

La clave de la API no puede ir en la página, porque es pública: cualquiera la copiaría y gastaría con
ella. Por eso hay un intermediario —un Worker de Cloudflare— que guarda la clave, solo atiende a este
sitio, arma el material desde `data/opiniones.json` (nadie puede mandarle textos propios) y limita el
uso por visitante y por día.

## Lo que necesita

1. Una cuenta en <https://console.anthropic.com> con una **clave de API** (`sk-ant-...`) y saldo.
2. Una cuenta gratuita en <https://dash.cloudflare.com>.
3. Node.js instalado (para el comando `npx`).

## Pasos (unos diez minutos, una sola vez)

```bash
cd proxy
npx wrangler login                      # abre el navegador: autorice Cloudflare
npx wrangler kv namespace create LIMITES
```

El último comando imprime un `id`. Descoméntelo en `wrangler.toml` y péguelo:

```toml
[[kv_namespaces]]
binding = "LIMITES"
id = "el-id-que-imprimió"
```

Luego, la clave (se pega en el terminal; no queda en ningún archivo del proyecto):

```bash
npx wrangler secret put ANTHROPIC_API_KEY
npx wrangler deploy
```

`deploy` imprime la dirección del Worker, algo como
`https://criteria.SU-CUENTA.workers.dev`. Esa dirección va en `scripts/build.py`:

```python
IA_ENDPOINT = "https://criteria.SU-CUENTA.workers.dev"
```

Y se regenera y publica el sitio:

```bash
python scripts/build.py && git add -A && git commit -m "Analice mi caso" && git push
```

## Lo que cuesta

Cloudflare es gratis en este volumen. Se paga a Anthropic por consulta, según el modelo (precios de
setiembre de 2026, por millón de tokens):

| Modelo en `worker.js` | Entrada | Salida | Costo aproximado por análisis |
|---|---|---|---|
| `claude-opus-5` (el que viene puesto) | $5 | $25 | ~$0,06 |
| `claude-sonnet-5` | $2 | $10 | ~$0,025 |
| `claude-haiku-4-5` | $1 | $5 | ~$0,012 |

Un análisis manda unas ocho opiniones con sus conclusiones (~8.000 tokens) y devuelve unas 400
palabras. Para cambiar de modelo, edite `MODELO` en `worker.js` y vuelva a desplegar.

Topes que trae puestos (en `worker.js`): **8 análisis por visitante al día** y **250 en todo el sitio
al día**. Con el modelo que viene, ese tope son unos 15 dólares diarios en el peor caso; bájelo si
quiere estar más tranquilo. Conviene además ponerle un **límite de gasto mensual** a la clave en la
consola de Anthropic.

## Apagarlo

Deje `IA_ENDPOINT = ""` en `scripts/build.py`, regenere y publique: el botón desaparece y el sitio
sigue igual que siempre. Para borrar el Worker: `npx wrangler delete`.

## Privacidad

El caso que escribe el visitante viaja al Worker y de ahí a la API de Anthropic, que no entrena con
datos de la API. El sitio se lo advierte antes de enviarlo y le pide no incluir datos personales ni
información reservada. El Worker no guarda el texto: solo cuenta cuántos análisis se hicieron.
