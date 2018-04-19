import discord.ext.commands, discord.ext.commands.view, discord.ext.commands.bot
import copy, re

async def help_command(ctx, *commands : str):
    'Shows this message'
    
    bot = ctx.bot
    destination = ctx.message.author if bot.pm_help else ctx.message.channel

    def repl(obj):
        return discord.ext.commands.bot._mentions_transforms.get(obj.group(0), '')

    # help by itself just lists our own commands.
    if len(commands) == 0:
        pages = bot.formatter.format_help_for(ctx, bot)
    elif len(commands) == 1:
        # try to see if it is a cog name
        name = discord.ext.commands.bot._mention_pattern.sub(repl, commands[0])
        command = None
        if name in bot.cogs:
            command = bot.cogs[name]
        else:
            for c in bot.commands.values():
                if re.match(c.name, name, re.IGNORECASE):
                    command = c
                    break

            if command is None:
                await bot.send_message(destination, bot.command_not_found.format(name))
                return

        pages = bot.formatter.format_help_for(ctx, command)
    else:
        name = discord.ext.commands.bot._mention_pattern.sub(repl, commands[0])
        for c in bot.commands.values():
            if re.match(c.name, name, re.IGNORECASE):
                command = c
                break

        if command is None:
            await bot.send_message(destination, bot.command_not_found.format(name))
            return

        for key in commands[1:]:
            try:
                key = discord.ext.commands.bot._mention_pattern.sub(repl, key)
                for c in command.commands.values():
                    if re.match(c.name, key, re.IGNORECASE):
                        command = c
                        break

                if command is None:
                    await bot.send_message(destination, bot.command_not_found.format(key))
                    return
            except AttributeError:
                await bot.send_message(destination, bot.command_has_no_subcommands.format(command, key))
                return

        pages = bot.formatter.format_help_for(ctx, command)

    if bot.pm_help is None:
        characters = sum(map(lambda l: len(l), pages))
        # modify destination based on length of pages.
        if characters > 1000:
            destination = ctx.message.author

    for page in pages:
        await bot.send_message(destination, page)

class RegexBot(discord.ext.commands.Bot):
    'Derived class of existing Bot designed to support regex commands'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        del self.commands[self.help_attrs['name']]
        self.command(**self.help_attrs)(help_command)

    async def process_commands(self, message):
        # Not sure what these assignments are for
        _internal_channel = message.channel
        _internal_author = message.author

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
                match = re.match(command.name, invoker, re.IGNORECASE)
            else:
                match = re.search(command.name, invoker, re.IGNORECASE)
            if match:
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
                    return
                except discord.ext.commands.CommandError as e:
                    ctx.command.dispatch_error(e, ctx)
                    return
