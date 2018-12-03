import bot, daemons
import discord, discord.ext.commands
import aiohttp
import argparse, bisect, json, logging, pathlib, random, re, string, urllib.parse
from collections import namedtuple

logging.basicConfig(level = logging.INFO)

# Set up #
def parseJsonFile(filepath):
    with argparse.FileType()(filepath) as f:
        return json.load(f)

argparser = argparse.ArgumentParser(description = 'Run Hilarious Man, the Discord bot for you and me.')
argparser.add_argument('config', type = parseJsonFile, nargs = '?', default = parseJsonFile(pathlib.PurePath(argparser.prog).with_suffix('.json')), help = 'Filepath to JSON file containing Hilarious Man configuration')
args = argparser.parse_args()

# Define bot #
bot = bot.RegexBot(command_prefix = '', help_attrs = {'name': r'/help'}, formatter = bot.HelpFormatter(), description = 'Hilarious Man, the bot for you and me. Commands listed below are regular expressions')

@bot.command(r'/hack')
async def hackSearch(context, *, query : str):
    'Searches for a hack on MetConst'

    metconst_url_hacks = 'http://metroidconstruction.com/hacks.php'
    metconst_url_hack = 'http://metroidconstruction.com/hack.php'
    metconst_url_files = 'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8001'
    metconst_url_forum_profile = 'http://forum.metroidconstruction.com/'

    async def metconst_search(query):
        async with aiohttp.get(metconst_url_hacks, params = {'search': query}) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            
            source = await r.text()
            match = re.search(r'hack\.php\?id=(\d+)', source)
            return match[1] if match else None

    async def metconst_id(hackId):
        async with aiohttp.get(metconst_url_hack, params = {'id': hackId}) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            
            source = await r.text()
            match = re.search(r'<title>(.+?) - Metroid Construction</title>', source)
            title = match[1] if match else None
            match = re.search(r'<b>Author:</b>\s*<a href=".+?action=profile;u=(\d+)">(.+?)</a>', source)
            authorId, author = match[1], match[2] if match else [None] * 2
            screenshotUrls = re.findall(fr'<img src=".+?files/hacks/{hackId}/(.+?)".*?>', source)
            return title, author, authorId, screenshotUrls

    def metconst_forum_profile_url(userId):
        queryString = urllib.parse.urlencode({'action': 'profile', 'u': userId})
        return f'{metconst_url_forum_profile}?{queryString}'

    hackId = await metconst_search(query)
    if not hackId:
        await bot.say('No results')
        return

    title, author, authorId, screenshotUrls = await metconst_id(hackId)
    
    queryString = urllib.parse.urlencode({'id': hackId})
    hackUrl = f'{metconst_url_hack}?{queryString}'
    
    embed = discord.Embed(title = title, url = hackUrl, colour = context.message.author.colour)
    if screenshotUrls:
        screenshotUrl = random.sample(screenshotUrls, 1)[0]
        screenshotUrl = f'{metconst_url_files}/metconst-hacks/{hackId}/{screenshotUrl}'
        embed.set_image(url = screenshotUrl)
        
    if author:
        embed.set_author(name = author, url = metconst_forum_profile_url(authorId))

    await bot.say(embed = embed)

@bot.command(r'/stadium|/reroll')
async def stadium(context):
    'Picks three random Kanto pokemon and three random Johto pokemon'

    await bot.say('\n'.join(f'{x}: {pokemon[x - 1]}' for x in sorted(random.sample(range(1, 149), 3) + random.sample(range(152, 248), 3))))

@bot.command(r'/aram2pc')
async def aram2pc(context, *, address : str):
    'Calculates the file offset of an ARAM address'

    translations = [
        (0x1500, 0x56E2, 0x278104 + 4), # Main SPC engine
        (0x5820, 0x5828, 0x27C2EA + 4), # Trackers
        (0x6C00, 0x6C90, 0x278000 + 4), # ADSR settings
        (0x6D00, 0x6D60, 0x27CF81 + 4), # Sample table
        (0x6E00, 0xB516, 0x27D025 + 4)  # Sample data
    ]

    address = int(''.join(c for c in address if c in string.hexdigits), 16)
    if address < 0x1500:
        await bot.say(f'${address:04X} is in SPC general purpose RAM, not loaded from ROM')
        return

    if address >= 0x10000:
        await bot.say(f'${address:X} is outside the ARAM address space')
        return

    for (begin_aram, end_aram, begin_pc) in translations:
        if begin_aram <= address < end_aram:
            await bot.say(f'${address - begin_aram + begin_pc:06X}')
            return
    else:
        await bot.say(f'${address:04X} is song-specific data, no unique ROM address')

@bot.command(r'/gb2pc')
async def gb2pc(context, *, address : str):
    'Calculates the file offset of a game boy address'

    address = int(''.join(c for c in address if c in string.hexdigits), 16)
    await bot.say(f'${address >> 2 & ~0x3FFF | address & 0x3FFF:05X}')

@bot.command(r'/pc2gb')
async def pc2gb(context, *, address : str):
    'Calculates a game boy address from a file offset'

    address = int(''.join(c for c in address if c in string.hexdigits), 16)
    if address < 0x4000:
        await bot.say(f'${address:04X}')
    else:
        await bot.say(f'${address >> 14:X}:{address & 0x3FFF | 0x4000:04X}')

@bot.command(r'/snes2pc')
async def snes2pc(context, *, address : str):
    'Calculates the file offset of a SNES address'

    address = int(''.join(c for c in address if c in string.hexdigits), 16)
    await bot.say(f'${address >> 1 & 0x3F8000 | address & 0x7FFF:06X}')

@bot.command(r'/pc2snes')
async def pc2snes(context, *, address : str):
    'Calculates a SNES address from a file offset'

    address = int(''.join(c for c in address if c in string.hexdigits), 16)
    await bot.say(f'${address >> 15 | 0x80:02X}:{address & 0xFFFF | 0x8000:04X}')

@bot.command(r'/sm_?w?ram')
async def smRam(context, *, address : str):
    'Looks up RAM address in Super Metroid RAM map'

    address = int(''.join(c for c in address if c in string.hexdigits), 16) | 0x7E0000
    await bot.say(ramMap[ramMapKeys[bisect.bisect(ramMapKeys, address) - 1]])

@bot.command(r'/yt')
async def yt(context, *, query : str):
    'Returns the first result for a youtube search'

    youtube_url_results = 'http://www.youtube.com/results'
    youtube_url_watch = 'http://www.youtube.com/watch'

    async def yt_search(query):
        async with aiohttp.get(youtube_url_results, params = {'q': query}) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            source = await r.text()
            return re.findall(r'href="\/watch\?v=(.{11})', source)

    def yt_watch_url(videoId):
        queryString = urllib.parse.urlencode({'v': videoId})
        return f'{youtube_url_watch}?{queryString}'

    results = await yt_search(query)
    if len(results) == 0:
        await bot.say('No results')
        return

    firstResult = results[0]

    await bot.say(f'{yt_watch_url(firstResult)}')

@bot.command(r'/clear_cache')
async def clear_cache(context):
    "Clear's karen's cache"

    karen_url_clear_cache = f'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8000/clear_cache'
    async with aiohttp.get(karen_url_clear_cache) as r:
        if r.status != 200:
            raise RuntimeError(f'{r.status} - {r.reason}')

    await bot.say(':thumbsup:')

@bot.command(r'/kav')
async def karen_video(context, *, query : str):
    'Creates hilarious spongebob clip'

    karen_url = 'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8000'
    karen_url_search = f'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8000/search'
    karen_url_video  = f'{karen_url}/video'

    async def karen_search(quote):
        async with aiohttp.get(karen_url_search, params = {'q': quote}) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            return await r.json()

    async def karen_video_url(episode, timestamp):
        async with aiohttp.get(karen_url_video, params = {'episodeName': episode, 'timestamp': timestamp}) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            return f'{karen_url}/' + urllib.parse.quote(f'{episode}.{timestamp}.webm')

    results = await karen_search(query)
    if len(results) == 0:
        await bot.say("Why don't you ask me later")
        return

    firstResult = results[0]
    episodeName = firstResult['episodeName']
    timestamp   = firstResult['time_begin']
    quote       = firstResult['text']

    logging.info(f'Episode name: {episodeName}, similarity: {firstResult["similarity"]}, timestamp range: {timestamp}..{firstResult["time_end"]}')
    logging.info(f'Text: {quote}')
    logging.info('')

    await bot.say(await karen_video_url(episodeName, timestamp))

@bot.command(r'/ka(?:ren)?')
async def karen(context, *, query : str):
    'Creates hilarious spongebob quote'

    karen_url = 'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8000'
    karen_url_search = f'http://127.0.0.1:8000/search' # <-- server side hack for efficiency
    karen_url_image  = f'{karen_url}/image'

    async def karen_search(quote):
        async with aiohttp.get(karen_url_search, params = {'q': quote}) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            return await r.json()

    def karen_image_url(episode, timestamp):
        queryString = urllib.parse.urlencode({'episodeName': episode, 'timestamp': timestamp})
        return f'{karen_url_image}?{queryString}'

    results = await karen_search(query)
    if len(results) == 0:
        await bot.say("Why don't you ask me later")
        return

    firstResult = results[0]
    episodeName = firstResult['episodeName']
    timestamp   = firstResult['time_begin']
    quote       = firstResult['text']

    logging.info(f'Episode name: {episodeName}, similarity: {firstResult["similarity"]}, timestamp range: {timestamp}..{firstResult["time_end"]}')
    logging.info(f'Text: {quote}')
    logging.info('')

    embed = discord.Embed(title = quote, colour = context.message.author.colour)
    embed.set_image(url = karen_image_url(episodeName, timestamp))

    await bot.say(embed = embed)

@bot.command(r'/add_?command')
async def addSimpleCommand(context, regex: str, message: str):
    'Add a command. Format: /add "regex" "message"'

    # Check if valid regex
    try:
        re.compile(regex, re.IGNORECASE)
    except re.error as e:
        await bot.say(f'Invalid regex "{e.pattern}": {e.msg}')
        return

    # Add to queue
    global commandRequests
    commandRequests += [SimpleCommand(context.message.server.id, regex, message)]
    await bot.say(f'Your command has been requested, you are number {len(commandRequests)} in the queue')

@bot.command(r'/approve')
async def approveSimpleCommand(context, id: int = 1):
    'Approves a command. Request queue is 1-indexed'

    # Assert privilege
    if context.message.author.id != args.config['adminId']:
        await bot.say('Denied')
        return

    # Assert valid id
    if not 1 <= id <= len(commandRequests):
        await bot.say('Invalid request id')
        return

    # Instatiate command and remove from requests queue
    command = commandRequests.pop(id - 1)
    bot.command(name = command.regex, help = command.message)(makeSayWrapper(command.message))

    # Add to simple commands JSON file
    global simpleCommands
    simpleCommands += [command]
    with open('commands.json', 'w') as f:
        json.dump(simpleCommands, f, indent = 4)

    await bot.say(f'Approved command: {command.regex}')

@bot.command(r'/deny')
async def denySimpleCommand(context, id: int = 1):
    'Denies a command. Request queue is 1-indexed'

    # Assert privilege
    if context.message.author.id != args.config['adminId']:
        await bot.say('Denied')
        return

    # Assert valid id
    if not 1 <= id <= len(commandRequests):
        await bot.say('Invalid request id')
        return

    command = commandRequests.pop(id - 1)
    await bot.say(f'Denied command: {command.regex}')

@bot.listen()
async def on_ready():
    print('Servers:')
    for server in bot.servers:
        print(f'{server} - {server.id!r}')

# Load simple commands
SimpleCommand = namedtuple('SimpleCommand', ['server', 'regex', 'message'])
simpleCommands = []
try:
    with open('commands.json') as f:
        simpleCommands = [SimpleCommand(*command) for command in json.load(f)]
except FileNotFoundError as e:
    pass

def makeSayWrapper(message):
    async def wrapper():
        await bot.say(message)

    return wrapper

for command in simpleCommands:
    bot.command(command.regex, server = command.server, help = command.message)(makeSayWrapper(command.message))

commandRequests = []

# Load RAM map
ramMap = {}

with open('RAM map.asm', 'r') as f:
    for line in f:
        if 'VRAM during main gameplay' in line:
            break

        match = re.match(r'\s*\$([0-9A-F]+)(?::([0-9A-F]+))?(:|\.\.).+', line, re.IGNORECASE)
        if not match:
            continue

        address = int(match[1], 16)
        if match[2]:
            address = address << 16 | int(match[2], 16)
        else:
            address |= 0x7E0000

        ramMap[address] = match[0]

ramMapKeys = list(ramMap.keys())

# Load miscellaneous JSON files
with open('pokemon.json', 'r') as f:
    pokemon = json.load(f)

# Start daemons
for task in daemons.tasks:
    bot.loop.create_task(task(bot))

# Main #
bot.run(args.config['token'])
