import os
import signal
import sys
import asyncio
import random
import json
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from aiohttp import web

# ---------------- CONFIGURACIÓN DEL BOT ----------------
intents = discord.Intents.default()

TEXT_CHANNEL_ID = 1571922687708897290  
OCULIN_EMOJI = "🕷️"

# Credenciales de Upstash Redis
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

# Estado global principal de la mascota principal
estado_mascota = {
    "hambre": 50,
    "felicidad": 50
}

# Almacén de inventarios y atributos por usuario en memoria
inventarios_usuarios = {}

http_session: aiohttp.ClientSession = None

estado_modificado = False
ya_se_desperto = False

async def cargar_estado_nube():
    global estado_mascota, inventarios_usuarios
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        print("Advertencia: Faltan las credenciales de Upstash Redis en el entorno.")
        return

    url = f"{UPSTASH_URL}/get/oculin_estado"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    
    try:
        async with http_session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                result = data.get("result")
                if result:
                    datos_cargados = json.loads(result)
                    estado_mascota["hambre"] = datos_cargados.get("hambre", 50)
                    estado_mascota["felicidad"] = datos_cargados.get("felicidad", 50)
                    inventarios_usuarios = datos_cargados.get("inventarios", {})
                    print("Estado e inventarios cargados exitosamente desde Upstash Redis.")
    except Exception as e:
        print(f"No se pudo cargar el estado de la nube: {e}")

async def guardar_estado_nube():
    global estado_modificado
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return

    url = f"{UPSTASH_URL}/set/oculin_estado"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    payload = json.dumps({
        "hambre": estado_mascota["hambre"],
        "felicidad": estado_mascota["felicidad"],
        "inventarios": inventarios_usuarios
    })
    
    try:
        async with http_session.post(url, headers=headers, data=payload) as resp:
            if resp.status == 200:
                estado_modificado = False
            else:
                print(f"Error al guardar en Upstash: {resp.status}")
    except Exception as e:
        print(f"Error de red al guardar estado en la nube: {e}")

def marcar_cambio():
    global estado_modificado
    estado_modificado = True

def obtener_datos_usuario(user_id: str):
    if user_id not in inventarios_usuarios:
        inventarios_usuarios[user_id] = {
            "monedas": 0,
            "objetos": [],
            "nucleos_aceleracion": 0,
            "cantidad_oculins": 1  # Empieza con 1 Oculin por defecto
        }
    # Asegurar retrocompatibilidad si el usuario ya existía sin esta clave
    if "cantidad_oculins" not in inventarios_usuarios[user_id]:
        inventarios_usuarios[user_id]["cantidad_oculins"] = 1
    return inventarios_usuarios[user_id]

def cooldown_segundos(datos: dict) -> float:
    nucleos = datos.get("nucleos_aceleracion", 0)
    cd = 30.0
    for _ in range(nucleos):
        cd = cd * 0.75
    return max(1.0, round(cd, 1))

def calcular_cooldown(interaction: discord.Interaction) -> app_commands.Cooldown | None:
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    segundos = cooldown_segundos(datos)
    return app_commands.Cooldown(1, segundos)

ATMOSPHERIC_MESSAGES = [
    "*chillido extraño*",
    "*sonido de araña alien*",
    "*Empieza a volar por ahí*",
    "Wuahhh",
    "¡Recuerde: un Oculin feliz es un hogar seguro a prueba de explosiones planetarias!",
    "¡La mascota oficial del extinto planeta Oculus directo a tu consola!",
    "¡No alimente a su Oculin con productos no autorizados o la garantía universal quedará anulada!"
]

def clamp(val: int) -> int:
    return max(0, min(100, val))

# ---------------- CLASE PRINCIPAL DEL BOT ----------------
class OculinBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        global http_session
        http_session = aiohttp.ClientSession()
        
        await cargar_estado_nube()
        
        try:
            synced = await self.tree.sync()
            print(f"Se sincronizaron {len(synced)} comandos de barra.")
        except Exception as e:
            print(f"Error al sincronizar comandos: {e}")
            
        decaer_estado.start()
        guardado_automatico.start()

bot = OculinBot()

@bot.tree.error
async def on_app_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Estás usando este comando muy seguido. Espera {error.retry_after:.1f}s."
    else:
        msg = "💥 Ocurrió un error inesperado al procesar la orden de Oculin."
        print(f"Error en comando: {error}")
    
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

@tasks.loop(minutes=10)
async def decaer_estado():
    estado_mascota["hambre"] = clamp(estado_mascota["hambre"] + 5)
    if estado_mascota["hambre"] > 70:
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] - 3)
    marcar_cambio()

@tasks.loop(seconds=30)
async def guardado_automatico():
    if estado_modificado:
        await guardar_estado_nube()

@decaer_estado.before_loop
@guardado_automatico.before_loop
async def before_loops():
    await bot.wait_until_ready()

@tasks.loop(minutes=20)
async def atmospheric_loop():
    try:
        channel = bot.get_channel(TEXT_CHANNEL_ID) or await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            frase = random.choice(ATMOSPHERIC_MESSAGES)
            await channel.send(frase)
    except Exception as e:
        print(f"Error en el bucle atmosférico: {e}")

@atmospheric_loop.before_loop
async def before_atmospheric_loop():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    global ya_se_desperto
    print(f"Sesión iniciada como: {bot.user.name} (ID: {bot.user.id})")
    
    if not ya_se_desperto:
        ya_se_desperto = True
        try:
            channel = bot.get_channel(TEXT_CHANNEL_ID) or await bot.fetch_channel(TEXT_CHANNEL_ID)
            if channel:
                await channel.send("*se despierta*")
        except Exception as e:
            print(f"No se pudo enviar el mensaje 'se despierta': {e}")
    
    if not atmospheric_loop.is_running():
        atmospheric_loop.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user.mentioned_in(message) and not message.mention_everyone:
        try:
            emoji = discord.utils.get(message.guild.emojis, name="ahh") if message.guild else None
            if emoji:
                await message.add_reaction(emoji)
            else:
                await message.add_reaction("👀")
        except Exception as e:
            print(f"Error al reaccionar: {e}")

    await bot.process_commands(message)

# ---------------- COMANDOS ----------------
class JuegoView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="¿Jugar?", url=url, emoji="🕹️"))

@bot.tree.command(name="jugar", description="Inicia un juego interactivo del universo de Oculin.")
@app_commands.describe(nombre="El nombre del juego que deseas abrir")
@app_commands.choices(nombre=[
    app_commands.Choice(name="Lükaa Ocular V13", value="lukaa")
])
async def jugar(interaction: discord.Interaction, nombre: app_commands.Choice[str]):
    if nombre.value == "lukaa":
        url_juego = "https://lukasraptorz99-lang.github.io/"
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} Lükaa ocular V13",
            description="Las sombras acechan en el servidor. Presiona el botón de abajo para entrar al juego y sobrevivir.",
            color=0xaa0000
        )
        embed.set_footer(text="Sinteks Labs / Oculin System")
        await interaction.response.send_message(embed=embed, view=JuegoView(url_juego))

@bot.tree.command(name="estado", description="Muestra el estado de ánimo y hambre de Oculin.")
async def estado(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    hambre = estado_mascota["hambre"]
    felicidad = estado_mascota["felicidad"]
    
    animo = "😁 Muy feliz" if felicidad > 75 else ("😐 Neutral" if felicidad > 40 else "💀 Deprimido / Enojado")
    saciado = "🟢 Saciado" if hambre < 30 else ("🟡 Con algo de apetito" if hambre < 70 else "🔴 ¡Muerto de hambre!")

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} Estado de la criatura",
        description=f"Diagnóstico actual (Tienes **{datos.get('cantidad_oculins', 1)}** Oculin(s) bajo tu control):",
        color=0x7289da
    )
    embed.add_field(name="Felicidad", value=f"{felicidad}/100\n{animo}", inline=False)
    embed.add_field(name="Hambre", value=f"{hambre}/100\n{saciado}", inline=False)
    embed.set_footer(text="Usa /inventario para ver tus créditos y objetos.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="acariciar", description="Dale mimos a Oculin para aumentar su felicidad.")
@app_commands.checks.dynamic_cooldown(calcular_cooldown)
async def acariciar(interaction: discord.Interaction):
    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 15)
    marcar_cambio()
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} ✨ ¡Acariciado!",
        description="Le das palmaditas con cuidado. Oculin emite un zumbido extrañamente tierno. *¡Su felicidad ha aumentado!*",
        color=0x00aa00
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tienda", description="Compra accesorios, núcleos o un Oculin extra para explorar en paralelo.")
@app_commands.describe(articulo="Elige qué accesorio o mejora deseas adquirir")
@app_commands.choices(articulo=[
    app_commands.Choice(name="Sombrero de copa invisible", value="sombrero"),
    app_commands.Choice(name="Gafas de sol de alta definición", value="gafas"),
    app_commands.Choice(name="Batería nuclear barata", value="bateria"),
    app_commands.Choice(name="Núcleo de Aceleración (100 créditos - Reduce CD 25%)", value="nucleo"),
    app_commands.Choice(name="Oculin de Repuesto (500 créditos - Permite explorar en paralelo)", value="oculin_extra")
])
@app_commands.checks.dynamic_cooldown(calcular_cooldown)
async def tienda(interaction: discord.Interaction, articulo: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    
    if articulo.value == "nucleo":
        cd_actual = cooldown_segundos(datos)
        if cd_actual <= 1.0:
            await interaction.response.send_message("⚠️ Ya has alcanzado el límite máximo de reducción de cooldown (1.0s).", ephemeral=True)
            return

        if datos["monedas"] < 100:
            await interaction.response.send_message(f"❌ No tienes suficientes créditos. Tienes **{datos['monedas']}** 🪙 y necesitas **100** 🪙.", ephemeral=True)
            return
            
        datos["monedas"] -= 100
        datos["nucleos_aceleracion"] = datos.get("nucleos_aceleracion", 0) + 1
        marcar_cambio()
        
        nuevo_cd = cooldown_segundos(datos)
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} ⚡ ¡Núcleo de Aceleración Adquirido!",
            description=f"Has comprado un núcleo tecnológico. Tiempos de espera reducidos un **25%**.\n⏱️ Cooldown actual: **{nuevo_cd}s**.",
            color=0x00ffcc
        )
        await interaction.response.send_message(embed=embed)
        return

    if articulo.value == "oculin_extra":
        if datos["monedas"] < 500:
            await interaction.response.send_message(f"❌ Necesitas **500 créditos** 🪙 para clonar/comprar otro Oculin. Tienes **{datos['monedas']}** 🪙.", ephemeral=True)
            return
            
        datos["monedas"] -= 500
        datos["cantidad_oculins"] = datos.get("cantidad_oculins", 1) + 1
        marcar_cambio()
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} 🕷️ ¡Nuevo Oculin Adquirido!",
            description=f"Has adquirido un espécimen adicional de la colmena. Ahora posees **{datos['cantidad_oculins']} Oculins** y puedes recolectar recompensas múltiples al explorar.",
            color=0x9b59b6
        )
        await interaction.response.send_message(embed=embed)
        return

    if datos["monedas"] < 50:
        await interaction.response.send_message(f"❌ Este accesorio cuesta **50 créditos** 🪙 y tú tienes **{datos['monedas']}** 🪙.", ephemeral=True)
        return

    datos["monedas"] -= 50
    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 20)
    datos["objetos"].append(articulo.name)
    marcar_cambio()
    
    descripciones = {
        "sombrero": "¡Has equipado un sombrero de copa totalmente invisible! Nadie lo ve, pero Oculin camina con elegancia intergaláctica.",
        "gafas": "Le colocas unas gafas de sol de alta definición sobre sus múltiples ojos. Estilo moderno activado.",
        "bateria": "Le das una batería nuclear barata para que juegue. Emana un brillo radioactivo, ¡y le encanta!"
    }
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 🛍️ Catálogo de Accesorios Universales",
        description=descripciones[articulo.value],
        color=0xffaa00
    )
    embed.set_footer(text="¡Felicidad incrementada, 50 créditos gastados y objeto añadido a tu inventario!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="alimentar", description="Dale de comer a Oculin (solo le gusta la lechuga 🥬).")
@app_commands.describe(comida="¿Qué objeto o alimento le vas a dar?")
@app_commands.checks.dynamic_cooldown(calcular_cooldown)
async def alimentar(interaction: discord.Interaction, comida: str):
    comida_limpia = comida.strip()
    
    if "🥬" in comida_limpia or "lechuga" in comida_limpia.lower():
        estado_mascota["hambre"] = clamp(estado_mascota["hambre"] - 35)
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 10)
        marcar_cambio()
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} 🍽️ ¡Ñam... ñam!",
            description="Oculin devora la lechuga con desesperación absoluta y emite un sonido extrañamente feliz. *¡Hambre reducida!*",
            color=0x00aa00
        )
        await interaction.response.send_message(embed=embed)
    else:
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] - 10)
        marcar_cambio()
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} ❌ ¡Rechazado!",
            description=f"Oculin desintegra tu **{comida_limpia}** con la mirada. *¡Exige lechuga (🥬)!*",
            color=0xaa0000
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="explorar", description="Manda a tus Oculins a buscar chatarra y ruinas del extinto planeta Oculus en paralelo.")
@app_commands.checks.dynamic_cooldown(calcular_cooldown)
async def explorar(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    cantidad = datos.get("cantidad_oculins", 1)
    
    hallazgos_posibles = [
        ("🔋 Batería de plasma descompuesta", 10, 5, 25),
        ("🧩 Fragmento de datos corruptos", 15, 10, 40),
        ("🕳️ Cayó en un cráter oscuro y asustó", -10, 5, 10),
        ("✨ Mineral brillante de Oculus", 20, 0, 50)
    ]
    
    resultados_texto = []
    total_creditos = 0
    
    # Realiza una expedición por cada Oculin que posea el usuario
    for i in range(cantidad):
        nombre_objeto, inc_felicidad, inc_hambre, creditos_ganados = random.choice(hallazgos_posibles)
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + inc_felicidad)
        estado_mascota["hambre"] = clamp(estado_mascota["hambre"] + inc_hambre)
        
        total_creditos += creditos_ganados
        datos["objetos"].append(nombre_objeto)
        resultados_texto.append(f"• **Oculin #{i+1}:** {nombre_objeto} (+{creditos_ganados} 🪙)")

    datos["monedas"] += total_creditos
    marcar_cambio()

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 🛰️ Expedición de Flota ({cantidad} Oculins)",
        description=f"Tus especímenes despliegan sus alas y regresan del vacío trayendo botín simultáneo:\n\n" + "\n".join(resultados_texto) + f"\n\n💰 **Total ganado:** +{total_creditos} créditos.",
        color=0x3498db
    )
    embed.set_footer(text="Usa /vender para comercializar tus hallazgos o /inventario.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vender", description="Vende los objetos y chatarra que han encontrado tus Oculins a cambio de créditos.")
@app_commands.checks.dynamic_cooldown(calcular_cooldown)
async def vender(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    
    objetos = datos.get("objetos", [])
    if not objetos:
        await interaction.response.send_message("❌ Tu inventario de objetos está vacío. ¡Usa `/explorar` para conseguir chatarra!", ephemeral=True)
        return
        
    ganancia_total = len(objetos) * 15
    datos["monedas"] += ganancia_total
    datos["objetos"] = [] 
    marcar_cambio()
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 💰 Comercio Intergaláctico",
        description=f"Has vendido toda la chatarra acumulada por tus expediciones en el mercado negro de Oculus.\n\n✨ Total entregado: **{len(objetos)} objetos**\n💵 Ganancia neta: **+{ganancia_total} créditos**",
        color=0xf1c40f
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="inventario", description="Muestra tus créditos, cantidad de Oculins, núcleos y objetos.")
@app_commands.checks.dynamic_cooldown(calcular_cooldown)
async def inventario(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    
    creditos = datos.get("monedas", 0)
    nucleos = datos.get("nucleos_aceleracion", 0)
    cantidad_oculins = datos.get("cantidad_oculins", 1)
    objetos = datos.get("objetos", [])
    cd_actual = cooldown_segundos(datos)
    
    lista_objetos = ", ".join(objetos[:10]) if objetos else "Ninguno"
    if len(objetos) > 10:
        lista_objetos += f" y {len(objetos) - 10} más..."

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 🎒 Inventario de {interaction.user.display_name}",
        description="Estado de tus recursos en la red de Oculus:",
        color=0x2ecc71
    )
    embed.add_field(name="Créditos", value=f"{creditos} 🪙", inline=True)
    embed.add_field(name="Oculins en propiedad", value=f"{cantidad_oculins} 🕷️", inline=True)
    embed.add_field(name="Núcleos de Aceleración", value=f"{nucleos} ⚡", inline=True)
    embed.add_field(name="Cooldown Actual", value=f"{cd_actual}s", inline=True)
    embed.add_field(name="Chatarra / Objetos en posesión", value=lista_objetos, inline=False)
    embed.set_footer(text="Usa /vender para cambiar la chatarra por créditos o /tienda para mejorar tu equipo.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="espiar", description="Oculin fija todos sus ojos en un usuario para hacerle un diagnóstico psicobiótico.")
@app_commands.describe(usuario="El usuario al que Oculin va a analizar

                       # ---------------- COMANDO /LORE ----------------
class LoreSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(LoreSelectDropdown())

class LoreSelectDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Lükaa", description="El origen del terror ocular y gerente en Sinteks.", emoji="👁️"),
            discord.SelectOption(label="Sr. Diamante", description="Diamante bugueado de la 1.9 y jefe de Sinteks.", emoji="💎"),
            discord.SelectOption(label="Willy", description="De la realeza británica a despertador en Chile.", emoji="📉")
        ]
        super().__init__(placeholder="Elige un personaje para consultar su expediente...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        seleccion = self.values[0]
        
        if seleccion == "Lükaa":
            embed = discord.Embed(
                title=f"{OCULIN_EMOJI} Expediente: Lükaa",
                description="**Historia:** Nació hace más de 2.000.000 de años en el planeta Oculus, de una mezcla entre una ocular y Satanás. Al nacer, al ver que salió bien, Satanás destruyó Oculus y lo llevó al infierno. A los 500.000 años se rebeló y lo destronó. Tras millones de años, cayó en la tierra y se asentó en una cueva rusa hasta que el Sr. Diamante lo contrató en Sinteks Labs.\n\n"
                            "⚔️ **Ataques:**\n"
                            "• **Disparo verde:** Rayo de energía con pequeña explosión.\n"
                            "• **Mutación pasiva:** Deforma el alma del oponente en un ser grotesco.\n"
                            "• **Extensión de dominio (Infierno Infinito):** Cúpula oscura donde es un Dios.\n\n"
                            "👁️ **Apariencia:** Globo ocular sin párpados, iris azul pálido, pupila azul oscuro y brillo azul claro. Por atrás tiene 3 tentáculos (vinotinto, rojo oscuro y rojo).",
                color=0xaa0000
            )
        elif seleccion == "Sr. Diamante":
            embed = discord.Embed(
                title=f"💎 Expediente: Sr. Diamante",
                description="**Historia:** Su nombre verdadero es *Diamante Difous Geminton sedius*. Proviene de un mineral de diamante de la versión 1.9 beta pré-release picado con toque de seda que por un bug cobró vida con inteligencia de jugador promedio y permisos de creativo (volar, fuerza, spawnear bloques). Tras recorrer dimensiones y conseguir un molde de armadura único en las ciudades del End, logró una 'ingeniosa entrevista laboral' para ser gerente y semi-jefe en sedes de Sinteks Labs (WoodLands, Sinteks Office, Infernos Labs y Sinteks Industries), además de ser dueño de un casino.\n\n"
                            "✨ **Habilidades:** Vuelo, superfuerza y capacidad infinita de spawnear diamantes.",
                color=0x00ffff
            )
        elif seleccion == "Willy":
            embed = discord.Embed(
                title=f"📉 Expediente: Willy",
                description="**Historia:** Nació en el Reino Unido en el seno de una familia real. Tras una crisis económica se mudó a Alemania y, al cabo de 3 años, emigró a Chile en busca de oportunidades. Consiguió empleo en Sinteks como 'despertador humano'. Lamentablemente, tras la disolución de Sinteks, Willy se convirtió en un fracasado que apenas sobrevive para comer.",
                color=0x95a5a6
            )
            
        embed.set_footer(text="Sinteks Labs / Archivos Confidenciales de Oculus")
        await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="lore", description="Consulta los expedientes e historia de los personajes del universo de Oculin.")
async def lore(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} Base de Datos de Lore - Sinteks Labs",
        description="Selecciona en el menú desplegable de abajo el archivo histórico del personaje que deseas investigar.",
        color=0x7289da
    )
    await interaction.response.send_message(embed=embed, view=LoreSelectView())

# ---------------- SERVIDOR WEB PARA RENDER ----------------
async def handle(request):
    return web.Response(text="Oculin Bot está vivo y operando 24/7.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Servidor web corriendo en el puerto {port}")

# ---------------- INTERCEPTAR APAGADO ----------------
async def shutdown():
    print("Señal de apagado recibida, guardando estado y cerrando sesión...")
    await guardar_estado_nube()
    
    try:
        channel = bot.get_channel(TEXT_CHANNEL_ID) or await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("*se duerme*")
            await asyncio.sleep(1)
    except Exception as e:
        print(f"No se pudo enviar el mensaje 'se duerme': {e}")
    
    if http_session and not http_session.closed:
        await http_session.close()
        
    await bot.close()

# ---------------- PUNTO DE ENTRADA PRINCIPAL ----------------
async def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("Error: La variable de entorno DISCORD_TOKEN no está configurada.")
        return
    
    await start_web_server()
    
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass

    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    
