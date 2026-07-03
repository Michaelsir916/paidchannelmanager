import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_IDS, VIEWER_IDS, SUPPORT_USERNAME
from services import storage, timeutils
from services.mdutils import escape_md


# ============================== Roles ==============================

def is_super_admin(user_id):
    return user_id in ADMIN_IDS


def is_managed_admin(user_id):
    return storage.is_managed_admin_active(user_id)


def is_full_admin(user_id):
    return is_super_admin(user_id) or is_managed_admin(user_id)


def is_viewer(user_id):
    return user_id in VIEWER_IDS


def is_authorized(user_id):
    return is_full_admin(user_id) or is_viewer(user_id)


def owner_filter_for(user_id):
    return None if is_super_admin(user_id) else user_id


# ============================== Keyboards ==============================

def group_list_keyboard(user_id):
    """Top-level screen: category folders (compact/organized) instead of a flat group list."""
    groups = storage.get_known_groups()
    is_super = is_super_admin(user_id)
    categories = storage.get_categories(user_id)

    own_groups = {cid: g for cid, g in groups.items() if g.get("owner_id") == user_id}
    other_groups = {cid: g for cid, g in groups.items() if g.get("owner_id") != user_id} if is_super else {}

    grouped, uncategorized = {}, []
    for cid, g in own_groups.items():
        cat_id = g.get("category_id")
        if cat_id and cat_id in categories:
            grouped.setdefault(cat_id, []).append((cid, g))
        else:
            uncategorized.append((cid, g))

    keyboard = []
    for cat_id, name in categories.items():
        count = len(grouped.get(cat_id, []))
        keyboard.append([InlineKeyboardButton(f"📁 {name} ({count})", callback_data=f"open_category:{cat_id}")])

    if uncategorized:
        keyboard.append([InlineKeyboardButton(f"📂 Uncategorized ({len(uncategorized)})", callback_data="open_category:none")])

    if not own_groups:
        keyboard.append([InlineKeyboardButton("⚠️ No groups found yet", callback_data="noop")])

    keyboard.append([InlineKeyboardButton("🏷️ Manage Categories", callback_data="manage_categories")])

    if is_super:
        keyboard.append([InlineKeyboardButton(f"🌐 Other Admins' Groups ({len(other_groups)})", callback_data="open_category:others")])
        count = len(storage.get_managed_admins())
        keyboard.append([InlineKeyboardButton(f"👥 Users ({count})", callback_data="manage_users_menu")])

    keyboard.append([InlineKeyboardButton("🔄 Refresh list", callback_data="refresh_groups")])
    keyboard.append([InlineKeyboardButton("🆘 Support", callback_data="show_support")])
    return InlineKeyboardMarkup(keyboard)


def category_groups_keyboard(user_id, bucket):
    """bucket: a category_id, 'none' (uncategorized), or 'others' (super-admin only)."""
    groups = storage.get_known_groups()
    is_super = is_super_admin(user_id)
    keyboard = []

    for chat_id, info in groups.items():
        owner = info.get("owner_id")
        cat = info.get("category_id")

        if bucket == "others":
            if not is_super or owner == user_id:
                continue
        else:
            if owner != user_id:
                continue
            if bucket == "none" and cat:
                continue
            if bucket not in ("none",) and cat != bucket:
                continue

        title = info.get("title") or chat_id
        keyboard.append([InlineKeyboardButton(title, callback_data=f"select_group:{chat_id}")])

    if not keyboard:
        keyboard.append([InlineKeyboardButton("⚠️ No groups here", callback_data="noop")])

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="refresh_groups")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cancel_state")])
    return InlineKeyboardMarkup(keyboard)


def categories_keyboard(user_id):
    categories = storage.get_categories(user_id)
    keyboard = []
    for cat_id, name in categories.items():
        keyboard.append([InlineKeyboardButton(f"✏️ {name}", callback_data=f"cat_edit:{cat_id}")])
    keyboard.append([InlineKeyboardButton("➕ New Category", callback_data="cat_add_start")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="refresh_groups")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cancel_state")])
    return InlineKeyboardMarkup(keyboard)


def category_detail_keyboard(cat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Rename", callback_data=f"cat_rename_start:{cat_id}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"cat_delete:{cat_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="manage_categories")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cancel_state")],
    ])


def set_category_keyboard(chat_id):
    owner = storage.get_group_owner(chat_id)
    categories = storage.get_categories(owner) if owner else {}
    keyboard = []
    for cat_id, name in categories.items():
        keyboard.append([InlineKeyboardButton(f"🏷️ {name}", callback_data=f"assign_category:{chat_id}:{cat_id}")])
    keyboard.append([InlineKeyboardButton("📂 Uncategorized", callback_data=f"assign_category:{chat_id}:none")])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cancel_state")])
    return InlineKeyboardMarkup(keyboard)


def main_menu_keyboard(is_full=True, is_super=False):
    keyboard = []

    if is_full:
        keyboard.append([
            InlineKeyboardButton("➕ Add Members", callback_data="add_members_start"),
            InlineKeyboardButton("📥 Bulk Import", callback_data="bulk_import_start"),
        ])
        keyboard.append([
            InlineKeyboardButton("➖ Remove a Member", callback_data="remove_member_start"),
            InlineKeyboardButton("📤 Export List", callback_data="export_allowed"),
        ])
        keyboard.append([InlineKeyboardButton("🚫 Remove Unauthorized Members", callback_data="remove_unauthorized")])
        keyboard.append([InlineKeyboardButton("📝 Pending Approvals", callback_data="pending_approvals")])
        keyboard.append([InlineKeyboardButton("🏷️ Set Category", callback_data="set_category_start")])

    keyboard.append([InlineKeyboardButton("👀 Unverified Members", callback_data="unverified_members")])
    keyboard.append([InlineKeyboardButton("💤 Inactivity Report", callback_data="inactivity_report")])
    keyboard.append([InlineKeyboardButton("📊 Removal Report", callback_data="removal_report")])
    keyboard.append([InlineKeyboardButton("🔍 Search Member", callback_data="search_start")])

    if is_full:
        keyboard.append([InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")])

    keyboard.append([InlineKeyboardButton("🔄 Change Group", callback_data="change_group")])
    keyboard.append([InlineKeyboardButton("🆘 Support", callback_data="show_support")])
    return InlineKeyboardMarkup(keyboard)


def done_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Done", callback_data="add_done")],
        [InlineKeyboardButton("⬅️ Back", callback_data="cancel_state")],
    ])


def back_only_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="cancel_state")]])


def settings_keyboard(chat_id):
    s = storage.get_group_settings(chat_id)

    def onoff(v):
        return "✅ ON" if v else "⬜ OFF"

    auto_kick_labels = {
        "off": "OFF (manual only)",
        "instant": "INSTANT",
        "grace": f"GRACE ({s['grace_minutes']}m)",
    }

    keyboard = [
        [InlineKeyboardButton(f"🚨 Auto-kick: {auto_kick_labels[s['auto_kick']]}", callback_data="settings_cycle_autokick")],
        [InlineKeyboardButton(f"👋 Welcome message: {onoff(s['welcome_message'])}", callback_data="settings_toggle_welcome")],
        [InlineKeyboardButton(f"🚶 Leave notification: {onoff(s['leave_notification'])}", callback_data="settings_toggle_leave")],
        [InlineKeyboardButton(f"🧹 Daily auto-cleanup: {onoff(s['auto_cleanup'])}", callback_data="settings_toggle_cleanup")],
        [InlineKeyboardButton(f"📆 Daily summary: {onoff(s['daily_summary'])}", callback_data="settings_toggle_summary")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def manage_users_keyboard():
    admins = storage.get_managed_admins()
    keyboard = []
    for uid, info in admins.items():
        active = storage.is_managed_admin_active(int(uid))
        dot = "🟢" if active else "🔴"
        uname = info.get("username")
        label = f"{dot} @{uname}" if uname else f"{dot} {uid}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"user_info:{uid}")])

    keyboard.append([InlineKeyboardButton("➕ Add User", callback_data="add_user_start")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="cancel_state")])
    return InlineKeyboardMarkup(keyboard)


def user_detail_keyboard(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Remove Access", callback_data=f"remove_user:{uid}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="manage_users_menu")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cancel_state")],
    ])


# ============================== Command handlers ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_authorized(user.id):
        info = storage.get_managed_admin_info(user.id)
        if info:
            await update.message.reply_text(
                f"⌛ Oops! Your access to this bot has expired.\n"
                f"📩 Contact the main admin to renew it, or reach out to support: {SUPPORT_USERNAME} 🆘"
            )
        else:
            await update.message.reply_text(
                f"🚫 Sorry, this bot can only be used by authorized admins.\n"
                f"🆘 Need access? Contact: {SUPPORT_USERNAME}"
            )
        return

    if is_managed_admin(user.id):
        storage.set_managed_admin_username(user.id, user.username)

    context.user_data["state"] = None
    context.user_data["selected_group"] = None

    extra = ""
    if not is_super_admin(user.id) and is_managed_admin(user.id):
        info = storage.get_managed_admin_info(user.id)
        expires = timeutils.to_ist_dual(info.get("expires_at")) if info.get("expires_at") else "♾️ Permanent (no expiry)"
        started = timeutils.to_ist_dual(info.get("started_at"))
        extra = f"\n\n🔑 *Your access*\n🟢 Started: {started}\n⏳ Expires: {expires}"

    await update.message.reply_text(
        "👋 *Welcome to the Group Guardian Bot!* 🛡️\n\n"
        "📂 Select a group to manage (only groups YOU added the bot to are shown):\n\n"
        "ℹ️ If a group isn't listed, go into that group's chat and send "
        "/registergroup once (as an authorized admin) to claim it ✅, then come back "
        "here and press 🔄 Refresh." + extra +
        f"\n\n🆘 Need help? Contact support: `{SUPPORT_USERNAME}`",
        parse_mode="Markdown",
        reply_markup=group_list_keyboard(user.id)
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Your Telegram User ID:\n`{user.id}`",
        parse_mode="Markdown"
    )


async def register_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup", "channel"):
        return

    if not is_full_admin(user.id):
        return

    storage.add_known_group(chat.id, chat.title, owner_id=user.id)

    await update.message.reply_text(
        "✅ This group has been registered under your account.\n"
        "Go to the bot's private chat and send /start to manage it."
    )


def _extract_id(text):
    match = re.search(r"-?\d{4,}", text or "")
    return int(match.group()) if match else None


def _extract_number(text):
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else None


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_authorized(user.id):
        return

    if update.effective_chat.type != "private":
        return

    state = context.user_data.get("state")
    text = update.message.text or ""
    is_super = is_super_admin(user.id)
    is_full = is_full_admin(user.id)

    # ---------- Manage Users flow (super admin only) ----------
    if state == "adding_user_id":
        if not is_super:
            context.user_data["state"] = None
            return
        new_uid = _extract_id(text)
        if new_uid is None:
            await update.message.reply_text(
                "⚠️ Send a valid numeric User ID, or press Back.",
                reply_markup=back_only_keyboard()
            )
            return
        context.user_data["new_user_id"] = new_uid
        context.user_data["state"] = "adding_user_days"
        await update.message.reply_text(
            f"How many days should User `{new_uid}` have access for?\n"
            "Send a number (e.g. `30`), or send `0` for permanent access.",
            parse_mode="Markdown",
            reply_markup=back_only_keyboard()
        )
        return

    if state == "adding_user_days":
        if not is_super:
            context.user_data["state"] = None
            return
        days = _extract_number(text)
        if days is None:
            await update.message.reply_text(
                "⚠️ Send a valid number of days (0 for permanent), or press Back.",
                reply_markup=back_only_keyboard()
            )
            return

        new_uid = context.user_data.get("new_user_id")
        storage.add_managed_admin(new_uid, added_by=user.id, days=days if days > 0 else None)
        context.user_data["state"] = None
        context.user_data.pop("new_user_id", None)

        expiry_text = "Permanent (no expiry)" if days == 0 else f"{days} day(s)"
        await update.message.reply_text(
            f"✅ User `{new_uid}` granted access.\nDuration: {expiry_text}",
            parse_mode="Markdown",
            reply_markup=manage_users_keyboard()
        )
        return

    # ---------- Category management flow ----------
    if state == "adding_category":
        name = text.strip()
        if not name:
            await update.message.reply_text("⚠️ Send a valid category name.", reply_markup=back_only_keyboard())
            return
        storage.add_category(user.id, name)
        context.user_data["state"] = None
        await update.message.reply_text(
            f"✅ Category *{escape_md(name)}* created.",
            parse_mode="Markdown",
            reply_markup=categories_keyboard(user.id)
        )
        return

    if state == "renaming_category":
        name = text.strip()
        cat_id = context.user_data.get("editing_category_id")
        if not name or not cat_id:
            await update.message.reply_text("⚠️ Send a valid category name.", reply_markup=back_only_keyboard())
            return
        storage.rename_category(user.id, cat_id, name)
        context.user_data["state"] = None
        context.user_data.pop("editing_category_id", None)
        await update.message.reply_text(
            f"✅ Category renamed to *{escape_md(name)}*.",
            parse_mode="Markdown",
            reply_markup=categories_keyboard(user.id)
        )
        return

    # ---------- Search flow (searches only the user's own groups, unless super admin) ----------
    if state == "searching":
        context.user_data["state"] = None
        query_text = text.strip()
        results = storage.search_member(query_text, owner_filter_for(user.id))

        if not results:
            await update.message.reply_text(
                "No matches found in your groups.",
                reply_markup=main_menu_keyboard(is_full, is_super)
            )
            return

        blocks = [f"🔍 Found in {len(results)} group(s):\n\n"]
        for i, r in enumerate(results, 1):
            status = "✅ Allowed" if r["allowed"] else "❌ Not allowed"
            uname = f"@{escape_md(r['username'])}" if r['username'] else "No username"
            join_display = timeutils.to_ist_dual(r["join_time"]) if r["join_time"] else "Not tracked"
            blocks.append(
                f"{i}. *{escape_md(r['group_title'])}*\n"
                f"   {uname} — `{r['user_id']}`\n"
                f"   Status: {status}\n"
                f"   Joined: {join_display}\n\n"
            )

        await update.message.reply_text(
            "".join(blocks),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_full, is_super)
        )
        return

    group_id = context.user_data.get("selected_group")
    if not group_id:
        await update.message.reply_text(
            "Please select a group first.",
            reply_markup=group_list_keyboard(user.id)
        )
        return

    # ---------- Add Members flow ----------
    if state == "adding":
        if not is_full:
            return
        new_id = _extract_id(text)
        if new_id is None:
            await update.message.reply_text(
                "⚠️ Couldn't find a valid User ID. Please try again, or press Back.",
                reply_markup=done_keyboard()
            )
            return

        storage.add_allowed_ids(group_id, [new_id])
        context.user_data["added_count"] = context.user_data.get("added_count", 0) + 1
        count = context.user_data["added_count"]

        await update.message.reply_text(
            f"✅ ID `{new_id}` saved. (Added so far this session: {count})\n\n"
            "Send another ID if you have more, or press Done below:",
            parse_mode="Markdown",
            reply_markup=done_keyboard()
        )
        return

    # ---------- Remove single member flow ----------
    if state == "removing":
        if not is_full:
            return
        rem_id = _extract_id(text)
        if rem_id is None:
            await update.message.reply_text("⚠️ Please send a valid User ID.", reply_markup=back_only_keyboard())
            return

        removed = storage.remove_allowed_id(group_id, rem_id)
        context.user_data["state"] = None

        if removed:
            await update.message.reply_text(
                f"✅ ID `{rem_id}` removed from the allowed list.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(is_full, is_super)
            )
        else:
            await update.message.reply_text(
                f"ℹ️ ID `{rem_id}` was not found in the allowed list.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(is_full, is_super)
            )
        return

    # ---------- Waiting for a bulk import file, but got text instead ----------
    if state == "bulk_import":
        await update.message.reply_text(
            "📥 Please upload a .txt file containing the User IDs.",
            reply_markup=back_only_keyboard()
        )
        return

    # ---------- No active flow ----------
    await update.message.reply_text(
        "Please use the buttons below:",
        reply_markup=main_menu_keyboard(is_full, is_super)
    )
