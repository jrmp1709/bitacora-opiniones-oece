/**
 * Intermediario de CriterIA: recibe el caso del visitante y le pide a Claude que lo analice
 * opinión por opinión. Corre en Cloudflare Workers, gratis para este volumen.
 *
 * Por qué existe: la clave de la API no puede vivir en la página (es pública). El Worker la
 * guarda como secreto, y además:
 *   - solo atiende al sitio (comprueba el origen);
 *   - solo acepta CLAVES de opiniones, nunca textos libres: el material lo toma del propio
 *     data/opiniones.json publicado, así nadie puede usar la clave como un chat general;
 *   - limita por visitante y por día, para que el gasto no se dispare;
 *   - devuelve la respuesta en streaming, para que se lea mientras se escribe.
 *
 * Despliegue: ver proxy/README.md
 */

const MODELO = "claude-opus-5";        // el más capaz; para gastar menos: "claude-sonnet-5" o "claude-haiku-4-5"
const ESFUERZO = "medium";             // low | medium | high | xhigh | max
const MAX_TOKENS = 4000;
const MAX_OPINIONES = 8;               // cuántas opiniones se le mandan como material
const MAX_CASO = 4000;                 // caracteres del caso del visitante
const LIMITE_VISITANTE = 8;            // análisis por visitante y día
const LIMITE_DIA = 250;                // análisis de todo el sitio por día (tope de gasto)
const DATOS = "https://jrmp1709.github.io/bitacora-opiniones-oece/data/opiniones.json";

const SISTEMA = `Eres CriterIA, el asistente documental de la Bitácora de Opiniones de la Dirección Técnico Normativa (OSCE/OECE) del Perú. Analizas el caso de un usuario frente a un conjunto de opiniones que ya fueron seleccionadas por su pertinencia.

Reglas, sin excepción:
1. Usa únicamente el material entregado. No cites opiniones, normas ni artículos que no estén en él, y no completes con conocimiento propio.
2. Analiza opinión por opinión: qué se le preguntó a la DTN, qué concluyó (cita entre comillas lo esencial de la conclusión, literal) y en qué medida alcanza o no al caso del usuario.
3. Distingue el régimen: la Ley N.° 32069 rige desde el 22.04.2025; la Ley N.° 30225 y el D.L. N.° 1017 son anteriores y siguen aplicándose a los contratos y procedimientos iniciados bajo ellas. Advierte cuando el criterio provenga de un régimen distinto al del caso.
4. Si el material no alcanza para el caso, dilo con todas sus letras y señala qué faltaría.
5. No afirmes por tu cuenta que algo procede o no procede: el criterio es de la DTN y el caso puede tener particularidades. Esto no es asesoría legal.
6. Cierra con "Qué revisar": de dos a cuatro puntos concretos, incluido leer el documento oficial de la opinión más cercana.

Forma: español del Perú, claro y directo, 400 palabras como máximo. Cita cada opinión por su número oficial. Sin encabezados decorativos ni listas anidadas.`;

const cabeceras = (origen) => ({
  "Access-Control-Allow-Origin": origen || "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Max-Age": "86400",
  Vary: "Origin",
});

const error = (codigo, mensaje, origen) =>
  new Response(JSON.stringify({ error: mensaje }), {
    status: codigo,
    headers: { ...cabeceras(origen), "content-type": "application/json; charset=utf-8" },
  });

let cache = { cuando: 0, datos: null };

async function opiniones() {
  // El material sale del sitio publicado; se guarda en memoria diez minutos.
  if (cache.datos && Date.now() - cache.cuando < 600000) return cache.datos;
  const r = await fetch(DATOS, { cf: { cacheTtl: 600, cacheEverything: true } });
  if (!r.ok) throw new Error("no se pudo leer la base de opiniones");
  cache = { cuando: Date.now(), datos: await r.json() };
  return cache.datos;
}

function material(datos, claves) {
  const porClave = {};
  for (const r of datos.rows) {
    const k = `${r.y}-${r.s}-${r.op}`;
    if (!claves.includes(k)) continue;
    (porClave[k] = porClave[k] || { r, consultas: [] }).consultas.push(r.q);
  }
  const marco = { 32069: "Ley N.° 32069 (vigente desde el 22.04.2025)", 30225: "Ley N.° 30225 (régimen anterior)", 1017: "D.L. N.° 1017 (régimen anterior)" };
  return claves
    .filter((k) => porClave[k])
    .map((k, i) => {
      const { r, consultas } = porClave[k];
      const cs = (datos.concl || {})[k] || [];
      return [
        `--- Opinión ${i + 1} ---`,
        `Número oficial: ${r.o}`,
        `Fecha: ${r.f}`,
        `Marco: ${marco[r.m] || r.m}`,
        `Asunto: ${(datos.asuntos || {})[k] || "(sin asunto)"}`,
        `Consultas absueltas:`,
        ...consultas.map((q, j) => `  ${j + 1}. ${q}`),
        cs.length ? `Conclusiones de la DTN (texto literal):` : `Conclusiones: (no disponibles)`,
        ...cs.map((c, j) => `  ${j + 1}. ${c}`),
      ].join("\n");
    })
    .join("\n\n");
}

export default {
  async fetch(req, env, ctx) {
    const origen = req.headers.get("Origin") || "";
    const permitidos = (env.ORIGENES || "").split(",").map((s) => s.trim()).filter(Boolean);
    if (req.method === "OPTIONS") return new Response(null, { headers: cabeceras(origen) });
    if (req.method !== "POST") return error(405, "Use POST.", origen);
    if (permitidos.length && !permitidos.includes(origen)) return error(403, "Origen no permitido.", origen);

    let cuerpo;
    try {
      cuerpo = await req.json();
    } catch {
      return error(400, "Cuerpo no válido.", origen);
    }
    const caso = String(cuerpo.caso || "").trim().slice(0, MAX_CASO);
    const claves = Array.isArray(cuerpo.claves) ? cuerpo.claves.slice(0, MAX_OPINIONES).map(String) : [];
    if (caso.length < 20) return error(400, "Cuénteme el caso con un poco más de detalle.", origen);
    if (!claves.length) return error(400, "No se indicaron opiniones que analizar.", origen);

    // Límites: por visitante y para todo el sitio. Sin KV configurado, no se limita.
    const kv = env.LIMITES;
    const hoy = new Date().toISOString().slice(0, 10);
    const ip = req.headers.get("CF-Connecting-IP") || "0.0.0.0";
    const kVisit = `v:${hoy}:${ip}`;
    const kDia = `d:${hoy}`;
    let nVisit = 0;
    let nDia = 0;
    if (kv) {
      [nVisit, nDia] = (await Promise.all([kv.get(kVisit), kv.get(kDia)])).map((x) => parseInt(x || "0", 10));
      if (nVisit >= LIMITE_VISITANTE)
        return error(429, "Por hoy llegó al límite de análisis. Las búsquedas y las conclusiones siguen disponibles.", origen);
      if (nDia >= LIMITE_DIA)
        return error(429, "El análisis con IA alcanzó su límite de hoy. Vuelva mañana; el buscador sigue funcionando.", origen);
    }

    let texto;
    try {
      texto = material(await opiniones(), claves);
    } catch (e) {
      return error(502, "No pude leer la base de opiniones.", origen);
    }
    if (!texto) return error(400, "Las opiniones indicadas no están en la base.", origen);

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: MODELO,
        max_tokens: MAX_TOKENS,
        stream: true,
        thinking: { type: "adaptive" },
        output_config: { effort: ESFUERZO },
        system: [{ type: "text", text: SISTEMA, cache_control: { type: "ephemeral" } }],
        messages: [
          {
            role: "user",
            content: `CASO DEL USUARIO:\n${caso}\n\nOPINIONES SELECCIONADAS DE LA BITÁCORA:\n\n${texto}\n\nAnalice el caso frente a estas opiniones, una por una, siguiendo sus reglas.`,
          },
        ],
      }),
    });

    if (!r.ok) {
      const detalle = await r.text();
      console.log("error de la API:", r.status, detalle.slice(0, 300));
      return error(r.status === 429 ? 429 : 502, r.status === 429 ? "El servicio está saturado; inténtelo en unos minutos." : "No pude completar el análisis.", origen);
    }
    if (kv)
      ctx.waitUntil(
        Promise.all([
          kv.put(kVisit, String(nVisit + 1), { expirationTtl: 172800 }),
          kv.put(kDia, String(nDia + 1), { expirationTtl: 172800 }),
        ])
      );
    return new Response(r.body, {
      headers: { ...cabeceras(origen), "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-store" },
    });
  },
};
