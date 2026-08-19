import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
import re
import asyncio
from datetime import datetime

# ============================================
# НАСТРОЙКИ
# ============================================

import os

TOKEN = os.getenv("TOKEN")

OWNER_IDS = [1134940528081911919, 595710607039135745]

OWNER_ROLE_ID = 1536427438169391155
ROLE_TO_REMOVE = 1536097831742472192  # UNVERIFY
ROLE_TO_GIVE = 1536097780894793738    # USER
ROLE_LOCALBAN = 1536434870371360849
AUTO_ROLE_ID = 1536097831742472192
ROLE_ACCEPTED = 1536449752722444379

LOG_CHANNEL_ID = 1536435126207250572
LINEDEATH_APPLICATION_CHANNEL = 0

PARTNERS_FILE = 'partners.json'
ANTICRASH_FILE = 'anticrash.json'


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def is_owner(user_id):
    return user_id in OWNER_IDS


def has_full_access(member):
    if member.id in OWNER_IDS:
        return True
    if member.guild.get_role(OWNER_ROLE_ID) in member.roles:
        return True
    return False


def is_user_role(member):
    return member.guild.get_role(ROLE_TO_GIVE) in member.roles


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True
intents.webhooks = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)


# ============================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ДАННЫХ
# ============================================
def load_partners():
    if not os.path.exists(PARTNERS_FILE):
        save_partners([])
        return []
    try:
        with open(PARTNERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except:
        save_partners([])
        return []


def save_partners(partners):
    with open(PARTNERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(partners, f, ensure_ascii=False, indent=2)


def load_anticrash():
    if not os.path.exists(ANTICRASH_FILE):
        default = {'users': {}, 'localbans': {}}
        save_anticrash(default)
        return default
    try:
        with open(ANTICRASH_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {'users': {}, 'localbans': {}}
            return json.loads(content)
    except:
        return {'users': {}, 'localbans': {}}


def save_anticrash(data):
    with open(ANTICRASH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def has_permission(user_id, action):
    if is_owner(user_id):
        return True
    data = load_anticrash()
    user_data = data['users'].get(str(user_id))
    return user_data and user_data.get('permissions', {}).get(action, False)


def can_access_anticrash(user_id):
    if is_owner(user_id):
        return True
    data = load_anticrash()
    user_data = data['users'].get(str(user_id))
    return user_data and user_data.get('permissions', {}).get('access_anticrash', False)


def is_localbanned(user_id):
    data = load_anticrash()
    return str(user_id) in data['localbans']


async def apply_localban(member, reason):
    if ROLE_LOCALBAN == 0:
        return
    data = load_anticrash()
    user_id = str(member.id)
    if user_id in data['localbans']:
        return
    old_roles = []
    for role in member.roles:
        if role.id != member.guild.default_role.id:
            old_roles.append(role.id)
    for role in member.roles:
        if role.id != member.guild.default_role.id:
            try:
                await member.remove_roles(role, reason=reason)
            except:
                pass
    localban_role = member.guild.get_role(ROLE_LOCALBAN)
    if localban_role:
        try:
            await member.add_roles(localban_role, reason=reason)
        except:
            pass
    data['localbans'][user_id] = {'old_roles': old_roles, 'timestamp': datetime.now().isoformat(), 'reason': reason}
    save_anticrash(data)


async def remove_localban(member):
    if ROLE_LOCALBAN == 0:
        return
    data = load_anticrash()
    user_id = str(member.id)
    if user_id not in data['localbans']:
        return
    localban_role = member.guild.get_role(ROLE_LOCALBAN)
    if localban_role and localban_role in member.roles:
        try:
            await member.remove_roles(localban_role)
        except:
            pass
    for role_id in data['localbans'][user_id].get('old_roles', []):
        role = member.guild.get_role(role_id)
        if role and role not in member.roles:
            try:
                await member.add_roles(role)
            except:
                pass
    del data['localbans'][user_id]
    save_anticrash(data)


async def send_log(embed):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)


URL_PATTERN = re.compile(r'https?://\S+|www\.\S+|discord\.gg/\S+|dsc\.gg/\S+')


async def check_owner_role(guild):
    for owner_id in OWNER_IDS:
        owner = guild.get_member(owner_id)
        target_role = guild.get_role(OWNER_ROLE_ID)
        if not owner or not target_role:
            continue
        if target_role in owner.roles:
            continue
        if target_role >= guild.get_member(bot.user.id).top_role:
            continue
        try:
            await owner.add_roles(target_role)
        except:
            pass


# ============================================
# ГЛОБАЛЬНЫЙ КЛАСС КНОПКИ ЗАЯВКИ (используется и в команде, и в fix)
# ============================================

class LineDeathButtons(discord.ui.View):
    """Кнопка для подачи заявки с бессрочным таймаутом."""
    def __init__(self):
        super().__init__(timeout=None)  # бессрочная

    @discord.ui.button(label="📝 Подать заявку", style=discord.ButtonStyle.danger, emoji="🔥")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = LineDeathApplicationModal()
        await interaction.response.send_modal(modal)


class LineDeathApplicationModal(discord.ui.Modal, title="📝 ЗАЯВКА В LINEDEATH"):
    """Модальное окно заявки (все упоминания HellDeath заменены на LineDeath)."""
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.TextInput(label="📌 Твой возраст", placeholder="Напиши свой возраст", required=True,
                                           style=discord.TextStyle.short))
        self.add_item(discord.ui.TextInput(label="🛠️ Osint/Troling/Tox/Hacker/Crasher/Rat",
                                           placeholder="Что умеешь?",
                                           required=True, style=discord.TextStyle.short))
        self.add_item(
            discord.ui.TextInput(label="🎙️ Активность в войс/чат (1-10)", placeholder="Оцени от 1 до 10", required=True,
                                 style=discord.TextStyle.short))
        self.add_item(
            discord.ui.TextInput(label="❓ Почему хочешь вступить", placeholder="Расскажи о себе", required=True,
                                 style=discord.TextStyle.paragraph))
        self.add_item(discord.ui.TextInput(label="⏰ Сколько времени можешь уделять", placeholder="Часов в день/неделю",
                                           required=True, style=discord.TextStyle.short))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🔥 НОВАЯ ЗАЯВКА В LINEDEATH",
            description=f"**Заявитель:** {interaction.user.mention}\n**Ник:** {interaction.user.name}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        answers = [child.value for child in self.children if hasattr(child, 'value') and child.value]
        if len(answers) >= 5:
            embed.add_field(name="📌 Возраст", value=answers[0], inline=True)
            embed.add_field(name="🛠️ Osint/Troling/Tox/Hacker/Crasher/Rat", value=answers[1], inline=True)
            embed.add_field(name="🎙️ Активность", value=answers[2], inline=True)
            embed.add_field(name="❓ Почему хочешь вступить", value=answers[3], inline=False)
            embed.add_field(name="⏰ Время", value=answers[4], inline=True)

        channel = interaction.guild.get_channel(LINEDEATH_APPLICATION_CHANNEL)
        if channel:
            class AdminButtons(discord.ui.View):
                def __init__(self, user_id):
                    super().__init__(timeout=None)
                    self.user_id = user_id

                @discord.ui.button(label="✅ ПРИНЯТЬ", style=discord.ButtonStyle.green)
                async def accept(self, btn_i: discord.Interaction, button: discord.ui.Button):
                    if not has_full_access(btn_i.user):
                        await btn_i.response.send_message("❌ Нет прав", ephemeral=True)
                        return
                    embed.color = discord.Color.green()
                    embed.add_field(name="✅ СТАТУС", value="ПРИНЯТО", inline=False)
                    await btn_i.message.edit(embed=embed, view=None)

                    member = btn_i.guild.get_member(self.user_id)
                    role_accepted = btn_i.guild.get_role(ROLE_ACCEPTED)
                    if role_accepted and member:
                        try:
                            await member.add_roles(role_accepted, reason="Принят в LineDeath")
                        except Exception as e:
                            print(f"Ошибка выдачи роли: {e}")

                    await btn_i.response.send_message("✅ Заявка принята!", ephemeral=True)

                @discord.ui.button(label="❌ ОТКЛОНИТЬ", style=discord.ButtonStyle.red)
                async def deny(self, btn_i: discord.Interaction, button: discord.ui.Button):
                    if not has_full_access(btn_i.user):
                        await btn_i.response.send_message("❌ Нет прав", ephemeral=True)
                        return
                    embed.color = discord.Color.red()
                    embed.add_field(name="❌ СТАТУС", value="ОТКЛОНЕНО", inline=False)
                    await btn_i.message.edit(embed=embed, view=None)
                    await btn_i.response.send_message("❌ Заявка отклонена!", ephemeral=True)

            await channel.send(embed=embed, view=AdminButtons(interaction.user.id))
            await interaction.followup.send("✅ **ЗАЯВКА ОТПРАВЛЕНА!** Жди решения.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Канал для заявок не настроен! Используй `/setup-line-detch`.",
                                            ephemeral=True)


# ============================================
# СОБЫТИЯ
# ============================================
@bot.event
async def on_ready():
    print(f'\n╔════════════════════════════════════════╗')
    print(f'║     🤖 БОТ ЗАПУЩЕН 🤖                 ║')
    print(f'╠════════════════════════════════════════╣')
    print(f'║ Имя: {bot.user}')
    print(f'║ ID: {bot.user.id}')
    print(f'╚════════════════════════════════════════╝\n')

    if GUILD_ID != 0:
        try:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f'[✓] Синхронизировано команд для сервера: {len(synced)}')
            for cmd in synced:
                print(f'    → /{cmd.name}')
        except Exception as e:
            print(f'[✗] Ошибка синхронизации с сервером: {e}')
    else:
        try:
            synced_global = await bot.tree.sync()
            print(f'[✓] Глобально синхронизировано: {len(synced_global)}')
        except Exception as e:
            print(f'[✗] Ошибка глобальной синхронизации: {e}')

    load_partners()
    load_anticrash()
    print(f'[✓] Данные загружены')

    for guild in bot.guilds:
        await check_owner_role(guild)

    print(f'[✓] Логи идут в канал {LOG_CHANNEL_ID}')
    print(f'[✓] Автовыдача роли {AUTO_ROLE_ID} новым участникам')
    print(f'[✓] Команды: !roleall @роль | !unroleall @роль | !rolealluser @user @роль\n')


@bot.event
async def on_member_join(member):
    auto_role = member.guild.get_role(AUTO_ROLE_ID)
    if auto_role:
        try:
            await member.add_roles(auto_role, reason="Автовыдача роли новому участнику")
        except Exception as e:
            print(f'[-] Ошибка выдачи роли: {e}')
    embed = discord.Embed(title="🟢 Участник зашёл", color=0x00FF00, timestamp=datetime.now())
    embed.add_field(name="Участник", value=f"{member.mention} ({member.id})", inline=False)
    embed.add_field(name="Аккаунт создан", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=False)
    embed.set_footer(text=f"Всего: {member.guild.member_count}")
    await send_log(embed)


@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="🔴 Участник вышел", color=0xFF0000, timestamp=datetime.now())
    embed.add_field(name="Участник", value=f"{member.name}#{member.discriminator} ({member.id})", inline=False)
    embed.set_footer(text=f"Осталось: {member.guild.member_count}")
    await send_log(embed)


@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message)
        return
    if message.guild and URL_PATTERN.search(message.content):
        if not has_permission(message.author.id, 'send_links') and not is_localbanned(
                message.author.id) and not has_full_access(message.author):
            await apply_localban(message.author, f'Отправка ссылки: {message.content[:100]}')
            try:
                await message.delete()
            except:
                pass
            return
    await bot.process_commands(message)


# ============================================
# ОБРАБОТКА СОЗДАНИЯ ВЕБХУКОВ (локальный бан)
# ============================================
@bot.event
async def on_webhook_update(webhook):
    if webhook.user and not webhook.user.bot:
        if not has_full_access(webhook.user):
            member = webhook.guild.get_member(webhook.user.id)
            if member and not is_localbanned(member.id):
                await apply_localban(member, f"Создание/обновление вебхука: {webhook.name}")
                await send_log(discord.Embed(
                    title="🚫 ВЕБХУК ЗАБЛОКИРОВАН",
                    description=f"Пользователь {member.mention} создал/обновил вебхук и получил локальный бан.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                ))


# ============================================
# ПРЕФИКСНЫЕ КОМАНДЫ (только для владельцев)
# ============================================
@bot.command()
async def sync(ctx):
    if not has_full_access(ctx.author):
        await ctx.send('❌ Нет прав')
        return
    try:
        if GUILD_ID != 0:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
        else:
            synced = await bot.tree.sync()
        embed = discord.Embed(title="✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА",
                              description=f"**Синхронизировано команд:** {len(synced)}", color=discord.Color.green())
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f'❌ Ошибка синхронизации: {e}')


@bot.command(name='roleall')
async def roleall(ctx, role: discord.Role = None):
    if not ctx.author.guild_permissions.administrator and not has_full_access(ctx.author):
        await ctx.send('❌ Нет прав')
        return
    if role is None:
        await ctx.send('❌ Укажите роль: `!roleall @роль`')
        return
    if role >= ctx.guild.me.top_role:
        await ctx.send(f'❌ Роль {role.mention} выше роли бота.')
        return
    members_without = [m for m in ctx.guild.members if not m.bot and role not in m.roles]
    if not members_without:
        await ctx.send(f'✅ Все уже имеют роль {role.mention}')
        return
    progress = await ctx.send(f'🔄 Выдача роли {role.mention}... 0/{len(members_without)}')
    success = 0
    for i, m in enumerate(members_without, 1):
        try:
            await m.add_roles(role)
            success += 1
        except:
            pass
        if i % 10 == 0 or i == len(members_without):
            await progress.edit(content=f'🔄 Выдача роли {role.mention}... {i}/{len(members_without)}')
        await asyncio.sleep(0.5)
    await progress.edit(content=f'✅ Выдано {success} из {len(members_without)}')


@bot.command(name='unroleall')
async def unroleall(ctx, role: discord.Role = None):
    if not ctx.author.guild_permissions.administrator and not has_full_access(ctx.author):
        await ctx.send('❌ Нет прав')
        return
    if role is None:
        await ctx.send('❌ Укажите роль: `!unroleall @роль`')
        return
    if role >= ctx.guild.me.top_role:
        await ctx.send(f'❌ Роль {role.mention} выше роли бота.')
        return
    members_with = [m for m in ctx.guild.members if not m.bot and role in m.roles]
    if not members_with:
        await ctx.send(f'✅ Ни у кого нет роли {role.mention}')
        return
    progress = await ctx.send(f'🔄 Снятие роли {role.mention}... 0/{len(members_with)}')
    success = 0
    for i, m in enumerate(members_with, 1):
        try:
            await m.remove_roles(role)
            success += 1
        except:
            pass
        if i % 10 == 0 or i == len(members_with):
            await progress.edit(content=f'🔄 Снятие роли {role.mention}... {i}/{len(members_with)}')
        await asyncio.sleep(0.5)
    await progress.edit(content=f'✅ Снято {success} из {len(members_with)}')


@bot.command(name='rolealluser')
async def rolealluser(ctx, member: discord.Member, role: discord.Role):
    if not has_full_access(ctx.author):
        await ctx.send('❌ Нет прав')
        return
    if role >= ctx.guild.me.top_role:
        await ctx.send(f'❌ Роль {role.mention} выше или равна роли бота. Я не могу её выдать.')
        return
    if role in member.roles:
        await ctx.send(f'✅ У {member.mention} уже есть роль {role.mention}')
        return
    try:
        await member.add_roles(role, reason=f"Выдана {ctx.author} через !rolealluser")
        await ctx.send(f'✅ Роль {role.mention} успешно выдана {member.mention}')
    except discord.Forbidden:
        await ctx.send('❌ У меня недостаточно прав для выдачи этой роли (возможно, она выше моей).')
    except Exception as e:
        await ctx.send(f'❌ Ошибка при выдаче роли: {e}')


# ============================================
# СЛЭШ-КОМАНДЫ
# ============================================
def create_embed(title, description, image=None, footer=None):
    e = discord.Embed(title=title, description=description, color=0x8B0000, timestamp=datetime.now())
    if image and (image.startswith('http://') or image.startswith('https://')):
        try:
            e.set_image(url=image)
        except:
            pass
    e.set_footer(text=footer or datetime.now().strftime('%H:%M:%S'))
    return e


def owner_only():
    async def predicate(interaction):
        if not has_full_access(interaction.user):
            await interaction.response.send_message('❌ Нет прав', ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


# ----- mm -----
@bot.tree.command(name='mm')
@owner_only()
async def mm(interaction):
    class Modal(discord.ui.Modal, title='Отправить сообщение'):
        cid = discord.ui.TextInput(label='ID канала', style=discord.TextStyle.short, required=True)
        txt = discord.ui.TextInput(label='Текст', style=discord.TextStyle.paragraph, required=True)
        async def on_submit(self, i):
            ch = bot.get_channel(int(self.cid.value))
            if not ch:
                await i.response.send_message('❌ Канал не найден', ephemeral=True)
                return
            await ch.send(self.txt.value)
            await i.response.send_message(f'✅ Отправлено в {ch.mention}', ephemeral=True)
    await interaction.response.send_modal(Modal())


# ----- menuu -----
class MenuuView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.user = user

    @discord.ui.button(label='👤 Мой профиль', style=discord.ButtonStyle.primary)
    async def profile(self, i, b):
        if i.user.id != self.user.id:
            await i.response.send_message('❌ Не твоё меню', ephemeral=True)
            return
        m = i.guild.get_member(i.user.id)
        roles = ', '.join([r.mention for r in m.roles if r.name != '@everyone']) or 'Нет'
        embed = create_embed(f'📊 {m.display_name}',
                             f'**ID:** {m.id}\n**Дата входа:** {m.joined_at.strftime("%d.%m.%Y %H:%M")}\n**Роли:** {roles}\n**Статус:** {str(m.status).upper()}',
                             m.display_avatar.url)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='🔍 Поиск', style=discord.ButtonStyle.success)
    async def search(self, i, b):
        if i.user.id != self.user.id:
            await i.response.send_message('❌ Не твоё меню', ephemeral=True)
            return
        class SearchModal(discord.ui.Modal, title='Поиск'):
            q = discord.ui.TextInput(label='ID или ник', style=discord.TextStyle.short, required=True)
            async def on_submit(self, i):
                await i.response.defer(ephemeral=True)
                qq = self.q.value.strip()
                res = []
                if qq.isdigit() and len(qq) >= 17:
                    res.append(f"**ID:** {qq}\nhttps://discord.com/users/{qq}")
                    try:
                        u = await bot.fetch_user(int(qq))
                        res.append(f"**Имя:** {u.name}")
                    except:
                        res.append("❌ Данные не получены")
                else:
                    found = False
                    for g in bot.guilds:
                        for m in g.members:
                            if qq.lower() in m.name.lower() or qq.lower() in m.display_name.lower():
                                res.append(f"**Найден:** {m.mention} на {g.name}")
                                found = True
                                break
                        if found:
                            break
                    if not found:
                        res.append("❌ Не найден")
                embed = create_embed('Результаты поиска', '\n'.join(res))
                await i.followup.send(embed=embed, ephemeral=True)
        await i.response.send_modal(SearchModal())


@bot.tree.command(name='menuu')
@owner_only()
async def menuu(interaction):
    await interaction.response.send_message(embed=create_embed('📋 Меню', 'Выбери действие:'),
                                            view=MenuuView(interaction.user), ephemeral=True)


# ----- influence -----
@bot.tree.command(name='influence')
@owner_only()
async def influence(interaction):
    await interaction.response.send_message('ебали дружно маму LineDeath')


# ----- message -----
@bot.tree.command(name='message')
@owner_only()
async def message(interaction):
    class MsgModal(discord.ui.Modal, title='Отправить embed'):
        h = discord.ui.TextInput(label='Заголовок', style=discord.TextStyle.short, required=True)
        d = discord.ui.TextInput(label='Описание', style=discord.TextStyle.paragraph, required=True)
        img = discord.ui.TextInput(label='Ссылка на картинку', style=discord.TextStyle.short, required=False)
        async def on_submit(self, i):
            await i.response.send_message(embed=create_embed(self.h.value, self.d.value, self.img.value))
    await interaction.response.send_modal(MsgModal())


# ----- partners-message -----
@bot.tree.command(name='partners-message')
@owner_only()
async def partners_message(interaction):
    class PartnersModal(discord.ui.Modal, title='Партнёрское сообщение'):
        h = discord.ui.TextInput(label='Заголовок', style=discord.TextStyle.short, required=True)
        d = discord.ui.TextInput(label='Описание', style=discord.TextStyle.paragraph, required=True)
        img = discord.ui.TextInput(label='Ссылка на скрин', style=discord.TextStyle.short, required=False)
        async def on_submit(self, i):
            partners = load_partners()
            if not partners:
                await i.response.send_message('Нет партнёров. Добавьте через /partners-add', ephemeral=True)
                return
            embed = create_embed(self.h.value, self.d.value, self.img.value)
            options = [discord.SelectOption(label=p.get('label', 'Без имени')[:100], value=str(idx)) for idx, p in enumerate(partners)]
            select = discord.ui.Select(placeholder='Список партнёров', options=options)
            view = discord.ui.View(timeout=None)
            async def sel_cb(i):
                idx = int(select.values[0])
                data = load_partners()
                if idx < len(data):
                    await i.response.send_message(f'🔗 Ссылка: {data[idx].get("invite")}', ephemeral=True)
            select.callback = sel_cb
            view.add_item(select)
            await i.response.send_message(embed=embed, view=view)
    await interaction.response.send_modal(PartnersModal())


# ----- partners-add -----
@bot.tree.command(name='partners-add')
@owner_only()
async def partners_add(interaction):
    class AddModal(discord.ui.Modal, title='Добавить партнёра'):
        name = discord.ui.TextInput(label='Название', style=discord.TextStyle.short, required=True)
        link = discord.ui.TextInput(label='Ссылка', style=discord.TextStyle.short, required=True)
        async def on_submit(self, i):
            partners = load_partners()
            partners.append({'label': self.name.value, 'invite': self.link.value})
            save_partners(partners)
            await i.response.send_message(f'✅ Партнёр "{self.name.value}" добавлен', ephemeral=True)
    await interaction.response.send_modal(AddModal())


# ----- verify-message -----
@bot.tree.command(name='verify-message')
@owner_only()
async def verify_message(interaction):
    class VerifyModal(discord.ui.Modal, title='Настройка верификации'):
        h = discord.ui.TextInput(label='Заголовок', style=discord.TextStyle.short, required=True)
        d = discord.ui.TextInput(label='Описание', style=discord.TextStyle.paragraph, required=True)
        img = discord.ui.TextInput(label='Ссылка на скрин', style=discord.TextStyle.short, required=False)
        async def on_submit(self, i):
            embed = create_embed(self.h.value, self.d.value, self.img.value)
            await i.response.send_message(embed=embed, view=discord.ui.View())
            msg = await i.original_response()
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label='✅ Верификация', style=discord.ButtonStyle.primary,
                                            custom_id=f'perm_verify_{msg.id}'))
            await msg.edit(view=view)
    await interaction.response.send_modal(VerifyModal())


@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data.get('custom_id', '')
        if cid.startswith('perm_verify_'):
            code = random.randint(100000, 999999)
            if not hasattr(bot, 'vs'):
                bot.vs = {}
            bot.vs[interaction.user.id] = code
            class CodeModal(discord.ui.Modal, title='Введите код'):
                inp = discord.ui.TextInput(label=f'Код: {code}', style=discord.TextStyle.short, required=True)
                async def on_submit(self, i):
                    await i.response.defer(ephemeral=True)
                    if int(self.inp.value) == bot.vs.get(i.user.id):
                        m = i.guild.get_member(i.user.id)
                        r_remove = i.guild.get_role(ROLE_TO_REMOVE)
                        r_give = i.guild.get_role(ROLE_TO_GIVE)
                        if r_remove:
                            await m.remove_roles(r_remove)
                        if r_give:
                            await m.add_roles(r_give)
                        await i.followup.send('✅ Верификация пройдена', ephemeral=True)
                        del bot.vs[i.user.id]
                    else:
                        await i.followup.send('❌ Неверный код', ephemeral=True)
            await interaction.response.send_modal(CodeModal())


# ----- fix_messages (усиленный фикс кнопок заявок) -----
async def rebuild_partners(msg):
    partners = load_partners()
    if not partners:
        return False
    options = [discord.SelectOption(label=p.get('label', 'Без имени')[:100], value=str(idx)) for idx, p in enumerate(partners)]
    select = discord.ui.Select(placeholder='Список партнёров', options=options)
    view = discord.ui.View(timeout=None)
    async def sel_cb(i):
        idx = int(select.values[0])
        data = load_partners()
        if idx < len(data):
            await i.response.send_message(f'🔗 Ссылка: {data[idx].get("invite")}', ephemeral=True)
    select.callback = sel_cb
    view.add_item(select)
    await msg.edit(view=view)
    return True


@bot.tree.command(name='fix_messages')
@owner_only()
async def fix_messages(interaction):
    await interaction.response.defer(ephemeral=True)
    v = p = l = 0

    for ch in interaction.guild.text_channels:
        try:
            async for msg in ch.history(limit=50):
                if msg.author.id != bot.user.id:
                    continue

                # Восстановление верификации
                if msg.components:
                    for comp in msg.components:
                        for item in comp.children:
                            if hasattr(item, 'custom_id') and item.custom_id and 'perm_verify' in item.custom_id:
                                view = discord.ui.View(timeout=None)
                                view.add_item(discord.ui.Button(label='✅ Верификация', style=discord.ButtonStyle.primary,
                                                                custom_id=f'perm_verify_{msg.id}'))
                                await msg.edit(view=view)
                                v += 1
                            elif hasattr(item, 'placeholder') and 'партнёр' in str(item.placeholder).lower():
                                if await rebuild_partners(msg):
                                    p += 1

                # Восстановление кнопок заявок LineDeath
                # Проверяем embed (не только заголовок, но и описание)
                if msg.embeds:
                    for embed in msg.embeds:
                        if embed.title and ("LineDeath — Вступай" in embed.title or "🔥 LineDeath" in embed.title):
                            # Убедимся, что view содержит кнопку "Подать заявку" с правильным обработчиком
                            # Просто заменяем на новый экземпляр
                            await msg.edit(view=LineDeathButtons())
                            l += 1
                            break  # выходим из цикла embed, так как сообщение уже исправлено
        except Exception as e:
            print(f'Ошибка при обработке канала {ch.name}: {e}')
            pass

    await interaction.followup.send(f'✅ Восстановлено: верификация {v}, партнёры {p}, кнопки заявок LineDeath {l}', ephemeral=True)


# ----- mkn -----
@bot.tree.command(name='mkn')
@owner_only()
async def mkn(interaction):
    await interaction.response.send_message('м.м...мамат....кунем')


# ----- anticrash (без изменений) -----
@bot.tree.command(name='anticrash')
async def anticrash(interaction):
    if not can_access_anticrash(interaction.user.id) and not has_full_access(interaction.user):
        await interaction.response.send_message('❌ Нет прав', ephemeral=True)
        return

    class AddUserModal(discord.ui.Modal, title='Добавить участника'):
        inp = discord.ui.TextInput(label='ID или @упоминание', style=discord.TextStyle.short, required=True)
        async def on_submit(self, i):
            guild = i.guild
            member = None
            val = self.inp.value.strip()
            if val.startswith('<@'):
                uid = int(val.replace('<@', '').replace('>', '').replace('!', ''))
                member = guild.get_member(uid)
            else:
                try:
                    member = guild.get_member(int(val))
                except:
                    for m in guild.members:
                        if val.lower() in m.name.lower() or val.lower() in m.display_name.lower():
                            member = m
                            break
            if not member:
                await i.response.send_message('❌ Не найден', ephemeral=True)
                return
            data = load_anticrash()
            uid = str(member.id)
            if uid not in data['users']:
                data['users'][uid] = {'permissions': {p: False for p in
                                                      ['create_roles', 'delete_roles', 'create_channels',
                                                       'delete_channels', 'add_bots', 'give_non_admin_roles',
                                                       'give_admin_roles', 'delete_bots', 'ban_members', 'kick_members',
                                                       'timeout_members', 'send_links', 'access_anticrash']}}
                save_anticrash(data)
                await i.response.send_message(f'✅ {member.mention} добавлен', ephemeral=True)
            else:
                await i.response.send_message(f'⚠️ Уже в системе', ephemeral=True)

    view = discord.ui.View(timeout=120)
    add_btn = discord.ui.Button(label='➕ Добавить участника', style=discord.ButtonStyle.success)
    async def add_cb(i):
        await i.response.send_modal(AddUserModal())
    add_btn.callback = add_cb
    view.add_item(add_btn)

    list_btn = discord.ui.Button(label='📋 Список участников', style=discord.ButtonStyle.primary)
    async def list_cb(i):
        data = load_anticrash()
        users = data.get('users', {})
        if not users:
            await i.response.send_message('Нет участников', ephemeral=True)
            return
        options = []
        for uid in users:
            m = i.guild.get_member(int(uid))
            name = m.display_name if m else f'ID: {uid}'
            options.append(discord.SelectOption(label=name[:100], value=uid))
        select = discord.ui.Select(placeholder='Выбери участника', options=options)
        view2 = discord.ui.View(timeout=60)
        async def sel_cb(interaction):
            m = interaction.guild.get_member(int(select.values[0]))
            if m:
                await show_settings(interaction, m)
            else:
                await interaction.response.send_message('Не найден', ephemeral=True)
        select.callback = sel_cb
        view2.add_item(select)
        await i.response.edit_message(view=view2)
    list_btn.callback = list_cb
    view.add_item(list_btn)

    unban_btn = discord.ui.Button(label='🔓 Вытащить из локал бана', style=discord.ButtonStyle.danger)
    async def unban_cb(i):
        data = load_anticrash()
        lbs = data.get('localbans', {})
        if not lbs:
            await i.response.send_message('Нет локалбанов', ephemeral=True)
            return
        options = []
        for uid in lbs:
            m = i.guild.get_member(int(uid))
            name = m.display_name if m else f'ID: {uid}'
            options.append(discord.SelectOption(label=name[:100], value=uid))
        select = discord.ui.Select(placeholder='Выбери', options=options)
        view2 = discord.ui.View(timeout=60)
        async def sel_cb(interaction):
            m = interaction.guild.get_member(int(select.values[0]))
            if m:
                await remove_localban(m)
                await interaction.response.send_message(f'✅ {m.display_name} вытащен', ephemeral=True)
            else:
                await interaction.response.send_message('Не найден', ephemeral=True)
        select.callback = sel_cb
        view2.add_item(select)
        await i.response.edit_message(view=view2)
    unban_btn.callback = unban_cb
    view.add_item(unban_btn)

    await interaction.response.send_message(embed=create_embed('🛡️ Антикраш', 'Управление безопасностью'), view=view)


async def show_settings(interaction, member):
    data = load_anticrash()
    uid = str(member.id)
    if uid not in data['users']:
        data['users'][uid] = {'permissions': {p: False for p in
                                              ['create_roles', 'delete_roles', 'create_channels', 'delete_channels',
                                               'add_bots', 'give_non_admin_roles', 'give_admin_roles', 'delete_bots',
                                               'ban_members', 'kick_members', 'timeout_members', 'send_links',
                                               'access_anticrash']}}
        save_anticrash(data)
    perms = data['users'][uid]['permissions']
    perms_list = [
        ('create_roles', '🎭 Создавать роли'), ('delete_roles', '🗑️ Удалять роли'),
        ('create_channels', '📁 Создавать каналы'), ('delete_channels', '🗑️ Удалять каналы'),
        ('add_bots', '🤖 Добавлять ботов'), ('give_non_admin_roles', '📝 Выдавать не админ роли'),
        ('give_admin_roles', '👑 Выдавать админ роли'), ('delete_bots', '🗑️ Удалять ботов'),
        ('ban_members', '🔨 Банить'), ('kick_members', '👢 Кикать'),
        ('timeout_members', '🔇 Мутить'), ('send_links', '🔗 Ссылки'),
        ('access_anticrash', '⚙️ Доступ к /anticrash')
    ]
    text = f'**{member.mention}**\n**Локал бан:** {"✅" if is_localbanned(member.id) else "❌"}\n\n'
    for k, n in perms_list:
        text += f'• {n}: {"✅" if perms.get(k) else "❌"}\n'
    embed = create_embed(f'Настройки {member.display_name}', text)
    view = discord.ui.View(timeout=120)
    for k, n in perms_list:
        btn = discord.ui.Button(label=f'{"✅" if perms.get(k) else "❌"} {n}', style=discord.ButtonStyle.secondary)
        async def cb(i, key=k):
            d = load_anticrash()
            u = str(member.id)
            if u not in d['users']:
                await i.response.send_message('Ошибка', ephemeral=True)
                return
            d['users'][u]['permissions'][key] = not d['users'][u]['permissions'].get(key, False)
            save_anticrash(d)
            await i.response.edit_message(embed=await rebuild_settings_embed(member, perms_list),
                                          view=await rebuild_settings_view(member, perms_list))
        btn.callback = cb
        view.add_item(btn)
    grant = discord.ui.Button(label='✅ Выдать все', style=discord.ButtonStyle.success)
    async def grant_cb(i):
        d = load_anticrash()
        u = str(member.id)
        for k, _ in perms_list:
            d['users'][u]['permissions'][k] = True
        save_anticrash(d)
        await i.response.edit_message(embed=await rebuild_settings_embed(member, perms_list),
                                      view=await rebuild_settings_view(member, perms_list))
    grant.callback = grant_cb
    view.add_item(grant)
    revoke = discord.ui.Button(label='❌ Снять все', style=discord.ButtonStyle.danger)
    async def revoke_cb(i):
        d = load_anticrash()
        u = str(member.id)
        for k, _ in perms_list:
            d['users'][u]['permissions'][k] = False
        save_anticrash(d)
        await i.response.edit_message(embed=await rebuild_settings_embed(member, perms_list),
                                      view=await rebuild_settings_view(member, perms_list))
    revoke.callback = revoke_cb
    view.add_item(revoke)
    back = discord.ui.Button(label='◀ Назад', style=discord.ButtonStyle.danger)
    async def back_cb(i):
        await i.response.edit_message(embed=create_embed('🛡️ Антикраш', 'Выбери действие:'), view=AnticrashMainView())
    back.callback = back_cb
    view.add_item(back)
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AnticrashMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label='➕ Добавить', style=discord.ButtonStyle.success)
    async def add(self, i, b):
        class AddModal(discord.ui.Modal, title='Добавить'):
            inp = discord.ui.TextInput(label='ID', style=discord.TextStyle.short, required=True)
            async def on_submit(self, i):
                try:
                    member = i.guild.get_member(int(self.inp.value))
                except:
                    member = None
                if not member:
                    await i.response.send_message('❌ Не найден', ephemeral=True)
                    return
                d = load_anticrash()
                uid = str(member.id)
                if uid not in d['users']:
                    d['users'][uid] = {'permissions': {p: False for p in
                                                       ['create_roles', 'delete_roles', 'create_channels',
                                                        'delete_channels', 'add_bots', 'give_non_admin_roles',
                                                        'give_admin_roles', 'delete_bots', 'ban_members',
                                                        'kick_members', 'timeout_members', 'send_links',
                                                        'access_anticrash']}}
                    save_anticrash(d)
                    await i.response.send_message(f'✅ {member.mention} добавлен', ephemeral=True)
                else:
                    await i.response.send_message('⚠️ Уже есть', ephemeral=True)
        await i.response.send_modal(AddModal())

    @discord.ui.button(label='📋 Список', style=discord.ButtonStyle.primary)
    async def lst(self, i, b):
        d = load_anticrash()
        users = d.get('users', {})
        if not users:
            await i.response.send_message('Нет участников', ephemeral=True)
            return
        options = []
        for uid in users:
            m = i.guild.get_member(int(uid))
            name = m.display_name if m else uid
            options.append(discord.SelectOption(label=name[:100], value=uid))
        select = discord.ui.Select(placeholder='Выбери', options=options)
        view = discord.ui.View(timeout=60)
        async def sel_cb(interaction):
            m = interaction.guild.get_member(int(select.values[0]))
            if m:
                await show_settings(interaction, m)
        select.callback = sel_cb
        view.add_item(select)
        await i.response.edit_message(view=view)


async def rebuild_settings_view(member, perms_list):
    d = load_anticrash()
    uid = str(member.id)
    perms = d['users'].get(uid, {}).get('permissions', {})
    view = discord.ui.View(timeout=120)
    for k, n in perms_list:
        btn = discord.ui.Button(label=f'{"✅" if perms.get(k) else "❌"} {n}', style=discord.ButtonStyle.secondary)
        async def cb(i, key=k):
            d2 = load_anticrash()
            u = str(member.id)
            if u not in d2['users']:
                await i.response.send_message('Ошибка', ephemeral=True)
                return
            d2['users'][u]['permissions'][key] = not d2['users'][u]['permissions'].get(key, False)
            save_anticrash(d2)
            await i.response.edit_message(embed=await rebuild_settings_embed(member, perms_list),
                                          view=await rebuild_settings_view(member, perms_list))
        btn.callback = cb
        view.add_item(btn)
    grant = discord.ui.Button(label='✅ Выдать все', style=discord.ButtonStyle.success)
    async def grant_cb(i):
        d2 = load_anticrash()
        u = str(member.id)
        for k, _ in perms_list:
            d2['users'][u]['permissions'][k] = True
        save_anticrash(d2)
        await i.response.edit_message(embed=await rebuild_settings_embed(member, perms_list),
                                      view=await rebuild_settings_view(member, perms_list))
    grant.callback = grant_cb
    view.add_item(grant)
    revoke = discord.ui.Button(label='❌ Снять все', style=discord.ButtonStyle.danger)
    async def revoke_cb(i):
        d2 = load_anticrash()
        u = str(member.id)
        for k, _ in perms_list:
            d2['users'][u]['permissions'][k] = False
        save_anticrash(d2)
        await i.response.edit_message(embed=await rebuild_settings_embed(member, perms_list),
                                      view=await rebuild_settings_view(member, perms_list))
    revoke.callback = revoke_cb
    view.add_item(revoke)
    back = discord.ui.Button(label='◀ Назад', style=discord.ButtonStyle.danger)
    async def back_cb(i):
        await i.response.edit_message(embed=create_embed('🛡️ Антикраш', 'Выбери действие:'), view=AnticrashMainView())
    back.callback = back_cb
    view.add_item(back)
    return view


async def rebuild_settings_embed(member, perms_list):
    d = load_anticrash()
    uid = str(member.id)
    perms = d['users'].get(uid, {}).get('permissions', {})
    text = f'**{member.mention}**\n**Локал бан:** {"✅" if is_localbanned(member.id) else "❌"}\n\n'
    for k, n in perms_list:
        text += f'• {n}: {"✅" if perms.get(k) else "❌"}\n'
    return create_embed(f'Настройки {member.display_name}', text)


# ============================================
# КОМАНДА LINEDEATH (использует глобальные классы)
# ============================================

@bot.tree.command(name='line-detch', description='📝 Подать заявку в клан LineDeath')
async def line_detch(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔥 LineDeath — Вступай в наши ряды!",
        description="Мы — сообщество единомышленников.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="## Требования",
        value="• Возраст 16+\n• Активность в голосовых каналах и чате\n• Интерес к Серверу",
        inline=False
    )
    embed.add_field(
        name="## Что мы предлагаем",
        value="• комфортное времяпровождение на сервере\n• Участие в совместных проектах",
        inline=False
    )
    embed.set_footer(text="Нажми на кнопку, чтобы подать заявку")
    await interaction.response.send_message(embed=embed, view=LineDeathButtons())


# ----- setup-line-detch (только для владельцев) -----
@bot.tree.command(name='setup-line-detch', description='⚙️ Настроить канал для заявок LineDeath')
@owner_only()
async def setup_line_detch(interaction: discord.Interaction):
    class SetupModal(discord.ui.Modal, title='Настройка канала для заявок LineDeath'):
        channel_id = discord.ui.TextInput(label='ID канала для заявок', placeholder='Введите ID канала', required=True)
        async def on_submit(self, i):
            global LINEDEATH_APPLICATION_CHANNEL
            try:
                LINEDEATH_APPLICATION_CHANNEL = int(self.channel_id.value)
                embed = discord.Embed(
                    title="✅ НАСТРОЙКА ЗАВЕРШЕНА",
                    description=f"**Канал для заявок LineDeath:** <#{LINEDEATH_APPLICATION_CHANNEL}>",
                    color=discord.Color.green()
                )
                await i.response.send_message(embed=embed, ephemeral=True)
            except:
                await i.response.send_message("❌ Ошибка! Введи корректный ID канала", ephemeral=True)
    await interaction.response.send_modal(SetupModal())


# ----- help (обновлён) -----
@bot.tree.command(name='help')
async def help_cmd(interaction):
    embed = create_embed('📋 КОМАНДЫ БОТА',
                         '**🔹 НАБОРЫ (ЗАЯВКИ):**\n'
                         '`/line-detch` - Подать заявку в LineDeath\n'
                         '`/setup-line-detch` - Настроить канал для заявок\n\n'
                         '**🔹 ПРЕФИКСНЫЕ КОМАНДЫ (!):**\n'
                         '`!roleall @роль` - Выдать роль всем\n'
                         '`!unroleall @роль` - Снять роль у всех\n'
                         '`!rolealluser @user @роль` - Выдать роль конкретному пользователю (только владельцам)\n'
                         '`!sync` - Синхронизация команд\n\n'
                         '**🔹 СЛЭШ-КОМАНДЫ:**\n'
                         '`/verify-message` - Создать верификацию\n'
                         '`/partners-add` - Добавить партнёра\n'
                         '`/partners-message` - Партнёрка\n'
                         '`/anticrash` - Управление антикрашем\n'
                         '`/menuu` - Меню профиля\n'
                         '`/message` - Отправить embed\n'
                         '`/mm` - Отправить сообщение\n'
                         '`/mkn` - Маматкунем\n'
                         '`/influence` - Influence\n'
                         '`/fix_messages` - Починить кнопки (верификация, партнёры, заявки LineDeath)\n'
                         '`/help` - Это меню',
                         footer='Топовый бот пахана | LineDeath')
    await interaction.response.send_message(embed=embed)


# ============================================
# ЗАПУСК БОТА
# ============================================
if __name__ == "__main__":
    bot.run(TOKEN)
