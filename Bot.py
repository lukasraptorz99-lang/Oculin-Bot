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

# ID del canal principal
TEXT_CHANNEL_ID = 1546286007308255234  

# Representación visual de Oculin en texto/emoji
OCULIN_EMOJI = "🕷️"

# Estado interno del Tamagotchi de Oculin
estado_mascota = {
    "hambre": 50,      # De 0 (lleno) a 100 (muerto de hambre)
    "felicidad": 50    # De 0 (triste/enojado) a 100 (muy feliz)
}

# Lista de frases atmosféricas actualizada
ATMOSPHERIC_MESSAGES = [
    "*chillido extraño*",
    "*sonido de araña alien*",
    "*Empieza a volar por ahí*",
    "Wuahhh"
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
    
    try:
        synced = await bot.tree.sync()
        print(f"Se sincronizaron {len(synced)} comandos de barra.")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

    try:
        channel = await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("*se despierta*")
            print("Mensaje 'se despierta' enviado exitosamente.")
    except Exception as e:
        print(f"No se pudo enviar el mensaje 'se despierta': {e}")
    
    if not atmospheric_loop.is_running():
        atmospheric_loop.start()

# ---------------- EVENTO DE MENSAJES (MENCIONES Y REACCIONES) ----------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

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
            title=f"{OCULIN_EMOJI} Lükaa ocular V13",
            description="Las sombras acechan en el servidor. Presiona el botón de abajo para entrar al juego y sobrevivir.",
            color=0xaa0000
        )
        embed.set_footer(text="Sinteks Labs / Oculin System")
        
        await interaction.response.send_message(embed=embed, view=JuegoView(url_juego))
    else:
        await interaction.response.send_message(
            f"Lo siento, no encontré ningún juego registrado con el nombre **'{nombre}'**. ¡Prueba escribiendo *Lükaa Ocular V13*!",
            ephemeral=True
        )

# ---------------- COMANDO /ESTADO (VER TAMAGOTCHI) ----------------
@bot.tree.command(name="estado", description="Muestra el estado de ánimo y hambre de Oculin.")
async def estado(interaction: discord.Interaction):
    hambre = estado_mascota["hambre"]
    felicidad = estado_mascota["felicidad"]
    
    # Definir texto según la felicidad
    if felicidad > 75:
        animo = "😁 Muy feliz (¡Cuidado, podría estar planeando algo!)"
    elif felicidad > 40:
        animo = "😐 Neutral (Mirando fijamente al vacío)"
    else:
        animo = "💀 Deprimido / Enojado (Emite chillidos de frustración)"

    # Definir texto según el hambre
    if hambre < 30:
        saciado = "🟢 Saciado (Comió suficiente lechuga)"
    elif hambre < 70:
        saciado = "🟡 Con algo de apetito"
    else:
        saciado = "🔴 ¡Muerto de hambre! (Exige 🥬)"

    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} Estado del Sistema Ocular",
        description="Diagnóstico actual de la criatura:",
        color=0x7289da
    )
    embed.add_field(name="Felicidad", value=f"{felicidad}/100\n{animo}", inline=False)
    embed.add_field(name="Hambre", value=f"{hambre}/100\n{saciado}", inline=False)
    embed.set_footer(text="Usa /alimentar con 🥬 y /acariciar para cambiar su estado.")
    
    await interaction.response.send_message(embed=embed)

# ---------------- COMANDO /ACARICIAR ----------------
@bot.tree.command(name="acariciar", description="Dale mimos a Oculin para aumentar su felicidad.")
async def acariciar(interaction: discord.Interaction):
    estado_mascota["felicidad"] = min(100, estado_mascota["felicidad"] + 15)
    
    embed = discord.Embed(
        title=f"{OCULIN_EMOJI} ✨ ¡Acariciado!",
        description="Le das palmaditas con cuidado. Oculin emite un zumbido extrañamente tierno y sus múltiples ojos brillan satisfechos. *¡Su felicidad ha aumentado!*",
        color=0x00aa00
    )
    await interaction.response.send_message(embed=embed)

# ---------------- MINIJUEGO /ALIMENTAR (TAMAGOTCHI DE LECHUGA) ----------------
@bot.tree.command(name="alimentar", description="Dale de comer a Oculin (solo le gusta la lechuga 🥬).")
@app_commands.describe(comida="¿Qué objeto o alimento le vas a dar?")
async def alimentar(interaction: discord.Interaction, comida: str):
    comida_limpia = comida.strip()
    
    if "🥬" in comida_limpia or "lechuga" in comida_limpia.lower():
        estado_mascota["hambre"] = max(0, estado_mascota["hambre"] - 35)
        estado_mascota["felicidad"] = min(100, estado_mascota["felicidad"] + 10)
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} 🍽️ ¡Ñam... ñam!",
            description="Oculin devora la lechuga con desesperación absoluta y emite un sonido extrañamente feliz. *¡Hambre reducida y energía recuperada!*",
            color=0x00aa00
        )
        await interaction.response.send_message(embed=embed)
    else:
        estado_mascota["felicidad"] = max(0, estado_mascota["felicidad"] - 10)
        
        embed = discord.Embed(
            title=f"{OCULIN_EMOJI} ❌ ¡Rechazado!",
            description=f"Oculin mira fijamente tu **{comida_limpia}**, parpadea sin piedad y lo desintegra con la mirada. *¡Se ha enojado un poco! Exige lechuga (🥬).*",
            color=0xaa0000
        )
        await interaction.response.send_message(embed=embed)

# ---------------- APAGADO ORDENADO (SHUTDOWN) ----------------
async def graceful_shutdown(signal_name):
    print(f"Recibida señal {signal_name}, apagando de forma ordenada...")
    try:
        channel = await bot.fetch_channel(TEXT_CHANNEL_ID)
        if channel:
            await channel.send("*se duerme*")
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
                await channel.send("*se duerme*")
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
    
