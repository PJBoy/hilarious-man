import discord.ext.commands, discord.ext.commands.view
import copy, re

class RegexBot(discord.ext.commands.Bot):
    'Derived class of existing Bot designed to support regex commands'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
            match = re.match(command.name, invoker, re.IGNORECASE)
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
