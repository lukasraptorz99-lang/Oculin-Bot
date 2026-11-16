import os
import asyncio
import random
import signal
import discord
from discord.ext import commands, tasks
from aiohttp import web

# Configuración básica de intents
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ID de tu canal de texto para los ruidos
TEXT_CHANNEL_ID = 1546286007308255239  

@bot.event
async def on_ready():
    print(f"[DISCORD] ¡Sesión iniciada con éxito como {bot.user}")
    
    # Enviar un mensaje inmediato al despertar
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        try:
            await channel.send("*se despierta*")
            print("[TEXTO] Mensaje inicial enviado: *se despierta*")
        except Exception as e:
            print(f"[ERROR DE TEXTO] No se pudo enviar el mensaje inicial: {e}")

    # Iniciar la tarea de ruidos si no está corriendo
    if not spooky_noises_task.is_running():
        spooky_noises_task.start()
        print("[TEXTO] Tarea de ruidos atmosféricos iniciada.")

# Tarea en bucle para mandar ruidos extraños cada 20 minutos
@tasks.loop(minutes=20)
async def spooky_noises_task():
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        noise = random.choice(["*sonido de araña alien*", "*chillido extraño*"])
        try:
            await channel.send(noise)
            print(f"[TEXTO] Mensaje enviado: {noise}")
        except Exception as e:
            print(f"[ERROR DE TEXTO] No se pudo enviar el mensaje: {e}")

@spooky_noises_task.before_loop
async def before_spooky_noises():
    await bot.wait_until_ready()

# Función para manejar el apagado elegante y mandar el mensaje de despedida
async def shutdown():
    print("[DISCORD] Apagando el bot...")
    channel = bot.get_channel(TEXT_CHANNEL_ID)
    if channel:
        try:
            await channel.send("*se duerme*")
            print("[TEXTO] Mensaje de apagado enviado: *se duerme*")
            # Pequeña pausa para asegurar que Discord procese el mensaje antes de cortar
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[ERROR DE TEXTO] No se pudo enviar el mensaje de apagado: {e}")
    await bot.close()

# Servidor HTTP dummy para que Render detecte el servicio web activo
async def handle(request):
    return web.Response(text="Bot de texto activo 24/7 en Render")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[WEB] Servidor dummy activo en el puerto {port}")

async def main():
    await start_web_server()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("[ERROR] No se encontró la variable de entorno DISCORD_TOKEN.")
        return

    # Capturar señales de apagado de Render (SIGTERM / SIGINT)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            # En algunos sistemas operativos (como Windows local) no soporta signal handlers de la misma forma
            pass

    try:
        await bot.start(token)
    finally:
        await shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
        
