import discord
import aiohttp, feedparser
import asyncio, datetime, html, random, re, time, urllib.parse

async def metconst_forum(bot):
    'Does the usual forum updates'
    
    metconst_url_forum_rss = 'http://forum.metroidconstruction.com/index.php?action=.xml;type=rss'
    metconst_url_forum_profile = 'http://forum.metroidconstruction.com/'
    metconst_update_channel_id = '518822602060464148'
    
    def toDateTime(structTime):
        return datetime.datetime.fromtimestamp(time.mktime(structTime))
    
    def stripHtml(text):
        return html.unescape(re.sub('<[^<]+?>', '', text))
    
    async def metconst_id(link):
        async with aiohttp.get(link) as r:
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

    def metconst_forum_profile_url(userId):
        queryString = urllib.parse.urlencode({'action': 'profile', 'u': userId})
        return f'{metconst_url_forum_profile}?{queryString}'
    
    async def getFeed():
        feed = feedparser.parse(metconst_url_forum_rss)
        while not feed.entries:
            await asyncio.sleep(10)
            feed = feedparser.parse(metconst_url_forum_rss)
            
        return feed
    
    await bot.wait_until_ready()
    channel = discord.Object(id = metconst_update_channel_id)
    feed = await getFeed()
    while not bot.is_closed:
        mostRecentPublished = feed.entries[0].published_parsed
        feed = await getFeed()
        for entry in reversed(feed.entries):
            if entry.published_parsed <= mostRecentPublished:
                continue
                
            title = f'{entry.category} — {entry.title}'
            authorId, author = await metconst_id(entry.link)
            
            embed = discord.Embed(title = title, url = entry.link, description = stripHtml(entry.summary), timestamp = toDateTime(entry.published_parsed))
            if author is not None:
                if authorId is not None:
                    embed.set_author(name = author, url = metconst_forum_profile_url(authorId))
                else:
                    embed.set_author(name = author)
                    
            await bot.send_message(channel, embed = embed)
            
        await asyncio.sleep(10)

async def metconst_site(bot):
    'Does the usual site updates'
    
    metconst_url_hack = 'http://metroidconstruction.com/hack.php'
    metconst_url_files = 'http://ec2-18-218-195-111.us-east-2.compute.amazonaws.com:8001'
    metconst_url_forum_profile = 'http://forum.metroidconstruction.com/'
    metconst_url_rss = 'http://metroidconstruction.com/recent.php?mode=atom&days=1&filters[]=New+Hack&filters[]=Hack+Updated&filters[]=Hack+Approved&filters[]=Hack+Review&filters[]=New+Resource&filters[]=Resource+Updated&filters[]=Resource+Approved&filters[]=Resource+Review&filters[]=Speedrun'
    metconst_update_channel_id = '518822602060464148'

    async def metconst_id(hackLink, hackId):
        async with aiohttp.get(hackLink) as r:
            if r.status != 200:
                raise RuntimeError(f'{r.status} - {r.reason}')
            
            source = await r.text()
            match = re.search(r'<b>Author:</b>\s*<a href=".+?action=profile;u=(\d+)">', source)
            authorId = match[1] if match else None
            screenshotUrls = re.findall(fr'<img src=".+?files/hacks/{hackId}/(.+?)".*?>', source)
            return authorId, screenshotUrls

    def metconst_forum_profile_url(userId):
        queryString = urllib.parse.urlencode({'action': 'profile', 'u': userId})
        return f'{metconst_url_forum_profile}?{queryString}'
    
    async def getFeed():
        feed = feedparser.parse(metconst_url_rss)
        while not feed.entries:
            await asyncio.sleep(60)
            feed = feedparser.parse(metconst_url_rss)
            
        return feed
    
    await bot.wait_until_ready()
    channel = discord.Object(id = metconst_update_channel_id)
    feed = await getFeed()
    while not bot.is_closed:
        mostRecentUpdated = feed.entries[0].updated_parsed
        feed = await getFeed()
        for entry in reversed(feed.entries):
            if entry.updated_parsed <= mostRecentUpdated:
                continue
                
            embed = discord.Embed(title = entry.title, url = entry.link)
            author = ', '.join(author.name for author in entry.authors)
            embed.set_author(name = author)
            match = re.search(r'hack\.php\?hack_id=(\d+)', entry.link)
            if match:
                hackId = match[1]
                authorId, screenshotUrls = await metconst_id(entry.link, hackId)            
                if screenshotUrls:
                    screenshotUrl = random.sample(screenshotUrls, 1)[0]
                    screenshotUrl = f'{metconst_url_files}/metconst-hacks/{hackId}/{screenshotUrl}'
                    embed.set_image(url = screenshotUrl)
                
                if authorId:
                    embed.set_author(name = author, url = metconst_forum_profile_url(authorId))
                
            await bot.send_message(channel, embed = embed)
            
        await asyncio.sleep(60)
    

tasks = [metconst_forum, metconst_site]
