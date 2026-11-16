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

TEXT_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 1546286007308255234))  
OCULIN_EMOJI = "🕷️"

# Credenciales de Upstash Redis
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "https://endless-octopus-173709.upstash.io")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "gQAAAAAAAqaNAAIgcDFjYmNjNmY1NzQ2YjA0NzgwYWVjMmQyZjAzZWJkM2ZiMw")

estado_mascota = {
    "hambre": 50,
    "felicidad": 50
}

async def cargar_estado_nube():
    global estado_mascota
    url = f"{UPSTASH_URL}/get/oculin_estado"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result")
                    if result:
                        estado_mascota = json.loads(result)
                        print("Estado cargado exitosamente desde Upstash Redis.")
    except Exception as e:
        print(f"No se pudo cargar el estado de la nube: {e}")

async def guardar_estado_nube():
    url = f"{UPSTASH_URL}/set/oculin_estado"
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    payload = json.dumps(estado_mascota)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=payload) as resp:
                if resp.status != 200:
                    print(f"Error al guardar en Upstash: {resp.status}")
    except Exception as e:
        print(f"Error de red al guardar estado en la nube: {e}")

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
        msg = f"⏳ Oculin está ocupado. Espera {error.retry_after:.1f}s para interactuar de nuevo."
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
    embed.set_footer(text="Usa /alimentar con 🥬, /acariciar o cómprale accesorios en /tienda.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="acariciar", description="Dale mimos a Oculin para aumentar su felicidad.")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
async def acariciar(interaction: discord.Interaction):
    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 15)
    await guardar_estado_nube()
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} ✨ ¡Acariciado!",
        description="Le das palmaditas con cuidado. Oculin emite un zumbido extrañamente tierno. *¡Su felicidad ha aumentado!*",
        color=0x00aa00
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tienda", description="Compra accesorios del catálogo universal para tu Oculin.")
@app_commands.describe(articulo="Elige qué accesorio deseas adquirir")
@app_commands.choices(articulo=[
    app_commands.Choice(name="Sombrero de copa invisible", value="sombrero"),
    app_commands.Choice(name="Gafas de sol de alta definición", value="gafas"),
    app_commands.Choice(name="Batería nuclear barata", value="bateria")
])
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
async def tienda(interaction: discord.Interaction, articulo: app_commands.Choice[str]):
    estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] + 20)
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
    embed.set_footer(text="¡Felicidad incrementada por adquisición exitosa!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="alimentar", description="Dale de comer a Oculin (solo le gusta la lechuga 🥬).")
@app_commands.describe(comida="¿Qué objeto o alimento le vas a dar?")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
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

# ---------------- INTERCEPTAR APAGADO ----------------
async def shutdown():
    try:
        channel = bot.get_channel(TEXT_CHANNEL_ID) or await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("*se duerme*")
            await asyncio.sleep(1)
    except Exception as e:
        print(f"No se pudo enviar el mensaje 'se duerme': {e}")
    
    await bot.close()

# ---------------- PUNTO DE ENTRADA PRINCIPAL ----------------
async def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("Error: La variable de entorno DISCORD_TOKEN no está configurada.")
        return
    
    # 1. Levantar primero el servidor web para que Render detecte el puerto de inmediato
    await start_web_server()
    
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown()))

    # 2. Iniciar el bot de Discord en paralelo
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    
