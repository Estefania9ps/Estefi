"""
iGaming Intel Bot — Análisis competitivo de operadores españoles (DGOJ)
Requiere: python-telegram-bot>=20.0, anthropic, python-dotenv
"""

import os
import json
import asyncio
import logging
from dotenv import load_dotenv
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")

if not TELEGRAM_TOKEN or not ANTHROPIC_KEY:
    raise RuntimeError("Faltan variables de entorno. Revisa el archivo .env")

ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ── Operadores de acceso rápido ───────────────────────────────────────────────
QUICK_OPS = [
    ("Codere",            "https://www.codere.es"),
    ("Luckia",            "https://www.luckia.es"),
    ("Sportium",          "https://www.sportium.es"),
    ("Bet365",            "https://www.bet365.es"),
    ("LeoVegas",          "https://www.leovegas.es"),
    ("PlayUZU",           "https://www.playuzu.com"),
    ("Casino Gran Madrid","https://www.casinogranmadrid.es"),
    ("Bwin",              "https://www.bwin.es"),
    ("888 Casino",        "https://www.888casino.es"),
    ("William Hill",      "https://www.williamhill.es"),
    ("Betfair",           "https://www.betfair.es"),
    ("PokerStars",        "https://www.pokerstars.es"),
]

SYSTEM_PROMPT = """Eres un analista experto en el mercado iGaming español regulado por DGOJ.

Genera un análisis competitivo completo del operador indicado basándote en tu conocimiento.

REGLAS:
- Si no tienes datos fiables de un campo, escribe "No disponible"
- No inventes números exactos que no conozcas
- Para booleanos usa "Sí" o "No"
- Arrays vacíos si no hay datos: []

Responde ÚNICAMENTE con JSON válido, sin markdown, sin explicaciones:

{"operador":{"nombre":"","url":"","licencia_dgoj":"","año_lanzamiento":"","grupo_corporativo":""},"casino":{"total_slots":"","total_ruletas":"","total_juegos_mesa":"","total_live_casino":"","total_juegos_general":"","proveedores":[],"categorias":[]},"bienvenida":{"oferta_casino":"","oferta_sports":"","requisito_apuesta":"","deposito_minimo":"","importe_maximo":"","dias_validez":"","condiciones_destacadas":""},"promociones":{"recarga":"","cashback":"","torneos":"","free_spins":"","otras":[]},"vip":{"tiene_vip":"","nombre_programa":"","niveles":[],"beneficios_destacados":""},"app":{"tiene_app_ios":"","tiene_app_android":"","valoracion_ios":"","valoracion_android":""},"deportes":{"tiene_apuestas_deportivas":"","mercados_destacados":[],"apuestas_en_vivo":"","cash_out":""},"metodos_pago":{"deposito":[],"retiro":[],"tiempo_retiro":"","minimo_deposito":"","minimo_retiro":""},"soporte":{"chat_en_vivo":"","horario":"","email":"","telefono":""},"marketing":{"redes_sociales":[],"afiliados":"","notas":""},"resumen_competitivo":{"fortalezas":[],"debilidades":[],"diferenciadores":[]}}"""


# ── Llamada a Claude ──────────────────────────────────────────────────────────
def analyze_operator(url: str) -> dict:
    """Llama a Claude y devuelve el JSON parseado."""
    try:
        name = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    except Exception:
        name = url

    msg = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Analiza el operador iGaming español: {url} ({name}). Devuelve el JSON completo con todos los campos."
        }]
    )

    raw = msg.content[0].text.strip()
    # Limpiar posibles fences de markdown
    raw = raw.replace("```json", "").replace("```", "").strip()
    start = raw.index("{")
    end   = raw.rindex("}") + 1
    return json.loads(raw[start:end])


# ── Formateador de respuesta Telegram ────────────────────────────────────────
def na(v):
    return not v or str(v).strip() in ("", "No disponible", "No encontrado")

def val(v, fallback="No disponible"):
    return fallback if na(v) else str(v)

def yesno(v):
    if str(v).lower() in ("sí", "si", "yes", "true", "1"): return "✅ Sí"
    if str(v).lower() in ("no", "false", "0"):              return "❌ No"
    return val(v)

def arr(lst, bullet="•"):
    if not lst or not isinstance(lst, list) or len(lst) == 0:
        return "  _No disponible_"
    return "\n".join(f"  {bullet} {i}" for i in lst)

def format_report(d: dict) -> str:
    op   = d.get("operador", {})
    cas  = d.get("casino", {})
    bv   = d.get("bienvenida", {})
    pro  = d.get("promociones", {})
    vip  = d.get("vip", {})
    app  = d.get("app", {})
    dep  = d.get("deportes", {})
    pag  = d.get("metodos_pago", {})
    sop  = d.get("soporte", {})
    mkt  = d.get("marketing", {})
    res  = d.get("resumen_competitivo", {})

    provs = ", ".join(cas.get("proveedores", [])) or "No disponible"
    cats  = ", ".join(cas.get("categorias",  [])) or "No disponible"

    def taglist(lst): return ", ".join(lst) if lst else "No disponible"

    lines = [
        f"🎰 *{val(op.get('nombre'), 'Operador')}* — Informe Competitivo",
        f"🔗 {val(op.get('url'))}",
        f"📋 Licencia DGOJ: `{val(op.get('licencia_dgoj'))}`",
        f"🏢 Grupo: {val(op.get('grupo_corporativo'))}  |  📅 Año: {val(op.get('año_lanzamiento'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🎰 *CASINO & JUEGOS*",
        f"  🎮 Total juegos: *{val(cas.get('total_juegos_general'))}*",
        f"  🎰 Slots: *{val(cas.get('total_slots'))}*",
        f"  🎡 Ruletas: *{val(cas.get('total_ruletas'))}*",
        f"  🃏 Mesa: *{val(cas.get('total_juegos_mesa'))}*",
        f"  📹 Live Casino: *{val(cas.get('total_live_casino'))}*",
        f"  🏭 Proveedores ({len(cas.get('proveedores',[]))}): _{provs}_",
        f"  📂 Categorías ({len(cas.get('categorias',[]))}): _{cats}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🎁 *BIENVENIDA*",
        f"  Casino: {val(bv.get('oferta_casino'))}",
        f"  Sports: {val(bv.get('oferta_sports'))}",
        f"  Req. apuesta: {val(bv.get('requisito_apuesta'))}",
        f"  Depósito mín: {val(bv.get('deposito_minimo'))}  |  Máximo: {val(bv.get('importe_maximo'))}",
        f"  Validez: {val(bv.get('dias_validez'))}",
        f"  📌 {val(bv.get('condiciones_destacadas'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💰 *PROMOCIONES*",
        f"  Recarga: {val(pro.get('recarga'))}",
        f"  Cashback: {val(pro.get('cashback'))}",
        f"  Torneos: {val(pro.get('torneos'))}",
        f"  Free Spins: {val(pro.get('free_spins'))}",
        f"  Otras: _{taglist(pro.get('otras', []))}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👑 *VIP*: {yesno(vip.get('tiene_vip'))}",
        f"  Programa: {val(vip.get('nombre_programa'))}",
        f"  Niveles: _{taglist(vip.get('niveles', []))}_",
        f"  Beneficios: {val(vip.get('beneficios_destacados'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📱 *APP MÓVIL*",
        f"  iOS: {yesno(app.get('tiene_app_ios'))}  ⭐ {val(app.get('valoracion_ios'))}",
        f"  Android: {yesno(app.get('tiene_app_android'))}  ⭐ {val(app.get('valoracion_android'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "⚽ *DEPORTES*",
        f"  Apuestas deportivas: {yesno(dep.get('tiene_apuestas_deportivas'))}",
        f"  Live betting: {yesno(dep.get('apuestas_en_vivo'))}  |  Cash-out: {yesno(dep.get('cash_out'))}",
        f"  Mercados: _{taglist(dep.get('mercados_destacados', []))}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💳 *MÉTODOS DE PAGO*",
        f"  Depósito: _{taglist(pag.get('deposito', []))}_",
        f"  Retiro: _{taglist(pag.get('retiro', []))}_",
        f"  Tiempo retiro: {val(pag.get('tiempo_retiro'))}",
        f"  Mín depósito: {val(pag.get('minimo_deposito'))}  |  Mín retiro: {val(pag.get('minimo_retiro'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💬 *SOPORTE*",
        f"  Chat en vivo: {yesno(sop.get('chat_en_vivo'))}  |  Horario: {val(sop.get('horario'))}",
        f"  Email: {val(sop.get('email'))}  |  Tel: {val(sop.get('telefono'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📣 *MARKETING*",
        f"  Redes: _{taglist(mkt.get('redes_sociales', []))}_",
        f"  Afiliados: {val(mkt.get('afiliados'))}",
        f"  Notas: {val(mkt.get('notas'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 *ANÁLISIS COMPETITIVO*",
        "💪 Fortalezas:",
        arr(res.get("fortalezas", [])),
        "⚠️ Debilidades:",
        arr(res.get("debilidades", [])),
        "⚡ Diferenciadores:",
        arr(res.get("diferenciadores", [])),
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "ℹ️ _Análisis basado en conocimiento de IA · Verifica datos en la web del operador_",
    ]
    return "\n".join(lines)


# ── Handlers de Telegram ──────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton(name, callback_data=f"op:{url}")]
        for name, url in QUICK_OPS
    ]
    # 2 columnas
    kb_2col = [kb[i:i+2] for i in range(0, len(kb), 2)]

    await update.message.reply_text(
        "🎰 *iGaming Intel* — Análisis competitivo DGOJ\n\n"
        "Envíame la URL de cualquier operador español y te genero un informe completo:\n"
        "juegos • bonos • VIP • pagos • app • marketing\n\n"
        "O elige un operador de acceso rápido 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb_2col)
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Cómo usar iGaming Intel*\n\n"
        "1️⃣ Envía la URL del operador:\n`https://www.codere.es`\n\n"
        "2️⃣ O usa /analizar seguido de la URL:\n`/analizar https://www.luckia.es`\n\n"
        "3️⃣ O escoge un operador con /start\n\n"
        "El bot analizará: slots, ruletas, live casino, proveedores, categorías, "
        "oferta de bienvenida, promociones, VIP, app, métodos de pago, soporte y marketing.\n\n"
        "⏱ El análisis tarda ~15-20 segundos.",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_analizar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("❌ Uso: `/analizar https://www.operador.es`", parse_mode=ParseMode.MARKDOWN)
        return
    url = args[0].strip()
    await run_analysis(update, ctx, url)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.startswith("http://") or text.startswith("https://") or "." in text:
        url = text if text.startswith("http") else "https://" + text
        await run_analysis(update, ctx, url)
    else:
        await update.message.reply_text(
            "👋 Envíame la URL de un operador, por ejemplo:\n`https://www.codere.es`\n\nO usa /start para ver los operadores frecuentes.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("op:"):
        url = query.data[3:]
        # Editar mensaje para quitar teclado
        await query.edit_message_reply_markup(reply_markup=None)
        # Crear un objeto Update-like para reutilizar run_analysis
        await run_analysis_query(query, ctx, url)

async def run_analysis(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text(f"🔍 Analizando *{url}*…\n\n⏱ Esto puede tardar 15-20 segundos.", parse_mode=ParseMode.MARKDOWN)
    await _do_analysis(msg, ctx, url)

async def run_analysis_query(query, ctx, url: str):
    msg = await query.message.reply_text(f"🔍 Analizando *{url}*…\n\n⏱ Esto puede tardar 15-20 segundos.", parse_mode=ParseMode.MARKDOWN)
    await _do_analysis(msg, ctx, url)

async def _do_analysis(status_msg, ctx, url: str):
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, analyze_operator, url)
        report = format_report(data)

        # Telegram tiene límite de 4096 chars; dividir si es necesario
        if len(report) <= 4096:
            await status_msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        else:
            await status_msg.delete()
            chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for chunk in chunks:
                await ctx.bot.send_message(
                    chat_id=status_msg.chat_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN
                )

    except json.JSONDecodeError as e:
        await status_msg.edit_text(f"❌ Error al parsear la respuesta de la IA: {e}\n\nIntenta de nuevo.")
    except Exception as e:
        log.error("Error en análisis: %s", e, exc_info=True)
        await status_msg.edit_text(f"❌ Error: {e}\n\nIntenta de nuevo o prueba con otra URL.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("analizar", cmd_analizar))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("🎰 iGaming Intel Bot arrancado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
