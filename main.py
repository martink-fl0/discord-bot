import discord
import random
import re
import numpy

from typing import NamedTuple
from enum import Enum
from config import TOKEN
from discord.ext import commands

def get_bot_intents() -> discord.Intents:
    intents = discord.Intents.none()
    intents.emojis_and_stickers = True
    intents.messages = True
    intents.reactions = True
    intents.message_content = True
    return intents

client = commands.Bot(
    activity=discord.Game(name="around"),
    intents=get_bot_intents(),
    command_prefix="roll ",
    help_command=None,
    description="Bot melhor que rollem"
)

FINAL_CMD_REGEX = re.compile(r"^(?:(?P<mult>\d{1,5})#)?(?P<num>\d{1,5})d(?P<size>\d{1,5})(?:\+(?P<add>\d{1,5}))?")

inits = numpy.array([(12, "Banana", 240732567744151553), (16, "Maçã", 442681532956803083)],
                dtype= [("roll", int), ("dado", (str, 50)), ("roller_id", int)])

init_msg_id = None


def merge_s_arr(array1, array2):
    n1 = len(array1)
    n2 = len(array2)
    array_out = array1.copy()
    array_out.resize(n1 + n2)
    array_out[n1:] = array2
    return array_out

class KeepAndDrop(Enum):
    KH = re.compile(r"kh(?P<num>\d{1,5})")
    KL = re.compile(r"kl(?P<num>\d{1,5})")
    DH = re.compile(r"dh(?P<num>\d{1,5})")
    DL = re.compile(r"dl(?P<num>\d{1,5})")

class Token(NamedTuple):
    type: Enum
    match: re.Match[str]

    @property
    def num(self) -> int:
        return int(self.match["num"])

@client.event
async def on_message(message: discord.Message, txt_channel: discord.abc.Messageable | None = None):
    await client.process_commands(message)

    if message.author.id == client.user.id: # type: ignore
        return
    
    if txt_channel is None:
        txt_channel = message.channel

    msg_content = message.content
    final_match = FINAL_CMD_REGEX.match(msg_content)

    if final_match is None:
        return
    
    kd_token = None

    for _rulee in KeepAndDrop:
        match = _rulee.value.search(msg_content)
        if match is not None:
            kd_token = Token(type=_rulee, match=match)
            break

    def kd_opt(x: int, idx: int, token: Token) -> tuple[bool, int]:
        if token.type == KeepAndDrop.KH:
            num = token.num
            if idx >= num:
                return True, -x
        elif token.type == KeepAndDrop.KL:
            num = token.num
            if idx <= num:
                return True, -x
        elif token.type == KeepAndDrop.DH:
            num = token.num
            if idx < num:
                return True, -x
        elif token.type == KeepAndDrop.DL:
            num = token.num
            if idx > num:
                return True, -x
        return False, 0

    def roll_dice(num: int, size: int) -> str:
        nums = [random.randint(1, size) for _ in range(num)]
        total = sum(nums)

        def format_roll(x: int, idx: int):
            nonlocal total

            if x == 1 or x == size:
                fmt = f'**{x}**'
            else:
                fmt = f"{x}"

            if kd_token is None:
                return fmt

            scratch, diff = kd_opt(x, idx, kd_token)
            if scratch:
                fmt = f"~~{fmt}~~"
            total += diff
            return fmt

        if message.reference is not None and message.reference.message_id == init_msg_id:
            return total

        srtd_nums = sorted(nums, reverse=True)
        formated_arr = [format_roll(x, i) for i, x in enumerate(srtd_nums)]

        add = int(final_match["add"]) if final_match["add"] is not None else 0

        if add == 0:
            return f"` {total} ` ⟵ [{', '.join(str(x) for x in formated_arr)}]"
        return f"` {total + add} ` ⟵ [{', '.join(str(x) for x in formated_arr)}] + {add}"

    mult = int(final_match["mult"]) if final_match["mult"] is not None else 1
    num = int(final_match["num"])
    size = int(final_match["size"])
    
    if message.reference is None:
        result = "\n".join(roll_dice(num, size) for _ in range(mult))
        await message.reply(result)
    elif message.reference.message_id != init_msg_id:
        result = "\n".join(roll_dice(num, size) for _ in range(mult))
        await message.reply(result)
    elif message.reference.message_id == init_msg_id:
        global inits

        for _ in range(mult):
            cenas = numpy.array([(roll_dice(num, size), msg_content, message.author.id)],
                    dtype= [("roll", int), ("dado", (str, 50)), ("roller_id", int)])
            inits = merge_s_arr(inits, cenas)
        srtd_inits = numpy.sort(inits, order="roll")[::-1]

        rolls = [srtd_inits[_x]["roll"] for _x in range(srtd_inits.size)]
        dado = [srtd_inits[_x]["dado"] for _x in range(srtd_inits.size)]
        roller_id = [srtd_inits[_x]["roller_id"] for _x in range(srtd_inits.size)]

        lista_ranks = [f"\t{_x}º - {(await client.fetch_user(roller_id[_x])).mention} - {rolls[_x]} ({dado[_x]})" for _x in range(1, srtd_inits.size)]
        fmt_lista = "\n".join(lista_ranks)
        fmt = f"Iniciativas:\n{fmt_lista}"

        message_to_edit = await txt_channel.fetch_message(init_msg_id)
        await message_to_edit.edit(content=fmt)

@client.command(name="initiative", aliases=("init", "iniciativa"))
async def initiative(ctx: commands.Context, close: str | None = None, txt_channel: discord.TextChannel = commands.parameter(default=lambda ctx: ctx.channel)):

    global inits, init_msg_id

    if close == "close" or close == "fechar":
        close = await txt_channel.fetch_message(init_msg_id)
        await close.edit(content=f"**FECHADO / CLOSED**\n{close.content}")
        init_msg_id = 0
        return

    inits = numpy.array([(999999999999, "", 0)],
                dtype= [("roll", int), ("dado", (str, 50)), ("roller_id", int)])

    init_msg = await ctx.reply("Iniciativas:\n\tResponde com um dado para rolar iniciativa")

    if init_msg.id != init_msg_id and init_msg_id is not None:
        close = await txt_channel.fetch_message(init_msg_id)
        await close.edit(content=f"**FECHADO / CLOSED**\n{close.content}")
    init_msg_id = init_msg.id

@client.command(name="stats")
async def stats(ctx: commands.Context):
    def forced_roll():
        nums = [random.randint(1, 6) for _ in range(4)]
        srtd_nums = sorted(nums, reverse=True)
        total = sum(srtd_nums) - srtd_nums[-1]
        for _x in range(len(srtd_nums)):
            if srtd_nums[_x] == 6 or srtd_nums[_x] == 1:
                srtd_nums[_x] = f"**{srtd_nums[_x]}**"
        srtd_nums[-1] = f"~~{srtd_nums[-1]}~~"
        rolled_stat = f"` {total} ` ⟵ [{', '.join(str(x) for x in srtd_nums)}]"
        return rolled_stat
    rolled_stats = "\n".join(forced_roll() for _ in range(6))
    await ctx.reply(rolled_stats)

@client.command(name="shortstats", aliases=("ss", "sstats"))
async def s_stats(ctx: commands.Context):
    unsrtd_nums = [random.randint(3, 18) for _ in range(6)]
    srtd_nums = sorted(unsrtd_nums, reverse=True)
    for _x in range(len(srtd_nums)):
        srtd_nums[_x] = f"` {srtd_nums[_x]} `"
    fmt_nums = "  ".join(srtd_nums)
    await ctx.reply(fmt_nums)

if __name__ == "__main__":
    client.run(TOKEN)
