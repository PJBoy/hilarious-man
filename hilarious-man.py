import bot
import discord, discord.ext.commands
import aiohttp, argparse, json, logging, pathlib, random, urllib.parse

logging.basicConfig(level = logging.INFO)

# Set up #
def parseJsonFile(filepath):
    with argparse.FileType()(filepath) as f:
        return json.load(f)

argparser = argparse.ArgumentParser(description = 'Run Hilarious Man, the Discord bot for you and me.')
argparser.add_argument('config', type = parseJsonFile, nargs = '?', default = parseJsonFile(pathlib.PurePath(argparser.prog).with_suffix('.json')), help = 'Filepath to JSON file containing Hilarious Man configuration')
args = argparser.parse_args()

# Define bot #
bot = bot.RegexBot(command_prefix = '', description = 'Hilarious Man, the bot for you and me')

@bot.command(name = r'/ka(?:ren)?', pass_context = True)
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
        await bot.say('No results')
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

# Main #
bot.run(args.config['token'])