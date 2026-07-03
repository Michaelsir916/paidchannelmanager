import re
from telegram import Update
from telegram.ext import ContextTypes

from services import storage
from handlers.commands import is_full_admin, is_super_admin, main_menu_keyboard


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

    ids = list(set(int(x) for x in re.findall(r"-?\d{4,}", text)))
    context.user_data["state"] = None

    is_super = is_super_admin(user.id)

    if not ids:
        await update.message.reply_text(
            "⚠️ No valid User IDs found in that file.",
            reply_markup=main_menu_keyboard(True, is_super)
        )
        return

    storage.add_allowed_ids(group_id, ids)

    await update.message.reply_text(
        f"✅ Imported {len(ids)} unique ID(s) from the file.",
        reply_markup=main_menu_keyboard(True, is_super)
    )
