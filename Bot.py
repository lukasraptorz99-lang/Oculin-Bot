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
intents.message_content = True

TEXT_CHANNEL_ID = 1571922687708897290  
OCULIN_EMOJI = "🕷️"

# Credenciales de Upstash Redis
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "https://endless-octopus-173709.upstash.io")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "gQAAAAAAAqaNAAIgcDFjYmNjNmY1NzQ2YjA0NzgwYWVjMmQyZjAzZWJkM2ZiMw")

# Estado global del Tamagotchi y de la economía de los usuarios
estado_mascota = {
    "hambre": 50,
    "felicidad": 50
}

# Almacén de inventarios y núcleos por usuario en memoria (sincronizable con Upstash)
inventarios_usuarios = {}

async def cargar_estado_nube():
    global estado_mascota, inventarios_usuarios
    url = f"{UPSTASH_URL}/get/oculin_estado"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result")
                    if result:
                        datos_cargados = json.loads(result)
                        estado_mascota["hambre"] = datos_cargados.get("hambre", 50)
                        estado_mascota["felicidad"] = datos_cargados.get("felicidad", 50)
                        global inventarios_usuarios
                        inventarios_usuarios = datos_cargados.get("inventarios", {})
                        print("Estado e inventarios cargados exitosamente desde Upstash Redis.")
    except Exception as e:
        print(f"No se pudo cargar el estado de la nube: {e}")

async def guardar_estado_nube():
    url = f"{UPSTASH_URL}/set/oculin_estado"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    payload = json.dumps({
        "hambre": estado_mascota["hambre"],
        "felicidad": estado_mascota["felicidad"],
        "inventarios": inventarios_usuarios
    })
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=payload) as resp:
                if resp.status != 200:
                    print(f"Error al guardar en Upstash: {resp.status}")
    except Exception as e:
        print(f"Error de red al guardar estado en la nube: {e}")

def obtener_datos_usuario(user_id: str):
    if user_id not in inventarios_usuarios:
        inventarios_usuarios[user_id] = {
            "monedas": 0,
            "objetos": [],
            "nucleos_aceleracion": 0
        }
    return inventarios_usuarios[user_id]

def calcular_cooldown(user_id: str, base_cooldown: float = 30.0) -> float:
    """Reduce el cooldown un 25% por cada núcleo comprado, con un límite de 1.0s."""
    datos = obtener_datos_usuario(user_id)
    nucleos = datos.get("nucleos_aceleracion", 0)
    
    cd = base_cooldown
    for _ in range(nucleos):
        cd = cd * 0.75  # Reduce un 25%
        
    return max(1.0, round(cd, 1))

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

# ---------------- CLASE PRINCIPAL DEL BOT ----------------
class OculinBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        await cargar_estado_nube()
        
        try:
            synced = await self.tree.sync()
            print(f"Se sincronizaron {len(synced)} comandos de barra.")
        except Exception as e:
            print(f"Error al sincronizar comandos: {e}")
            
        decaer_estado.start()

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
    await guardar_estado_nube()

@decaer_estado.before_loop
async def before_decaer_estado():
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
    print(f"Sesión iniciada como: {bot.user.name} (ID: {bot.user.id})")
    
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
    hambre = estado_mascota["hambre"]
    felicidad = estado_mascota["felicidad"]
    
    animo = "😁 Muy feliz" if felicidad > 75 else ("😐 Neutral" if felicidad > 40 else "💀 Deprimido / Enojado")
    saciado = "🟢 Saciado" if hambre < 30 else ("🟡 Con algo de apetito" if hambre < 70 else "🔴 ¡Muerto de hambre!")

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} Estado de la criatura",
        description="Diagnóstico actual del espécimen (de los últimos sobrevivientes del planeta Oculus):",
        color=0x7289da
    )
    embed.add_field(name="Felicidad", value=f"{felicidad}/100\n{animo}", inline=False)
    embed.add_field(name="Hambre", value=f"{hambre}/100\n{saciado}", inline=False)
    embed.set_footer(text="Usa /inventario para ver tus monedas y objetos.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="acariciar", description="Dale mimos a Oculin para aumentar su felicidad.")
async def acariciar(interaction: discord.Interaction):
    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 15)
    await guardar_estado_nube()
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} ✨ ¡Acariciado!",
        description="Le das palmaditas con cuidado. Oculin emite un zumbido extrañamente tierno. *¡Su felicidad ha aumentado!*",
        color=0x00aa00
    )
    await interaction.response.send_message(embed=embed)

@acariciar.dynamic_cooldown
def acariciar_cd(interaction: discord.Interaction):
    cd = calcular_cooldown(str(interaction.user.id), 30.0)
    return app_commands.Cooldown(1, cd)

@bot.tree.command(name="tienda", description="Compra accesorios o el Núcleo de Aceleración para reducir tus cooldowns.")
@app_commands.describe(articulo="Elige qué accesorio o mejora deseas adquirir")
@app_commands.choices(articulo=[
    app_commands.Choice(name="Sombrero de copa invisible", value="sombrero"),
    app_commands.Choice(name="Gafas de sol de alta definición", value="gafas"),
    app_commands.Choice(name="Batería nuclear barata", value="bateria"),
    app_commands.Choice(name="Núcleo de Aceleración (100 monedas - Reduce CD 25%)", value="nucleo")
])
async def tienda(interaction: discord.Interaction, articulo: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    
    if articulo.value == "nucleo":
        if datos["monedas"] < 100:
            await interaction.response.send_message(f"❌ No tienes suficientes monedas. Tienes **{datos['monedas']}** 🪙 y necesitas **100** 🪙.", ephemeral=True)
            return
        
        if datos.get("nucleos_aceleracion", 0) >= 12: 
            await interaction.response.send_message("⚠️ Ya has alcanzado el límite máximo de reducción de cooldown (1.0s).", ephemeral=True)
            return
            
        datos["monedas"] -= 100
        datos["nucleos_aceleracion"] = datos.get("nucleos_aceleracion", 0) + 1
        await guardar_estado_nube()
        
        nuevo_cd = calcular_cooldown(user_id, 30.0)
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} ⚡ ¡Núcleo de Aceleración Adquirido!",
            description=f"Has comprado un núcleo tecnológico. Tus tiempos de espera ahora se reducen un **25%**.\n⏱️ Tu nuevo cooldown actual es de **{nuevo_cd}s**.",
            color=0x00ffcc
        )
        await interaction.response.send_message(embed=embed)
        return

    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 20)
    datos["objetos"].append(articulo.name)
    await guardar_estado_nube()
    
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
    embed.set_footer(text="¡Felicidad incrementada y objeto añadido a tu inventario!")
    await interaction.response.send_message(embed=embed)

@tienda.dynamic_cooldown
def tienda_cd(interaction: discord.Interaction):
    cd = calcular_cooldown(str(interaction.user.id), 30.0)
    return app_commands.Cooldown(1, cd)

@bot.tree.command(name="alimentar", description="Dale de comer a Oculin (solo le gusta la lechuga 🥬).")
@app_commands.describe(comida="¿Qué objeto o alimento le vas a dar?")
async def alimentar(interaction: discord.Interaction, comida: str):
    comida_limpia = comida.strip()
    
    if "🥬" in comida_limpia or "lechuga" in comida_limpia.lower():
        estado_mascota["hambre"] = clamp(estado_mascota["hambre"] - 35)
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 10)
        await guardar_estado_nube()
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} 🍽️ ¡Ñam... ñam!",
            description="Oculin devora la lechuga con desesperación absoluta y emite un sonido extrañamente feliz. *¡Hambre reducida!*",
            color=0x00aa00
        )
        await interaction.response.send_message(embed=embed)
    else:
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] - 10)
        await guardar_estado_nube()
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} ❌ ¡Rechazado!",
            description=f"Oculin desintegra tu **{comida_limpia}** con la mirada. *¡Exige lechuga (🥬)!*",
            color=0xaa0000
        )
        await interaction.response.send_message(embed=embed)

@alimentar.dynamic_cooldown
def alimentar_cd(interaction: discord.Interaction):
    cd = calcular_cooldown(str(interaction.user.id), 30.0)
    return app_commands.Cooldown(1, cd)

@bot.tree.command(name="explorar", description="Manda a Oculin a buscar chatarra y ruinas del extinto planeta Oculus.")
async def explorar(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    
    hallazgos = [
        ("🔋 Batería de plasma descompuesta", 10, 5, 25),
        ("🧩 Fragmento de datos corruptos", 15, 10, 40),
        ("🕳️ Cayó en un cráter oscuro y asustó", -10, 5, 10),
        ("✨ Mineral brillante de Oculus", 20, 0, 50)
    ]
    
    nombre_objeto, inc_felicidad, inc_hambre, monedas_ganadas = random.choice(hallazgos)
    
    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + inc_felicidad)
    estado_mascota["hambre"] = clamp(estado_mascota["hambre"] + inc_hambre)
    
    datos["monedas"] += monedas_ganadas
    datos["objetos"].append(nombre_objeto)
    await guardar_estado_nube()

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 🛰️ Expedición Planetaria",
        description=f"Oculin despliega sus alas y regresa del vacío trayendo botín.\n\n**Encontraste:** {nombre_objeto}\n💰 Has ganado **+{monedas_ganadas} monedas**.",
        color=0x3498db
    )
    embed.set_footer(text="Usa /vender para comercializar tus hallazgos o /inventario.")
    await interaction.response.send_message(embed=embed)

@explorar.dynamic_cooldown
def explorar_cd(interaction: discord.Interaction):
    cd = calcular_cooldown(str(interaction.user.id), 30.0)
    return app_commands.Cooldown(1, cd)

@bot.tree.command(name="vender", description="Vende los objetos y chatarra que has encontrado explorando a cambio de monedas.")
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
    await guardar_estado_nube()
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 💰 Comercio Intergaláctico",
        description=f"Has vendido toda tu chatarra acumulada en el mercado negro de Oculus.\n\n✨ Total entregado: **{len(objetos)} objetos**\n💵 Ganancia neta: **+{ganancia_total} monedas**",
        color=0xf1c40f
    )
    await interaction.response.send_message(embed=embed)

@vender.dynamic_cooldown
def vender_cd(interaction: discord.Interaction):
    cd = calcular_cooldown(str(interaction.user.id), 30.0)
    return app_commands.Cooldown(1, cd)

@bot.tree.command(name="inventario", description="Muestra tus monedas, núcleos de aceleración y objetos recolectados.")
async def inventario(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    datos = obtener_datos_usuario(user_id)
    
    monedas = datos.get("monedas", 0)
    nucleos = datos.get("nucleos_aceleracion", 0)
    objetos = datos.get("objetos", [])
    cd_actual = calcular_cooldown(user_id, 30.0)
    
    lista_objetos = ", ".join(objetos[:10]) if objetos else "Ninguno"
    if len(objetos) > 10:
        lista_objetos += f" y {len(objetos) - 10} más..."

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 🎒 Inventario de {interaction.user.display_name}",
        description="Estado de tus recursos en la red de Oculus:",
        color=0x2ecc71
    )
    embed.add_field(name="Monedas", value=f"{monedas} 🪙", inline=True)
    embed.add_field(name="Núcleos de Aceleración", value=f"{nucleos} ⚡", inline=True)
    embed.add_field(name="Cooldown Actual de Comandos", value=f"{cd_actual}s", inline=True)
    embed.add_field(name="Chatarra / Objetos en posesión", value=lista_objetos, inline=False)
    embed.set_footer(text="Usa /vender para cambiar la chatarra por monedas o /tienda para mejorar tu equipo.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="espiar", description="Oculin fija todos sus ojos en un usuario para hacerle un diagnóstico psicobiótico.")
@app_commands.describe(usuario="El usuario al que Oculin va a analizar con sus múltiples ojos")
async def espiar(interaction: discord.Interaction, usuario: discord.Member):
    nivel_locura = random.randint(0, 100)
    diagnosticos = [
        "Apto para la supervivencia en Oculus.",
        "Riesgo moderado de mutación por radiación cuántica.",
        "Absolutamente inestable, podría desintegrarse en cualquier momento.",
        "Posee una extraña resistencia mental a las sombras."
    ]
    diagnostico = random.choice(diagnosticos)

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} 👁️ Escaneo Ocular",
        description=f"Oculin clava sus múltiples ojos en **{usuario.mention}** durante varios segundos...",
        color=0x9b59b6
    )
    embed.add_field(name="Índice de Locura Ocular", value=f"{nivel_locura}%", inline=False)
    embed.add_field(name="Diagnóstico del espécimen", value=diagnostico, inline=False)
    embed.set_footer(text="Sistema de vigilancia intergaláctica Oculin.")
    
    await interaction.response.send_message(embed=embed)

@espiar.dynamic_cooldown
def espiar_cd(interaction: discord.Interaction):
    cd = calcular_cooldown(str(interaction.user.id), 30.0)
    return app_commands.Cooldown(1, cd)

# ---------------- INTERCEPTAR APAGADO ----------------
async def shutdown():
    try:
        channel = bot.get_channel(TEXT_CHANNEL_ID) or await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("*se duerme*")
            await asyncio.sleep(1)
    except Exception as e:
