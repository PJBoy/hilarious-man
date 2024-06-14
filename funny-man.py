import daemons
import discord
import aiohttp, colour as color
import argparse, bisect, json, logging, pathlib, random, re, string, traceback, urllib.parse
from collections import namedtuple


# Set up #
logging.basicConfig(level = logging.INFO)

def parseJsonFile(filepath):
    with argparse.FileType()(filepath) as f:
        return json.load(f)

argparser = argparse.ArgumentParser(description = 'Run Hilarious Man, the Discord bot for you and me.')
argparser.add_argument('config', type = parseJsonFile, nargs = '?', default = parseJsonFile(pathlib.PurePath(argparser.prog).with_suffix('.json')), help = 'Filepath to JSON file containing Hilarious Man configuration')
args = argparser.parse_args()


# Define bot #
intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents = intents)

@bot.event
async def on_ready():
    logging.info('Servers:')
    for server in bot.guilds:
        logging.info(f'{server} - {server.id!r}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if await trySimpleCommands(message):
        return
    
    await tryCommands(message)

def init():
    def loadSimpleCommands():
        global SimpleCommand, simpleCommands, commandRequests
        
        SimpleCommand = namedtuple('SimpleCommand', ['server', 'regex', 'message'])
        simpleCommands = []
        try:
            with open('commands.json') as f:
                simpleCommands = [SimpleCommand(*command) for command in json.load(f)]
        except FileNotFoundError as e:
            pass

        commandRequests = []

    def loadRamMap():
        global ramMap, ramMapKeys
        
        ramMap = {}

        with open('RAM map.asm', 'r') as f:
            for line in f:
                if 'VRAM (in word addresses, not byte addresses)' in line:
                    break

                match = re.match(r'\s*\$([0-7][0-9A-F]+)(?::([0-9A-F]+))?(:|\.\.).+', line, re.IGNORECASE)
                if not match:
                    continue

                address = int(match[1], 16)
                if match[2]:
                    address = address << 16 | int(match[2], 16)
                else:
                    address |= 0x7E0000

                ramMap[address] = match[0]

        ramMapKeys = list(ramMap.keys())

    def loadMiscFiles():
        global pokemon, nicks
        
        with open('pokemon.json', 'r') as f:
            pokemon = json.load(f)

        with open('nicks.json', 'r') as f:
            nicks = json.load(f)
    
    async def startDaemons():
        for task in daemons.tasks:
            bot.loop.create_task(task(bot))

    loadSimpleCommands()
    loadRamMap()
    loadMiscFiles()
    bot.setup_hook = startDaemons

async def trySimpleCommands(message):
    if message.guild is None:
        return
        
    for command in simpleCommands:
        if command.server != message.guild.id:
            continue
            
        if command.regex.startswith('/'):
            match = re.match(command.regex, message.content, re.I)
        else:
            match = re.search(command.regex, message.content, re.I)
        if match:
            await message.channel.send(command.message)
            return True
    
    return False

async def tryCommands(message):
    for command in commands:
        match = re.match(command.regex, message.content, re.DOTALL)
        if match:
            try:
                await command.callback(message, match)
                return
            except Exception as e:
                logging.warning(f'Command {command.regex!r} failed:')
                logging.warning(traceback.format_exc())
    
Command = namedtuple('Command', ['regex', 'callback'])
commands = []
def makeCommand(regex):
    def callback(callback):
        global commands
        
        commands += [Command(regex, callback)]
    
    return callback


# Bot commands #
@makeCommand(r'/stadium *(\d*)')
async def stadium(message, match):
    'Picks three random Kanto pokemon and three random Johto pokemon'

    if match[1] and int(match[1]) == 2:
        await message.channel.send('\n'.join(f'{x}: {pokemon[x - 1]}' for x in sorted(random.sample(range(1, 149), 3) + random.sample(range(152, 248), 3))))
    else:
        await message.channel.send('\n'.join(f'{x}: {pokemon[x - 1]}' for x in sorted(random.sample(range(1, 149), 6))))

@makeCommand(r'/aram2pc\s+(.+)')
async def aram2pc(message, match):
    'Calculates the file offset of an ARAM address'

    translations = [
        (0x1500, 0x56E2, 0x278104 + 4), # Main SPC engine
        (0x5820, 0x5828, 0x27C2EA + 4), # Trackers
        (0x6C00, 0x6C90, 0x278000 + 4), # ADSR settings
        (0x6D00, 0x6D60, 0x27CF81 + 4), # Sample table
        (0x6E00, 0xB516, 0x27D025 + 4)  # Sample data
    ]

    address = int(''.join(c for c in match[1] if c in string.hexdigits), 16)
    if address < 0x1500:
        await message.channel.send(f'${address:04X} is in SPC general purpose RAM, not loaded from ROM')
        return

    if address >= 0x10000:
        await message.channel.send(f'${address:X} is outside the ARAM address space')
        return

    for (begin_aram, end_aram, begin_pc) in translations:
        if begin_aram <= address < end_aram:
            await message.channel.send(f'${address - begin_aram + begin_pc:06X}')
            return
    else:
        await message.channel.send(f'${address:04X} is song-specific data, no unique ROM address')

@makeCommand(r'/gb2pc\s+(.+)')
async def gb2pc(message, match):
    'Calculates the file offset of a game boy address'

    address = int(''.join(c for c in match[1] if c in string.hexdigits), 16)
    await message.channel.send(f'${address >> 2 & ~0x3FFF | address & 0x3FFF:05X}')

@makeCommand(r'/pc2gb\s+(.+)')
async def pc2gb(message, match):
    'Calculates a game boy address from a file offset'

    address = int(''.join(c for c in match[1] if c in string.hexdigits), 16)
    if address < 0x4000:
        await message.channel.send(f'${address:04X}')
    else:
        await message.channel.send(f'${address >> 14:X}:{address & 0x3FFF | 0x4000:04X}')

@makeCommand(r'/snes2pc\s+(.+)')
async def snes2pc(message, match):
    'Calculates the file offset of a SNES address'

    address = int(''.join(c for c in match[1] if c in string.hexdigits), 16)
    await message.channel.send(f'${address >> 1 & 0x3F8000 | address & 0x7FFF:06X}')

@makeCommand(r'/pc2snes\s+(.+)')
async def pc2snes(message, match):
    'Calculates a SNES address from a file offset'

    address = int(''.join(c for c in match[1] if c in string.hexdigits), 16)
    await message.channel.send(f'${address >> 15 | 0x80:02X}:{address & 0xFFFF | 0x8000:04X}')

@makeCommand(r'/sm_?w?ram\s+(.+)')
async def smRam(message, match):
    'Looks up RAM address in Super Metroid RAM map'

    address = int(''.join(c for c in match[1] if c in string.hexdigits), 16) | 0x7E0000
    await message.channel.send(ramMap[ramMapKeys[bisect.bisect(ramMapKeys, address) - 1]])

@makeCommand(r'/yt\s+(.+)')
async def yt(message, match):
    'Returns the first result for a youtube search'

    youtube_url_results = 'http://www.youtube.com/results'
    youtube_url_watch = 'http://www.youtube.com/watch'

    async def yt_search(query):
        async with aiohttp.ClientSession() as session:
            async with session.get(youtube_url_results, params = {'q': query}) as r:
                if r.status != 200:
                    await message.channel.send(f'YouTube error: `{r.status} - {r.reason}`')
                    raise RuntimeError(f'{r.status} - {r.reason}')
                    
                source = await r.text()
                return re.findall(r'"\/watch\?v=(.{11})', source)

    def yt_watch_url(videoId):
        queryString = urllib.parse.urlencode({'v': videoId})
        return f'{youtube_url_watch}?{queryString}'

    query = match[1]
    results = await yt_search(query)
    if len(results) == 0:
        await message.channel.send('No results')
        return

    firstResult = results[0]

    await message.channel.send(f'{yt_watch_url(firstResult)}')

@makeCommand(r'/add_?command\s+"(.+?)"\s+"(.+?)"')
async def addSimpleCommand(message, match):
    'Add a command. Format: /add "regex" "message"'
    
    regex, response = match[1], match[2]

    # Check if valid regex
    try:
        re.compile(regex, re.IGNORECASE)
    except re.error as e:
        await message.channel.send(f'Invalid regex "{e.pattern}": {e.msg}')
        return

    # Add to queue
    global commandRequests
    commandRequests += [SimpleCommand(message.guild.id, regex, response)]
    await message.channel.send(f'Your command has been requested, you are number {len(commandRequests)} in the queue')

@makeCommand(r'/approve(?:\s+(\d+))?')
async def approveSimpleCommand(message, match):
    'Approves a command. Request queue is 1-indexed'
    
    global simpleCommands

    if match[1]:
        id = int(match[1])
    else:
        id = 1

    # Assert privilege
    if message.author.id != args.config['adminId']:
        logging.info(f"{message.author.id = } != {args.config['adminId'] = }")
        await message.channel.send('Denied')
        return

    # Assert valid id
    if not 1 <= id <= len(commandRequests):
        await message.channel.send('Invalid request id')
        return

    # Instatiate command and remove from requests queue
    command = commandRequests.pop(id - 1)
    simpleCommands += [command]

    # Add to simple commands JSON file
    with open('commands.json', 'w') as f:
        json.dump(simpleCommands, f, indent = 4)

    await message.channel.send(f'Approved command: {command.regex}')

@makeCommand(r'/deny(?:\s+(\d+))?')
async def denySimpleCommand(message, match):
    'Denies a command. Request queue is 1-indexed'
    
    if match[1]:
        id = int(match[1])
    else:
        id = 1

    # Assert privilege
    if message.author.id != args.config['adminId']:
        await message.channel.send('Denied')
        return

    # Assert valid id
    if not 1 <= id <= len(commandRequests):
        await message.channel.send('Invalid request id')
        return

    command = commandRequests.pop(id - 1)
    await message.channel.send(f'Denied command: {command.regex}')


init()
bot.run(args.config['token'])
