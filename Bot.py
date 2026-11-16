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

# ID del canal principal donde Oculin enviará los mensajes automáticos
TEXT_CHANNEL_ID = 1546286007308255239  # Cambia esto por el ID de tu canal de texto principal si lo deseas

# Lista de frases atmosféricas y de terror
ATMOSPHERIC_MESSAGES = [
    "chillido extraño",
    "sonido de araña alien",
    "wuaaaaah",
    "*empieza a volar por ahi*"
]

# ---------------- SERVIDOR WEB PARA RENDER async ----------------
async def handle(request):
    return web.Response(text="Oculin Bot está vivo y operando 24/7.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render asigna dinámicamente un puerto mediante la variable de entorno PORT (por defecto 10000)
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Servidor web corriendo en el puerto {port}")

# ---------------- TAREAS Y CICLO DE VIDA ----------------
@tasks.loop(minutes=20)
async def atmospheric_loop():
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        import random
        frase = random.choice(ATMOSPHERIC_MESSAGES)
        await channel.send(frase)

@bot.event
async def on_ready():
    print(f"Sesión iniciada como: {bot.user.name} (ID: {bot.user.id})")
    
    # Sincronizamos los comandos de barra (slash commands) con Discord
    try:
        synced = await bot.tree.sync()
        print(f"Se sincronizaron {len(synced)} comandos de barra.")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

    # Mensaje de inicio en el canal principal
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        await channel.send("se despierta")
    
    # Iniciamos el bucle de mensajes atmosféricos si no está corriendo
    if not atmospheric_loop.is_running():
        atmospheric_loop.start()

# ---------------- BOTÓN INTERACTIVO PARA EL JUEGO ----------------
class JuegoView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()
        # Botón interactivo con el texto requerido
        self.add_item(discord.ui.Button(label="¿Jugar?", url=url, emoji="🕹️"))

# ---------------- COMANDO /JUGAR ----------------
@bot.tree.command(name="jugar", description="Inicia un juego interactivo del universo de Oculin.")
@app_commands.describe(nombre="El nombre del juego que deseas abrir")
async def jugar(interaction: discord.Interaction, nombre: str):
    juego_lower = nombre.lower().strip()
    
    # Verificamos si el usuario solicita el juego de Lükaa
    if "lükaa" in juego_lower or "luka" in juego_lower:
        url_juego = "https://lukasraptorz99-lang.github.io/"
        
        embed = discord.Embed(
            title="Lükaa ocular V13",
            description="Las sombras acechan en el servidor. Presiona el botón de abajo para entrar al juego y sobrevivir.",
            color=0xaa0000  # Color rojo atmosférico
        )
        
        # Agregamos el GIF animado junto a la tarjeta
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1546286007308255234/1571712687606595635/GIF_20261102_154546_388.gif?ex=6afbbb01&is=6afa6981&hm=f949b5cfc90fdbd9f26a8d94728a547b97467a925f05d05a7919ff2561ce0b11&")
        embed.set_footer(text="Sinteks Labs / Oculin System")
        
        await interaction.response.send_message(embed=embed, view=JuegoView(url_juego))
    else:
        await interaction.response.send_message(
            f"Lo siento, no encontré ningún juego registrado con el nombre **'{nombre}'**. ¡Prueba escribiendo *Lükaa Ocular V13*!",
            ephemeral=True
        )

# ---------------- APAGADO GRACIÓSO (SHUTDOWN) ----------------
async def graceful_shutdown(signal_name):
    print(f"Recibida señal {signal_name}, apagando de forma ordenada...")
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        try:
            await channel.send("se duerme")
            # Damos un pequeño respiro para que el mensaje se alcance a enviar antes de cerrar sesión
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
    # Token del bot obtenido desde las variables de entorno de Render
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("Error: La variable de entorno DISCORD_TOKEN no está configurada.")
        return

    # Configuramos las señales de cierre si el sistema operativo lo soporta (en Linux / Render funciona perfecto)
    if sys.platform != "win32":
        setup_signals()

    # Iniciamos en paralelo el servidor web falso (para Render) y el bot de Discord
    web_task = asyncio.create_start_task = asyncio.create_task(start_web_server())
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")
    finally:
        # Asegurarnos de enviar el mensaje de apagado si ocurre un fallo general
        channel = bot.get_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("se duerme")

if __name__ == "__main__":
    asyncio.run(main())
    
