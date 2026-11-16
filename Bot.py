import os
import signal
import sys
import asyncio
import random
import json
import discord
from discord import app_commands
from discord.ext import commands, tasks
from aiohttp import web

# ---------------- CONFIGURACIÓN DEL BOT ----------------
intents = discord.Intents.default()
intents.message_content = True

TEXT_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 1546286007308255234))  
OCULIN_EMOJI = "🕷️"

# Archivo local para persistencia del Tamagotchi
ESTADO_FILE = "estado_oculin.json"

def cargar_estado():
    if os.path.exists(ESTADO_FILE):
        try:
            with open(ESTADO_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"hambre": 50, "felicidad": 50}

def guardar_estado():
    try:
        with open(ESTADO_FILE, "w") as f:
            json.dump(estado_mascota, f)
    except Exception as e:
        print(f"Error al guardar estado: {e}")

estado_mascota = cargar_estado()

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

# ---------------- SERVIDOR WEB PARA RENDER async ----------------
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

# ---------------- CLASE PRINCIPAL DEL BOT CON SETUP_HOOK ----------------
class OculinBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.web_task = None

    async def setup_hook(self):
        self.web_task = asyncio.create_task(start_web_server())
        
        try:
            synced = await self.tree.sync()
            print(f"Se sincronizaron {len(synced)} comandos de barra.")
        except Exception as e:
            print(f"Error al sincronizar comandos: {e}")
            
        decaer_estado.start()

bot = OculinBot()

# ---------------- MANEJADOR GLOBAL DE ERRORES DE COMANDOS ----------------
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

# ---------------- TAREAS EN SEGUNDO PLANO ----------------
@tasks.loop(minutes=10)
async def decaer_estado():
    estado_mascota["hambre"] = clamp(estado_mascota["hambre"] + 5)
    if estado_mascota["hambre"] > 70:
        estado_mascota["felicidad"] = clamp(estado_mascota["felicidad"] - 3)
    guardar_estado()

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

# ---------------- EVENTOS ----------------
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
            description="Las sombras acechan en el servidor. Presiona el botón
            
