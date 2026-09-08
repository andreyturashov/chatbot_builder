from sqladmin import ModelView

from app.models.bot import Bot
from app.models.user import User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.is_active,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.email, User.is_active, User.created_at]
    column_details_exclude_list = [User.hashed_password]
    form_excluded_columns = [User.bots, User.created_at, User.updated_at]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True


class BotAdmin(ModelView, model=Bot):
    name = "Bot"
    name_plural = "Bots"
    icon = "fa-solid fa-robot"

    column_list = [
        Bot.id,
        Bot.name,
        Bot.status,
        Bot.user_id,
        Bot.created_at,
    ]
    column_searchable_list = [Bot.name, Bot.description]
    column_sortable_list = [Bot.name, Bot.status, Bot.created_at]
    form_excluded_columns = [Bot.created_at, Bot.updated_at]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
