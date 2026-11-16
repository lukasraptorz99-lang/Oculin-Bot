import os
import signal
import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from aiohttp import web

# ---------------- CONFIGURACIÓN DEL BOT ----------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ID del canal principal actualizado
TEXT_CHANNEL_ID = 1546286007308255234  

# Enlace limpio del GIF de Lükaa con audífonos
LUKAA_GIF_URL = "https://cdn.discordapp.com/attachments/1546286007308255234/1571712687606595635/GIF_20261102_154546_388.gif?ex=6afbbb01&is=6afa6981&hm=f949b5cfc90fdbd9f26a8d94728a547b97467a925f05d05a7919ff2561ce0b11&"

# Lista de frases atmosféricas y de terror
ATMOSPHERIC_MESSAGES = [
    "chillido extraño",
    "sonido de araña alien",
    "susurros en la oscuridad",
    "algo se mueve en las sombras...",
    "pisadas lejanas rechinan en el suelo metálico"
]

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

# ---------------- TAREAS Y CICLO DE VIDA ----------------
@tasks.loop(minutes=20)
async def atmospheric_loop():
    try:
        channel = await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            import random
            frase = random.choice(ATMOSPHERIC_MESSAGES)
            await channel.send(frase)
    except Exception as e:
        print(f"Error en el bucle atmosférico: {e}")

@bot.event
async def on_ready():
    print(f"Sesión iniciada como: {bot.user.name} (ID: {bot.user.id})")
    
    # Sincronizamos los comandos de barra con Discord
    try:
        synced = await bot.tree.sync()
        print(f"Se sincronizaron {len(synced)} comandos de barra.")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

    # Forzamos la búsqueda del canal directamente en la API para enviar "se despierta"
    try:
        channel = await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("se despierta")
            print("Mensaje 'se despierta' enviado exitosamente.")
    except Exception as e:
        print(f"No se pudo enviar el mensaje 'se despierta': {e}")
    
    # Iniciamos el bucle de mensajes atmosféricos
    if not atmospheric_loop.is_running():
        atmospheric_loop.start()

# ---------------- EVENTO DE MENSAJES (MENCIONES Y REACCIONES) ----------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Si alguien etiqueta a Oculin en el mensaje
    if bot.user.mentioned_in(message):
        try:
            emoji = discord.utils.get(message.guild.emojis, name="ahh")
            if emoji:
                await message.add_reaction(emoji)
            else:
                await message.add_reaction("👀")
        except Exception as e:
            print(f"No se pudo reaccionar al mensaje: {e}")

    await bot.process_commands(message)

# ---------------- BOTÓN INTERACTIVO PARA EL JUEGO ----------------
class JuegoView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="¿Jugar?", url=url, emoji="🕹️"))

# ---------------- COMANDO /JUGAR ----------------
@bot.tree.command(name="jugar", description="Inicia un juego interactivo del universo de Oculin.")
@app_commands.describe(nombre="El nombre del juego que deseas abrir")
async def jugar(interaction: discord.Interaction, nombre: str):
    juego_lower = nombre.lower().strip()
    
    if "lükaa" in juego_lower or "luka" in juego_lower:
        url_juego = "https://lukasraptorz99-lang.github.io/"
        
        embed = discord.Embed(
            title="Lükaa ocular V13",
            description="Las sombras acechan en el servidor. Presiona el botón de abajo para entrar al juego y sobrevivir.",
            color=0xaa0000
        )
        
        embed.set_thumbnail(url=LUKAA_GIF_URL)
        embed.set_footer(text="Sinteks Labs / Oculin System")
        
        await interaction.response.send_message(embed=embed, view=JuegoView(url_juego))
    else:
        await interaction.response.send_message(
            f"Lo siento, no encontré ningún juego registrado con el nombre **'{nombre}'**. ¡Prueba escribiendo *Lükaa Ocular V13*!",
            ephemeral=True
        )

# ---------------- APAGADO ORDENADO (SHUTDOWN) ----------------
async def graceful_shutdown(signal_name):
    print(f"Recibida señal {signal_name}, apagando de forma ordenada...")
    try:
        channel = await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("se duerme")
            await asyncio.sleep(1)
    except Exception as e:
        print(f"No se pudo enviar el mensaje de cierre: {e}")
    await bot.close()
    sys.exit(0)

def setup_signals():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(graceful_shutdown(s.name)))

# ---------------- PUNTO DE ENTRADA ----------------
async def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("Error: La variable de entorno DISCORD_TOKEN no está configurada.")
        return

    if sys.platform != "win32":
        setup_signals()

    web_task = asyncio.create_task(start_web_server())
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")
    finally:
        try:
            channel = await bot.fetch_channel(TEXT_CHANNEL_ID)
            if channel:
                await channel.send("se duerme")
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
                                
