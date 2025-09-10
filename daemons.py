import discord
import aiofiles, aiohttp, bs4, feedparser, lxml.html
import asyncio, async_timeout, datetime, html, logging, random, re, time, traceback, urllib.parse


metconst_update_channel_id = 518822602060464148
magconst_update_channel_id = 962419389720821760
test_update_channel_id = 1412087177474478100
metconst_url_forum_profile = 'http://forum.metroidconstruction.com/'
sleepTime = 60

def setup_logger(name):
    handler = logging.FileHandler(f'{name}.log', 'w')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger

setup_logger('metconst_forum')
setup_logger('metconst_site_approved')
setup_logger('metconst_site_new')
setup_logger('metconst_wiki')
setup_logger('metconst_reddit')

logging.basicConfig(format = '%(asctime)s - %(message)s', datefmt = '%Y-%m-%d %H:%M:%S', level = logging.INFO)

def metconst_forum_profile_url(userId):
    queryString = urllib.parse.urlencode({'action': 'profile', 'u': userId})
    return f'{metconst_url_forum_profile}?{queryString}'

async def getFeed(who, url):
    i_attempt = 0
    while True:
        logging.getLogger(who).info(f'Attempt {i_attempt} - getFeed({url})')
        try:
            async with aiohttp.ClientSession() as session:
                logging.getLogger(who).info(f'opening client session ({url})')
                with async_timeout.timeout(sleepTime):
                    logging.getLogger(who).info(f'timeout started ({url})')
                    async with session.get(url) as response:
                        logging.getLogger(who).info(f'session gotten ({url})')
                        html = await response.text()
                        logging.getLogger(who).info(f'respone text awaited ({url})')
                        feed = feedparser.parse(html)
                        logging.getLogger(who).info(f'feed parsed ({url})')
                        if feed.entries:
                            logging.getLogger(who).info(f'feed entries found ({url})')
                            break

                        logging.getLogger(who).info(f'feed entries not found ({url})')
        except Exception as e:
            logging.getLogger(who).warning(f'RSS feed parse error for {url}')
            logging.getLogger(who).warning(traceback.format_exc())

        i_attempt += 1

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
    text = re.sub('<div.+?class="spoiler_content".*?></div>', r'', text)
    text = re.sub('<div.+?class="spoiler_content".*?>(.*?)</div>', r'||\1||', text)

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

async def processFeed(who, bot, rssUrl, entryProcessor):
    await bot.wait_until_ready()
    logging.getLogger(who).info(f'Getting feed - processFeed({who})')
    feed = await getFeed(who, rssUrl)
    logging.getLogger(who).info(f'Got feed - processFeed({who})')
    while not bot.is_closed():
        mostRecentUpdated = max(entry.updated_parsed for entry in feed.entries)
        logging.getLogger(who).info(f'mostRecentUpdated = {toDateTime(mostRecentUpdated)} - processFeed({who})')
        logging.getLogger(who).info(f'Getting feed - processFeed({who})')
        feed = await getFeed(who, rssUrl)
        logging.getLogger(who).info(f'Got feed - processFeed({who})')
        for entry in reversed(feed.entries):
            if entry.updated_parsed <= mostRecentUpdated:
                continue

            logging.getLogger(who).info(f'entry.updated_parsed = {toDateTime(entry.updated_parsed)} - processFeed({who})')
            await entryProcessor(entry)

        await asyncio.sleep(sleepTime)


async def metconst_forum(bot):
    'Does the usual forum updates'

    metconst_url_forum_rss = 'https://forum.metroidconstruction.com/index.php?action=.xml;type=rss&quotes=0'

    async def metconst_id(link):
        try:
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
        except Exception as e:
            logging.getLogger('metconst_forum').warning(f'Error getting metconst profile ID for {link}')
            logging.getLogger('metconst_forum').warning(traceback.format_exc())
            return None, None

    async def processEntry(entry):
        logging.getLogger('metconst_forum').info(f'metconst_forum - {entry.title}')
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

    await processFeed('metconst_forum', bot, metconst_url_forum_rss, processEntry)


async def metconst_site_approved(bot):
    'Does the site updates for accessible content'

    metconst_url_files = 'https://metroidconstruction.com/files'
    metconst_url_rss_approved = 'http://metroidconstruction.com/recent.php?mode=atom&days=1&filters[]=Hack+Approved&filters[]=Hack+Review&filters[]=Resource+Approved&filters[]=Resource+Review'

    async def metconst_id(hackLink, hackId):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(hackLink) as r:
                    if r.status != 200:
                        raise RuntimeError(f'{r.status} - {r.reason}')

                    source = await r.text()
                    tree = lxml.html.fromstring(source)

                    authorId = None
                    match = tree.xpath('//a[starts-with(@title, "View the profile of")]')
                    if match:
                        a_profile = match[0]
                        profileUrl = a_profile.get('href')
                        if profileUrl:
                            match = re.search(r'.+\?action=profile;u=(\d+)', profileUrl)
                            if match:
                                authorId = match[1]

                    stars_avg = None
                    stars_avg_score = None
                    span_average = tree.get_element_by_id('average_star_rating', None)
                    if span_average.text_content() != 'Pending':
                        span_averageContents = span_average[0]
                        match = re.search(r'Average Rating: (.+) chozo orbs', span_averageContents.get('title'))
                        if match:
                            stars_avg_score = match[1]

                        stars_avg = len(span_averageContents.xpath('./img[@src="/images/site/star.png"]'))

                    screenshotUrls = re.findall(fr'<img src=".+?files/(.+?/{hackId}/.+?)".*?>', source)

                    stars = None
                    stats = None
                    reviewText = None
                    div_reviews = tree.get_element_by_id('reviewsContainer', None)
                    if div_reviews:
                        reviews = div_reviews.findall('.//div[@class="ratingBox"]')
                        if reviews:
                            div_review = reviews[-1]

                            div_rating = div_review[0]
                            span_rating = div_rating.find('.//span')
                            stars = len(span_rating.xpath('./img[@src="/images/site/star.png"]'))
                            div_stats = div_rating.find('.//div[@class="ratingStats"]')
                            stats = div_stats.text_content()

                            div_reviewText = div_review[1]
                            span_reviewText = div_reviewText[1]
                            reviewText = span_reviewText.text_content()

                    return authorId, screenshotUrls, stars, stars_avg, stars_avg_score, stats, reviewText
        except Exception as e:
            logging.getLogger('metconst_site_approved').warning(f'Error getting metadata for {hackLink} - {hackId}')
            logging.getLogger('metconst_site_approved').warning(traceback.format_exc())
            return None, None, None, None, None

    async def getImage(hackLink, filepath):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(hackLink) as r:
                    if r.status != 200:
                        raise RuntimeError(f'{r.status} - {r.reason}')

                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(await r.read())
        except Exception as e:
            logging.getLogger('metconst_site_approved').warning(f'Error getting image {hackLink}')
            logging.getLogger('metconst_site_approved').warning(traceback.format_exc())
            return False

        return True

    async def processEntry(entry):
        # See entries[i].xyz https://feedparser.readthedocs.io/en/latest/reference-entry/

        logging.getLogger('metconst_site_approved').info(f'metconst_site - {entry.title}')

        isReview = False
        if re.search(f'Resource Approved', entry.title):
            embedColour = 0x00FF00
            title = 'Resource Approved'
        elif re.search(f'Resource Review', entry.title):
            embedColour = 0x008000
            title = 'Resource Review'
            isReview = True
        elif re.search(f'Hack Approved', entry.title):
            embedColour = 0x0000FF
            title = 'Hack Approved'
        elif re.search(f'Hack Review', entry.title):
            embedColour = 0x000080
            title = 'Hack Review'
            isReview = True
        else:
            embedColour = None

        embed = discord.Embed(title = entry.title, url = entry.link, timestamp = toDateTime(entry.updated_parsed), color = embedColour)
        #embed = discord.Embed(title = title, url = entry.link, timestamp = toDateTime(entry.updated_parsed), color = embedColour)

        author = ', '.join(author.name for author in entry.authors)
        #embed.set_author(name = author)

        stars = None
        stats = None
        reviewText = None
        file = None
        match = re.search(r'(?:hack|resource)\.php\?(?:hack|resource)_id=(\d+)', entry.link)
        if match:
            hackId = match[1]
            authorId, screenshotUrls, stars, stars_avg, stars_avg_score, stats, reviewText = await metconst_id(entry.link, hackId)
            if screenshotUrls:
                screenshotUrl = random.sample(screenshotUrls, 1)[0]
                i_ext = screenshotUrl.rfind('.')
                if i_ext != -1:
                    filepath = 'temp' + screenshotUrl[i_ext:]
                    screenshotUrl = f'{metconst_url_files}/{screenshotUrl}'
                    if await getImage(screenshotUrl, filepath):
                        file = discord.File(filepath, filename = filepath)
                        embed.set_image(url = f'attachment://{filepath}')

            if authorId:
                #embed.set_author(name = author, url = metconst_forum_profile_url(authorId))
                author = f'[{author}]({metconst_forum_profile_url(authorId)})'

            msg = ''
            if stars_avg is not None:
                msg += 'Average: ' + ':full_moon: ' * stars_avg + ':new_moon: ' * (5 - stars_avg) + f' ({stars_avg_score})\n'

            #msg += ': '.join(entry.title.split(': ')[1:]) # resource/hack name
            embed.add_field(name = '', value = msg, inline = False)

        if isReview:
            msg = f'**{author}**'
            if stats is not None:
                msg += f' - {stats}'
            if stars is not None:
                msg += '\n' + ':full_moon: ' * stars + ':new_moon: ' * (5 - stars)
            if reviewText is not None:
                msg += f'\n> {reviewText}'
        else:
            msg = f'**{author}**'

        embed.add_field(name = '', value = msg, inline = False)

        try:
            logging.getLogger('metconst_site_approved').info(f'Sending bot message - {embed}')
            if file is None:
                await bot.get_channel(metconst_update_channel_id).send('', embed = embed)
                await bot.get_channel(magconst_update_channel_id).send('', embed = embed)
            else:
                await bot.get_channel(metconst_update_channel_id).send('', file = file, embed = embed)
                # send apparently closes the file, so we need to reopen it
                file = discord.File(filepath, filename = filepath)
                await bot.get_channel(magconst_update_channel_id).send('', file = file, embed = embed)
        except Exception as e:
            logging.getLogger('metconst_site_approved').warning(f'Error sending bot message - {embed}')
            logging.getLogger('metconst_site_approved').warning(traceback.format_exc())

    await processFeed('metconst_site_approved', bot, metconst_url_rss_approved, processEntry)


async def metconst_site_approved_test(bot):
    'Does the site updates for accessible content'

    metconst_url_files = 'https://metroidconstruction.com/files'
    metconst_url_rss_approved = 'http://metroidconstruction.com/recent.php?mode=atom&days=1&filters[]=Hack+Approved&filters[]=Hack+Review&filters[]=Resource+Approved&filters[]=Resource+Review'

    async def metconst_id(hackLink, hackId):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(hackLink) as r:
                    if r.status != 200:
                        raise RuntimeError(f'{r.status} - {r.reason}')

                    source = await r.text()
                    tree = lxml.html.fromstring(source)

                    authorId = None
                    match = tree.xpath('//a[starts-with(@title, "View the profile of")]')
                    if match:
                        a_profile = match[0]
                        profileUrl = a_profile.get('href')
                        if profileUrl:
                            match = re.search(r'.+\?action=profile;u=(\d+)', profileUrl)
                            if match:
                                authorId = match[1]

                    stars_avg = None
                    stars_avg_score = None
                    span_average = tree.get_element_by_id('average_star_rating', None)
                    if span_average.text_content() != 'Pending':
                        span_averageContents = span_average[0]
                        match = re.search(r'Average Rating: (.+) chozo orbs', span_averageContents.get('title'))
                        if match:
                            stars_avg_score = match[1]

                        stars_avg = len(span_averageContents.xpath('./img[@src="/images/site/star.png"]'))

                    screenshotUrls = re.findall(fr'<img src=".+?files/(.+?/{hackId}/.+?)".*?>', source)

                    stars = None
                    stats = None
                    reviewText = None
                    div_reviews = tree.get_element_by_id('reviewsContainer', None)
                    reviews = div_reviews.findall('.//div[@class="ratingBox"]')
                    if reviews:
                        div_review = reviews[-1]

                        div_rating = div_review[0]
                        span_rating = div_rating.find('.//span')
                        stars = len(span_rating.xpath('./img[@src="/images/site/star.png"]'))
                        div_stats = div_rating.find('.//div[@class="ratingStats"]')
                        stats = div_stats.text_content()

                        div_reviewText = div_review[1]
                        span_reviewText = div_reviewText[1]
                        reviewText = span_reviewText.text_content()

                    return authorId, screenshotUrls, stars, stars_avg, stars_avg_score, stats, reviewText
        except Exception as e:
            logging.getLogger('metconst_site_approved').warning(f'Error getting metadata for {hackLink} - {hackId}')
            logging.getLogger('metconst_site_approved').warning(traceback.format_exc())
            return None, None, None, None, None

    async def getImage(hackLink, filepath):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(hackLink) as r:
                    if r.status != 200:
                        raise RuntimeError(f'{r.status} - {r.reason}')

                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(await r.read())
        except Exception as e:
            logging.getLogger('metconst_site_approved').warning(f'Error getting image {hackLink}')
            logging.getLogger('metconst_site_approved').warning(traceback.format_exc())
            return False

        return True

    async def processEntry(entry):
        # See entries[i].xyz https://feedparser.readthedocs.io/en/latest/reference-entry/

        logging.getLogger('metconst_site_approved').info(f'metconst_site - {entry.title}')

        isReview = False
        if re.search(f'Resource Approved', entry.title):
            embedColour = 0x00FF00
            title = 'Resource Approved'
        elif re.search(f'Resource Review', entry.title):
            embedColour = 0x008000
            title = 'Resource Review'
            isReview = True
        elif re.search(f'Hack Approved', entry.title):
            embedColour = 0x0000FF
            title = 'Hack Approved'
        elif re.search(f'Hack Review', entry.title):
            embedColour = 0x000080
            title = 'Hack Review'
            isReview = True
        else:
            embedColour = None

        #embed = discord.Embed(title = entry.title, url = entry.link, timestamp = toDateTime(entry.updated_parsed), color = embedColour)
        embed = discord.Embed(title = title, url = entry.link, timestamp = toDateTime(entry.updated_parsed), color = embedColour)

        author = ', '.join(author.name for author in entry.authors)
        #embed.set_author(name = author)

        stars = None
        stats = None
        reviewText = None
        file = None
        match = re.search(r'(?:hack|resource)\.php\?(?:hack|resource)_id=(\d+)', entry.link)
        if match:
            hackId = match[1]
            authorId, screenshotUrls, stars, stars_avg, stars_avg_score, stats, reviewText = await metconst_id(entry.link, hackId)
            if screenshotUrls:
                screenshotUrl = random.sample(screenshotUrls, 1)[0]
                i_ext = screenshotUrl.rfind('.')
                if i_ext != -1:
                    filepath = 'temp' + screenshotUrl[i_ext:]
                    screenshotUrl = f'{metconst_url_files}/{screenshotUrl}'
                    if await getImage(screenshotUrl, filepath):
                        file = discord.File(filepath, filename = filepath)
                        embed.set_image(url = f'attachment://{filepath}')

            if authorId:
                #embed.set_author(name = author, url = metconst_forum_profile_url(authorId))
                author = f'[{author}]({metconst_forum_profile_url(authorId)})'

            msg = ''
            if stars_avg is not None:
                msg += 'Average: ' + ':full_moon: ' * stars_avg + ':new_moon: ' * (5 - stars_avg) + f' ({stars_avg_score})\n'

        msg += ': '.join(entry.title.split(': ')[1:]) # resource/hack name
        embed.add_field(name = '', value = msg, inline = False)

        if isReview:
            msg = f'**{author}**'
            if stats is not None:
                msg += f' - {stats}'
            if stars is not None:
                msg += '\n' + ':full_moon: ' * stars + ':new_moon: ' * (5 - stars)
            if reviewText is not None:
                msg += f'\n> {reviewText}'
        else:
            msg = f'**{author}**'

        embed.add_field(name = '', value = msg, inline = False)

        try:
            logging.getLogger('metconst_site_approved').info(f'Sending bot message - {embed}')
            if file is None:
                await bot.get_channel(test_update_channel_id).send('', embed = embed)
            else:
                await bot.get_channel(test_update_channel_id).send('', file = file, embed = embed)
        except Exception as e:
            logging.getLogger('metconst_site_approved').warning(f'Error sending bot message - {embed}')
            logging.getLogger('metconst_site_approved').warning(traceback.format_exc())

    await processFeed('metconst_site_approved', bot, metconst_url_rss_approved, processEntry)


async def metconst_site_new(bot):
    'Does the site updates for inaccessible content'

    metconst_url_rss_new = 'http://metroidconstruction.com/recent.php?mode=atom&days=1&filters[]=New+Hack&filters[]=Hack+Updated&filters[]=New+Resource&filters[]=Resource+Updated&filters[]=Speedrun'

    async def processEntry(entry):
        logging.getLogger('metconst_site_new').info(f'metconst_site - {entry.title}')

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

    await processFeed('metconst_site_new', bot, metconst_url_rss_new, processEntry)


async def metconst_wiki(bot):
    'Does the usual wiki updates'

    metconst_url_wiki_rss = 'https://wiki.metroidconstruction.com/feed.php'

    async def processEntry(entry):
        logging.getLogger('metconst_wiki').info(f'metconst_wiki - {entry.title}')
        embed = discord.Embed(title = entry.title, url = entry.link, description = processHtml(entry.summary), timestamp = toDateTime(entry.updated_parsed))
        author = ', '.join(author.name for author in entry.authors)
        embed.set_author(name = author)
        await bot.get_channel(metconst_update_channel_id).send(embed = embed)
        await bot.get_channel(magconst_update_channel_id).send(embed = embed)

    await processFeed('metconst_wiki', bot, metconst_url_wiki_rss, processEntry)


async def metconst_reddit(bot):
    'Does the usual reddit updates'

    metconst_url_reddit_rss = 'https://reddit.com/r/metroidconstruction.rss'

    async def processEntry(entry):
        logging.getLogger('metconst_reddit').info(f'metconst_reddit - {entry.title}')

        title = entry.title
        url = entry.link
        description = remove_tags(html.unescape(entry.content[0].value))
        logging.getLogger('metconst_reddit').info(description)
        timestamp = toDateTime(entry.published_parsed)
        embed = discord.Embed(title = title, url = url, description = description, timestamp = timestamp, color = 0x600000)
        if entry.author is not None:
            logging.getLogger('metconst_reddit').info(f'{entry.author_detail!r}')
            embed.set_author(name = entry.author, url = entry.author_detail.href)

        await bot.get_channel(metconst_update_channel_id).send(embed = embed)

    await processFeed('metconst_reddit', bot, metconst_url_reddit_rss, processEntry)


tasks = [metconst_forum, metconst_site_approved, metconst_site_new, metconst_wiki, metconst_reddit,
    #metconst_site_approved_test
]
