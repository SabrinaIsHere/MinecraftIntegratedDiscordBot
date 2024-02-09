import os
import subprocess
from subprocess import PIPE, Popen

import re
import traceback
import time

import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Amount of ram in gigabytes allocated to the minecraft server
RAM_AMOUNT = 2


server_on = False

console_id = 1204923440084025415
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


# General Utility Functions
# Class because of being annoyed with globals
class GenUtility():
    def __init__(self) -> None:
        # Used to output from a log file to get around subprocess limitations
        self.log = "logs/latest.log"
        f = open(self.log)
        self.previous_content = f.read()
        f.close()
    
    def read(self) -> str:
        '''Largely from https://stackoverflow.com/questions/20892875/using-python-to-communicate-with-a-minecraft-server'''
        content = ''
        out = ''
        if server_on:
            f = open(self.log)
            content = f.read()
            t = content
            if self.previous_content in content:
                out = content.replace(self.previous_content, '')
            self.previous_content = t
            f.close()
        return out

    def write(self, msg: str):
        minecraft_server.stdin.write(msg + '\r\n')
        minecraft_server.stdin.flush()

util = GenUtility()


class NetworkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.port_maintainer.start()
    
    def cog_unload(self):
        self.port_maintainer.cancel()

    @tasks.loop(seconds=45.0)
    async def port_maintainer(self):
        if server_on:
            await port_forward()


class ConsoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ch = bot.get_channel(console_id)
        self.printer.start()
    
    def cog_unload(self):
        self.printer.cancel()

    @tasks.loop(seconds=1.0)
    async def printer(self):
        if server_on:
            out = util.read()
            if (not out == '') and len(out) >= 2000:
                n = (len(out) // 2000) + 1
                for i in range(n):
                    await self.ch.send(out[(i * 2000):(i + 1) * 2000])
            elif (not out == ''):
                await self.ch.send(out)
            if not out == '':
                print(out.strip())

    
    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author == bot.user:
            return
        #await bot.process_commands(msg)
        if msg.channel.id == console_id and not msg.content.startswith('!'):
            print(f'Handling {msg.content}')
            util.write(msg.content)


@bot.event
async def on_ready():
    await bot.add_cog(ConsoleCog(bot))
    await bot.add_cog(NetworkCog(bot))
    print(f'{bot.user} is Connected')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send('Please Enter All Required Arguments')
    else:
        print(error)
        print(traceback.format_exc())


# Commands
@bot.command(name='stop', help='Stop either the bot or minecraft server, depending on the first arg (bot/server)')
async def on_stop(ctx, service: str):
    if service == 'bot':
        await ctx.send('Stopping Bot...')
        exit()
    elif service == 'server':
        global server_on
        await ctx.send('Stopping Server...')
        await bot.change_presence(activity=None)
        stop_minecraft()
    else:
        await ctx.send('Please enter a valid argument (bot/server)')


@bot.command(name='start', help='Start the minecraft server')
async def start_server_cmd(ctx):
    await ctx.send('Starting Server...')
    ch = bot.get_channel(console_id)
    await ch.send('Server Starting...')
    await start_minecraft()
    await ctx.send(f'IP: {get_ip()}')
    await ctx.send(re.search('Mapped public port [\d]* protocol TCP to local port 25565', await port_forward()).group())


@bot.command(name='send', help='Send a message to the minecraft server')
async def message(ctx, *, msg: str):
    await ctx.send('Sending...')
    print_to_minecraft(msg)


@bot.command(name='cmd', help='Send a command to the minecraft server. Do not start the command with \'/\'.')
async def minecraft_cmd(ctx, *, msg: str):
    await ctx.send('Sending...')
    exec_minecraft_cmd("/" + msg)


@bot.command(name='dump', help='Dump output from the server')
async def dump(ctx):
    out = util.read()
    if out == None or out == '':
        await ctx.send('No data to relay')
    else:
        await ctx.send(out)


# Minecraft utility functions
async def start_minecraft():
    global minecraft_server
    global server_on
    print('Starting Minecraft')
    cmd = f'java -Xms{RAM_AMOUNT}G -Xmx{RAM_AMOUNT}G -jar server.jar nogui'
    minecraft_server = Popen(args=cmd.split(" "), stdin=PIPE, text=True)
    print(f"PID: {minecraft_server.pid}")
    server_on = True


def stop_minecraft():
    exec_minecraft_cmd('/stop')
    minecraft_server.stdin.close()


async def port_forward():
    str = subprocess.run(['natpmpc', '-a', '25565', '25565', 'tcp', '60', '-g', '10.96.0.1'], stdout=PIPE, stderr=subprocess.STDOUT, text=True).stdout
    status = re.search("public port [\d]*", str).group()[12:]
    status = get_ip() + ":" + status
    await bot.change_presence(activity=discord.Game(name=status))
    return str


def get_ip():
    return subprocess.run(['curl', 'ip.me'], stdout=PIPE, text=True).stdout


def print_to_minecraft(msg: str):
    exec_minecraft_cmd(f'/say {msg}')


def exec_minecraft_cmd(cmd: str):
    util.write(cmd)


bot.run(TOKEN)