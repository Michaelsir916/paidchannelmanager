import re
from telegram import Update
from telegram.ext import ContextTypes

from services import storage
from handlers.commands import is_full_admin, is_super_admin, main_menu_keyboard, expiry_keyboard


async def handle_bulk_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_full_admin(user.id):
        return

    if update.effective_chat.type != "private":
        return

    if context.user_data.get("state") != "bulk_import":
        return

    group_id = context.user_data.get("selected_group")
    if not group_id:
        await update.message.reply_text("Please select a group first.")
        return

    doc = update.message.document
    if not doc:
        return

    tg_file = await doc.get_file()
    file_bytes = await tg_file.download_as_bytearray()
    text = file_bytes.decode("utf-8", errors="ignore")

    found_ids = list(set(int(x) for x in re.findall(r"-?\d{4,}", text)))
    context.user_data["state"] = None

    is_super = is_super_admin(user.id)

    if not found_ids:
        await update.message.reply_text(
            "⚠️ No valid User IDs found in that file.",
            reply_markup=main_menu_keyboard(True, is_super)
        )
        return

    existing = set(storage.get_allowed_ids(group_id))
    new_ids = [i for i in found_ids if i not in existing]
    skipped = len(found_ids) - len(new_ids)

    if not new_ids:
        await update.message.reply_text(
            f"ℹ️ All {len(found_ids)} ID(s) in that file are *already added* to the whitelist. Nothing new to import.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(True, is_super)
        )
        return

    context.user_data["pending_add_ids"] = new_ids
    skip_line = f"\n⚠️ Skipped {skipped} ID(s) already in the whitelist." if skipped else ""

    await update.message.reply_text(
        f"📥 Found {len(new_ids)} new ID(s) to import.{skip_line}\n\n"
        "Choose how long they should stay whitelisted:",
        parse_mode="Markdown",
        reply_markup=expiry_keyboard()
    )
