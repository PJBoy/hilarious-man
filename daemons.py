import discord
import aiohttp, bs4, feedparser
import asyncio, async_timeout, datetime, html, logging, random, re, time, traceback, urllib.parse


metconst_update_channel_id = 518822602060464148
magconst_update_channel_id = 962419389720821760
metconst_url_forum_profile = 'http://forum.metroidconstruction.com/'
sleepTime = 10

def metconst_forum_profile_url(userId):
    queryString = urllib.parse.urlencode({'action': 'profile', 'u': userId})
    return f'{metconst_url_forum_profile}?{queryString}'

async def getFeed(url):
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                with async_timeout.timeout(sleepTime):
                    async with session.get(url) as response:
                        html = await response.text()
                        feed = feedparser.parse(html)
                        if feed.entries:
                            break
        except Exception as e:
            logging.warning(f'{datetime.datetime.now()}:')
            logging.warning(f'RSS feed parse error for {url}:')
            logging.warning(traceback.format_exc())
        
        await asyncio.sleep(sleepTime)

    return feed

def toDateTime(structTime):
    return datetime.datetime.fromtimestamp(time.mktime(structTime))

def remove_tags(text):
    return bs4.BeautifulSoup(text, features = 'html.parser').get_text()

def processHtml(text):
    # print('Before:')
    # print(text)
    # print()
    
    # Hide spoilers
    text = re.sub('<div.+?class="spoilerbody".*?></div>', r'', text)
    text = re.sub('<div.+?class="spoilerbody".*?>(.*?)</div>', r'||\1||', text)
    text = re.sub('<input.+?class="spoilerbutton".+?value="(.*?)".*?>(.*?)/>', r'\1 ', text)
    
    # Erase quotes
    # text = re.sub('<div.+?class="topslice_quote".*?>.*?</div>', r'', text)
    # text = re.sub('<div.+?class="quoteheader".*?>.*?</div>', r'', text)
    # text = re.sub('<blockquote.+?class="bbc_standard_quote".*?>.*?</blockquote>', r'', text)
    # text = re.sub('<div.+?class="botslice_quote".*?>.*?</div>', r'', text)
    # text = re.sub('<div.+?class="quotefooter".*?>.*?</div>', r'', text)
    
    text = text.replace(r'\n', '\n')
    text = text.replace('<br />', '\n')
    text = text.replace('</div>', '\n')
    text = re.sub('<.+?>', '', text)
    
    # print('After:')
    # print(html.unescape(text))
    # print()
    return html.unescape(text).replace('#039', '').replace('nbsp', '').replace('"quot', '"')

async def processFeed(bot, rssUrl, entryProcessor):
    await bot.wait_until_ready()
    feed = await getFeed(rssUrl)
    while not bot.is_closed():
        mostRecentUpdated = max(entry.updated_parsed for entry in feed.entries)
        feed = await getFeed(rssUrl)
        for entry in reversed(feed.entries):
            if entry.updated_parsed <= mostRecentUpdated:
                continue

            await entryProcessor(entry)

        await asyncio.sleep(sleepTime)


async def metconst_forum(bot):
    'Does the usual forum updates'

    metconst_url_forum_rss = 'https://forum.metroidconstruction.com/index.php?action=.xml;type=rss&quotes=0'

    async def metconst_id(link):
        async with aiohttp.ClientSession() as session:
            async with session.get(link) as r:
                if r.status != 200:
                    raise RuntimeError(f'{r.status} - {r.reason}')

                source = await r.text()
                match = re.search(r'.*#msg(\d+)', link)
                authorId, author = None, None
                if match:
                    messageId = match[1]
                    match = re.search(f'id="msg{messageId}".+?<a href=".+?u=(\\d+)".+?>(.+?)</a>', source, flags = re.DOTALL)
                    if match:
                        authorId, author = match[1], match[2]

                return authorId, author

    async def processEntry(entry):
        logging.info(f'metconst_forum - {entry.title}')
        title = f'{entry.category} — {entry.title}'
        authorId, author = await metconst_id(entry.link)

        embed = discord.Embed(title = title, url = entry.link, description = processHtml(entry.summary), timestamp = toDateTime(entry.published_parsed))
        if author is not None:
            if authorId is not None:
                embed.set_author(name = author, url = metconst_forum_profile_url(authorId))
            else:
                embed.set_author(name = author)

        await bot.get_channel(metconst_update_channel_id).send(embed = embed)
        await bot.get_channel(magconst_update_channel_id).send(embed = embed)

    await processFeed(bot, metconst_url_forum_rss, processEntry)


async def metconst_site_approved(bot):
    'Does the site updates for inaccessible content'

    metconst_url_files = 'http://pjboy.cc:8001'
    metconst_url_rss_approved = 'http://metroidconstruction.com/recent.php?mode=atom&days=1&filters[]=Hack+Approved&filters[]=Hack+Review&filters[]=Resource+Approved&filters[]=Resource+Review'

    async def metconst_id(hackLink, hackId):
        async with aiohttp.ClientSession() as session:
            async with session.get(hackLink) as r:
                if r.status != 200:
                    raise RuntimeError(f'{r.status} - {r.reason}')

                source = await r.text()
                match = re.search(r'<b>Author:</b>\s*<a href=".+?action=profile;u=(\d+)">', source)
                authorId = match[1] if match else None
                
                match = re.search(r'Pending</acronym>', source)
                if match:
                    stars_avg_score = None
                    stars_avg = None
                else:
                    match = re.search(r'Average rating: (.+) chozo orbs', source)
                    stars_avg_score = match[1] if match else None
                
                screenshotUrls = re.findall(fr'<img src=".+?files/(.+?/{hackId}/.+?)".*?>', source)
                
                matches = re.findall(r'(no_)?star\.png', source)
                if not matches:
                    stars = None
                    stars_avg = None
                else:
                    stars = 0
                    for i in range(5):
                        if matches[-1 - i] != "no_":
                            stars += 1
                            
                    if stars_avg_score != None:
                        stars_avg = 0
                        for i in range(5):
                            if matches[i] != "no_":
                                stars_avg += 1
                    else:
                        stars_avg = None
                
                return authorId, screenshotUrls, stars, stars_avg, stars_avg_score

    async def processEntry(entry):
        logging.info(f'metconst_site - {entry.title}')
        
        if re.search(f'Resource Approved', entry.title):
            embedColour = 0x00FF00
        elif re.search(f'Resource Review', entry.title):
            embedColour = 0x008000
        elif re.search(f'Hack Approved', entry.title):
            embedColour = 0x0000FF
        elif re.search(f'Hack Review', entry.title):
            embedColour = 0x000080
        else:
            embedColour = None
        
        embed = discord.Embed(title = entry.title, url = entry.link, timestamp = toDateTime(entry.updated_parsed), color = embedColour)
        
        author = ', '.join(author.name for author in entry.authors)
        embed.set_author(name = author)
            
        match = re.search(r'(?:hack|resource)\.php\?(?:hack|resource)_id=(\d+)', entry.link)
        stars = None
        if match:
            hackId = match[1]
            authorId, screenshotUrls, stars, stars_avg, stars_avg_score = await metconst_id(entry.link, hackId)
            if screenshotUrls:
                screenshotUrl = random.sample(screenshotUrls, 1)[0]
                screenshotUrl = f'{metconst_url_files}/metconst-{screenshotUrl}'
                embed.set_image(url = screenshotUrl)

            if authorId:
                embed.set_author(name = author, url = metconst_forum_profile_url(authorId))

        msg = ''
        if stars is not None:
            msg += 'Latest: ' + ':full_moon: ' * stars + ':new_moon: ' * (5 - stars)
        if stars_avg is not None:
            msg += '\nAverage: ' + ':full_moon: ' * stars_avg + ':new_moon: ' * (5 - stars_avg) + f' ({stars_avg_score})'
            
        await bot.get_channel(metconst_update_channel_id).send(msg, embed = embed)
        await bot.get_channel(magconst_update_channel_id).send(msg, embed = embed)

    await processFeed(bot, metconst_url_rss_approved, processEntry)


async def metconst_site_new(bot):
    'Does the site updates for inaccessible content'

    metconst_url_rss_new = 'http://metroidconstruction.com/recent.php?mode=atom&days=1&filters[]=New+Hack&filters[]=Hack+Updated&filters[]=New+Resource&filters[]=Resource+Updated&filters[]=Speedrun'

    async def processEntry(entry):
        logging.info(f'metconst_site - {entry.title}')
        
        if re.search(f'Resource Updated', entry.title):
            embedColour = 0x004000
        elif re.search(f'New Resource', entry.title):
            embedColour = 0x004000
        elif re.search(f'Hack Updated', entry.title):
            embedColour = 0x000040
        elif re.search(f'New Hack', entry.title):
            embedColour = 0x000040
        else:
            embedColour = None
        
        embed = discord.Embed(title = entry.title, url = entry.link, timestamp = toDateTime(entry.updated_parsed), color = embedColour)
        author = ', '.join(author.name for author in entry.authors)
        embed.set_author(name = author)
        msg = ''
        
        await bot.get_channel(metconst_update_channel_id).send(msg, embed = embed)
        await bot.get_channel(magconst_update_channel_id).send(msg, embed = embed)

    await processFeed(bot, metconst_url_rss_new, processEntry)


async def metconst_wiki(bot):
    'Does the usual wiki updates'

    metconst_url_wiki_rss = 'https://wiki.metroidconstruction.com/feed.php'

    async def processEntry(entry):
        logging.info(f'metconst_wiki - {entry.title}')
        embed = discord.Embed(title = entry.title, url = entry.link, description = processHtml(entry.summary), timestamp = toDateTime(entry.updated_parsed))
        author = ', '.join(author.name for author in entry.authors)
        embed.set_author(name = author)
        await bot.get_channel(metconst_update_channel_id).send(embed = embed)
        await bot.get_channel(magconst_update_channel_id).send(embed = embed)

    await processFeed(bot, metconst_url_wiki_rss, processEntry)


async def metconst_reddit(bot):
    'Does the usual reddit updates'

    metconst_url_reddit_rss = 'https://reddit.com/r/metroidconstruction.rss'

    async def processEntry(entry):
        logging.info(f'metconst_reddit - {entry.title}')

        title = entry.title
        url = entry.link
        description = remove_tags(html.unescape(entry.content[0].value))
        logging.info(description)
        timestamp = toDateTime(entry.published_parsed)
        embed = discord.Embed(title = title, url = url, description = description, timestamp = timestamp, color = 0x600000)
        if entry.author is not None:
            logging.info(f'{entry.author_detail!r}')
            embed.set_author(name = entry.author, url = entry.author_detail.href)

        await bot.get_channel(metconst_update_channel_id).send(embed = embed)

    await processFeed(bot, metconst_url_reddit_rss, processEntry)


tasks = [metconst_forum, metconst_site_approved, metconst_site_new, metconst_wiki, metconst_reddit]
