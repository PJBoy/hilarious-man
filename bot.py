import discord.ext.commands, discord.ext.commands.bot, discord.ext.commands.formatter, discord.ext.commands.view
import copy, re

async def help_command(ctx, *commands : str):
    'Shows this message'

    bot = ctx.bot
    destination = ctx.message.author if bot.pm_help else ctx.message.channel

    def repl(obj):
        return discord.ext.commands.bot._mentions_transforms.get(obj.group(0), '')

    # help just lists our own commands.
    pages = bot.formatter.format_help_for(ctx, bot)

    if bot.pm_help is None:
        characters = sum(map(lambda l: len(l), pages))
        # modify destination based on length of pages.
        if characters > 1000:
            destination = ctx.message.author

    for page in pages:
        await bot.send_message(destination, page)


class RegexBot(discord.ext.commands.Bot):
    'Derived class of existing Bot designed to support regex and server specific commands'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        del self.commands[self.help_attrs['name']]
        self.command(**self.help_attrs)(help_command)

    def command(self, name, server = None, *args, **kwargs):
        kwargs['pass_context'] = True
        def decorator(f):
            def doesServerMatch(ctx):
                return server == None or server == ctx.message.server.id

            command = discord.ext.commands.Bot.command(self, name, *args, **kwargs)(f)
            self.commands[command.name].server = server
            self.commands[command.name].checks += [doesServerMatch]
            return command

        return decorator

    async def process_commands(self, message):
        _internal_channel = message.channel
        _internal_author = message.author

        message.content = message.content.replace('*', '')
        view = discord.ext.commands.view.StringView(message.content)
        if self._skip_check(message.author, self.user):
            return

        prefix = await self._get_prefix(message)
        invoked_prefix = prefix

        if not isinstance(prefix, (tuple, list)):
            if not view.skip_string(prefix):
                return
        else:
            invoked_prefix = discord.utils.find(view.skip_string, prefix)
            if invoked_prefix is None:
                return

        invoker = copy.deepcopy(view).read_rest()
        for command in self.commands.values():
            if command.name.startswith('/'):
                match = re.match(command.name + r'\b', invoker, re.IGNORECASE)
            else:
                match = re.search(command.name, invoker, re.IGNORECASE)
            if match:
                break
        else:
            return

        matched_view = copy.deepcopy(view)
        matched_view.skip_string(match[0])
        matched_view.skip_ws()
        tmp = {
            'bot': self,
            'invoked_with': invoker,
            'message': message,
            'view': matched_view,
            'prefix': invoked_prefix
        }
        ctx = discord.ext.commands.Context(**tmp)
        self.dispatch('command', command, ctx)
        try:
            await command.invoke(ctx)
            self.dispatch('command_completion', command, ctx)
        except discord.ext.commands.CommandError as e:
            ctx.command.dispatch_error(e, ctx)


class HelpFormatter(discord.ext.commands.formatter.HelpFormatter):
    'Derived class of existing HelpFormatter designed to be rid of the footer message and width restriction'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_ending_note(self):
        return ''

    def shorten(self, text):
        return text
