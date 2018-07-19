import bot
import discord, discord.ext.commands
import aiohttp
import argparse, json, logging, pathlib, random, re, urllib.parse
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
bot = bot.RegexBot(command_prefix = '', help_attrs = {'name': r'/help'}, formatter = bot.HelpFormatter(), description = 'Hilarious Man, the bot for you and me')

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

@bot.command(r'/ka(?:ren)?')
async def karen(context, *, query : str):
    'Creates hilarious spongebob quote'

    karen_url = 'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8000'
    karen_url_search = f'{karen_url}/search'
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
    commandRequests += [SimpleCommand(regex, message)]
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

# Main #
bot.run(args.config['token'])
