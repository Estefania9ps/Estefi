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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY")

if not TELEGRAM_TOKEN or not ANTHROPIC_KEY:
    raise RuntimeError("Faltan variables de entorno: TELEGRAM_TOKEN y ANTHROPIC_API_KEY")

ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

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
- Para booleanos usa "Si" o "No"
- Arrays vacíos si no hay datos: []
Responde UNICAMENTE con JSON valido, sin markdown, sin explicaciones:
{"operador":{"nombre":"","url":"","licencia_dgoj":"","año_lanzamiento":"","grupo_corporativo":""},"casino":{"total_slots":"","total_ruletas":"","total_juegos_mesa":"","total_live_casino":"","total_juegos_general":"","proveedores":[],"categorias":[]},"bienvenida":{"oferta_casino":"","oferta_sports":"","requisito_apuesta":"","deposito_minimo":"","importe_maximo":"","dias_validez":"","condiciones_destacadas":""},"promociones":{"recarga":"","cashback":"","torneos":"","free_spins":"","otras":[]},"vip":{"tiene_vip":"","nombre_programa":"","niveles":[],"beneficios_destacados":""},"app":{"tiene_app_ios":"","tiene_app_android":"","valoracion_ios":"","valoracion_android":""},"deportes":{"tiene_apuestas_deportivas":"","mercados_destacados":[],"apuestas_en_vivo":"","cash_out":""},"metodos_pago":{"deposito":[],"retiro":[],"tiempo_retiro":"","minimo_deposito":"","minimo_retiro":""},"soporte":{"chat_en_vivo":"","horario":"","email":"","telefono":""},"marketing":{"redes_sociales":[],"afiliados":"","notas":""},"resumen_competitivo":{"fortalezas":[],"debilidades":[],"diferenciadores":[]}}"""


def analyze_operator(url: str) -> dict:
    try:
        name = url.replace("https://","").replace("http://","").replace("www.","").split("/")[0]
    except Exception:
        name = url

    msg = ai.messages.create(
        model="claude-haiku-4-5",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Analiza el operador iGaming español: {url} ({name}). Devuelve el JSON completo."
        }]
    )
    raw = msg.content[0].text.strip()
    raw = raw.replace("```json","").replace("```","").strip()
    start = raw.index("{")
    end   = raw.rindex("}") + 1
    return json.loads(raw[start:end])


def na(v):
    return not v or str(v).strip() in ("","No disponible","No encontrado")

def val(v, fallback="No disponible"):
    return fallback if na(v) else str(v)

def yesno(v):
    s = str(v).lower()
    if s in ("si","sí","yes","true","1"): return "✅ Si"
    if s in ("no","false","0"):           return "❌ No"
    return val(v)

def arr(lst, bullet="•"):
    if not lst or not isinstance(lst,list) or len(lst)==0:
        return "  No disponible"
    return "\n".join(f"  {bullet} {i}" for i in lst)

def taglist(lst):
    return ", ".join(lst) if lst else "No disponible"

def format_report(d: dict) -> str:
    op  = d.get("operador",{})
    cas = d.get("casino",{})
    bv  = d.get("bienvenida",{})
    pro = d.get("promociones",{})
    vip = d.get("vip",{})
    app = d.get("app",{})
    dep = d.get("deportes",{})
    pag = d.get("metodos_pago",{})
    sop = d.get("soporte",{})
    mkt = d.get("marketing",{})
    res = d.get("resumen_competitivo",{})

    lines = [
        f"🎰 *{val(op.get('nombre'),'Operador')}* — Informe Competitivo",
        f"🔗 {val(op.get('url'))}",
        f"📋 Licencia DGOJ: {val(op.get('licencia_dgoj'))}",
        f"🏢 Grupo: {val(op.get('grupo_corporativo'))}  |  📅 Año: {val(op.get('año_lanzamiento'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🎰 *CASINO Y JUEGOS*",
        f"  🎮 Total: *{val(cas.get('total_juegos_general'))}*",
        f"  🎰 Slots: *{val(cas.get('total_slots'))}*",
        f"  🎡 Ruletas: *{val(cas.get('total_ruletas'))}*",
        f"  🃏 Mesa: *{val(cas.get('total_juegos_mesa'))}*",
        f"  📹 Live: *{val(cas.get('total_live_casino'))}*",
        f"  🏭 Proveedores ({len(cas.get('proveedores',[]))}): {taglist(cas.get('proveedores',[]))}",
        f"  📂 Categorias ({len(cas.get('categorias',[]))}): {taglist(cas.get('categorias',[]))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🎁 *BIENVENIDA*",
        f"  Casino: {val(bv.get('oferta_casino'))}",
        f"  Sports: {val(bv.get('oferta_sports'))}",
        f"  Req apuesta: {val(bv.get('requisito_apuesta'))}",
        f"  Deposito min: {val(bv.get('deposito_minimo'))}  |  Maximo: {val(bv.get('importe_maximo'))}",
        f"  Validez: {val(bv.get('dias_validez'))}",
        f"  📌 {val(bv.get('condiciones_destacadas'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💰 *PROMOCIONES*",
        f"  Recarga: {val(pro.get('recarga'))}",
        f"  Cashback: {val(pro.get('cashback'))}",
        f"  Torneos: {val(pro.get('torneos'))}",
        f"  Free Spins: {val(pro.get('free_spins'))}",
        f"  Otras: {taglist(pro.get('otras',[]))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👑 *VIP*: {yesno(vip.get('tiene_vip'))}",
        f"  Programa: {val(vip.get('nombre_programa'))}",
        f"  Niveles: {taglist(vip.get('niveles',[]))}",
        f"  Beneficios: {val(vip.get('beneficios_destacados'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📱 *APP MOVIL*",
        f"  iOS: {yesno(app.get('tiene_app_ios'))}  ⭐ {val(app.get('valoracion_ios'))}",
        f"  Android: {yesno(app.get('tiene_app_android'))}  ⭐ {val(app.get('valoracion_android'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "⚽ *DEPORTES*",
        f"  Apuestas: {yesno(dep.get('tiene_apuestas_deportivas'))}",
        f"  Live: {yesno(dep.get('apuestas_en_vivo'))}  |  Cash-out: {yesno(dep.get('cash_out'))}",
        f"  Mercados: {taglist(dep.get('mercados_destacados',[]))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💳 *METODOS DE PAGO*",
        f"  Deposito: {taglist(pag.get('deposito',[]))}",
        f"  Retiro: {taglist(pag.get('retiro',[]))}",
        f"  Tiempo retiro: {val(pag.get('tiempo_retiro'))}",
        f"  Min deposito: {val(pag.get('minimo_deposito'))}  |  Min retiro: {val(pag.get('minimo_retiro'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💬 *SOPORTE*",
        f"  Chat: {yesno(sop.get('chat_en_vivo'))}  |  Horario: {val(sop.get('horario'))}",
        f"  Email: {val(sop.get('email'))}  |  Tel: {val(sop.get('telefono'))}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 *ANALISIS COMPETITIVO*",
        "💪 Fortalezas:",
        arr(res.get("fortalezas",[])),
        "⚠️ Debilidades:",
        arr(res.get("debilidades",[])),
        "⚡ Diferenciadores:",
        arr(res.get("diferenciadores",[])),
        "",
        "ℹ️ Analisis basado en IA. Verifica datos en la web del operador.",
    ]
    return "\n".join(lines)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(name, callback_data=f"op:{url}")] for name, url in QUICK_OPS]
    kb_2col = [kb[i:i+2] for i in range(0, len(kb), 2)]
    await update.message.reply_text(
        "🎰 *iGaming Intel* — Analisis competitivo DGOJ\n\n"
        "Enviame la URL de cualquier operador español.\n\n"
        "O elige uno de acceso rapido 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb_2col)
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Como usar iGaming Intel*\n\n"
        "Envia la URL: `https://www.codere.es`\n"
        "O usa: `/analizar https://www.luckia.es`\n"
        "O elige con /start\n\n"
        "⏱ El analisis tarda 15-20 segundos.",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_analizar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Uso: `/analizar https://www.operador.es`", parse_mode=ParseMode.MARKDOWN)
        return
    await run_analysis(update, ctx, ctx.args[0].strip())

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if "." in text and not text.startswith("/"):
        url = text if text.startswith("http") else "https://" + text
        await run_analysis(update, ctx, url)
    else:
        await update.message.reply_text(
            "Enviame la URL de un operador, por ejemplo:\n`https://www.codere.es`\n\nO usa /start",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("op:"):
        url = query.data[3:]
        await query.edit_message_reply_markup(reply_markup=None)
        msg = await query.message.reply_text(
            f"🔍 Analizando *{url}*...\n\n⏱ 15-20 segundos.",
            parse_mode=ParseMode.MARKDOWN
        )
        await _do_analysis(msg, ctx, url)

async def run_analysis(update: Update, ctx: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text(
        f"🔍 Analizando *{url}*...\n\n⏱ 15-20 segundos.",
        parse_mode=ParseMode.MARKDOWN
    )
    await _do_analysis(msg, ctx, url)

async def _do_analysis(status_msg, ctx, url: str):
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, analyze_operator, url)
        report = format_report(data)
        if len(report) <= 4096:
            await status_msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
        else:
            await status_msg.delete()
            for chunk in [report[i:i+4000] for i in range(0, len(report), 4000)]:
                await ctx.bot.send_message(chat_id=status_msg.chat_id, text=chunk, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error("Error: %s", e, exc_info=True)
        await status_msg.edit_text(f"❌ Error: {e}\n\nIntenta de nuevo.")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("analizar", cmd_analizar))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("🎰 iGaming Intel Bot arrancado")
    app.run_polling()

if __name__ == "__main__":
    main()
