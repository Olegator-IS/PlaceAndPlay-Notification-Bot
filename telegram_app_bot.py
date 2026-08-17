"""
Основной класс Telegram App бота для Place&Play
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import os
import html
import time
import requests
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

from models import UserState, Sport, Place, Event
from place_and_play_api import PlaceAndPlayAPI

# Загружаем переменные окружения
load_dotenv('config.env')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Эмодзи для кнопок
def parse_connect_tokens(raw: str):
    """
    connect_62 -> (62, None)
    connect_62_13 -> (62, 13)
    """
    if not raw or not raw.startswith("connect_"):
        return None, None
    rest = raw[len("connect_"):]
    if not rest:
        return None, None
    parts = rest.split("_")
    try:
        org_id = int(parts[0])
        branch_id = int(parts[1]) if len(parts) > 1 else None
        return org_id, branch_id
    except ValueError:
        return None, None


EMOJIS = {
    'start': '🚀',
    'back': '⬅️',
    'home': '🏠',
    'register': '✅',
    'details': 'ℹ️',
    'app_store': '📱',
    'google_play': '🤖',
    'web_app': '🌐',
    'sports': '🏃',
    'places': '📍',
    'events': '📅'
}


class PlaceAndPlayAppBot:
    """Основной класс Telegram App бота для Place&Play"""
    
    def __init__(self):
        # Инициализация API
        self.api = PlaceAndPlayAPI(
            base_url=os.getenv('PLACE_AND_PLAY_API_BASE_URL'),
            email=os.getenv('PLACE_AND_PLAY_LOGIN_EMAIL'),
            password=os.getenv('PLACE_AND_PLAY_LOGIN_PASSWORD')
        )
        
        # URL веб-приложения
        self.app_url = os.getenv('TELEGRAM_APP_URL')
        
        # Хранение состояний пользователей
        self.user_states: Dict[int, UserState] = {}
        # chat_id -> {event_id, original_message_id, prompt_message_id, started_at}
        self.pending_rejects: Dict[int, dict] = {}
        
        # Инициализация бота с настройками HTTP клиента
        self.application = Application.builder().token(
            os.getenv('TELEGRAM_BOT_TOKEN')
        ).http_version("1.1").get_updates_http_version("1.1").build()
        
        # Настройка обработчиков
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        
        # Основные команды
        self.application.add_handler(CommandHandler('start', self.start_command))
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('connect', self.connect_command))
        
        # Обработка данных от веб-приложения
        self.application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_webapp_data))
        
        # Обработка callback'ов для дополнительных действий
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_reject_reason_message)
        )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        logger.info(f"Получена команда /start от пользователя {user.id} (@{user.username})")
        
        if update.effective_chat:
            self.pending_rejects.pop(update.effective_chat.id, None)

        # Проверяем, есть ли параметр для подключения организации
        if context.args and len(context.args) > 0:
            start_param = context.args[0]
            logger.info(f"Параметр start: {start_param}")
            if start_param.startswith('connect_'):
                org_id, branch_id = parse_connect_tokens(start_param)
                if org_id is not None:
                    logger.info(
                        f"Обнаружен параметр подключения org={org_id} branch={branch_id}"
                    )
                    context.args = [str(org_id)] + ([str(branch_id)] if branch_id else [])
                    await self.connect_command(update, context)
                    return
                logger.warning(f"Ошибка парсинга connect из параметра {start_param}")
        
        # Создаем главное меню только с информацией о проекте (без веб-приложения для локальной разработки)
        keyboard = [
            [InlineKeyboardButton(f"{EMOJIS['details']} О проекте", callback_data='about_project')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
    f"👋 <b>Привет, {user.first_name}!</b>\n\n"
    "🏟 <b>Добро пожаловать в Place&Play для бизнеса!</b>\n\n"
    "🔔 <b>Получайте моментальные уведомления</b> о новых бронированиях прямо в Telegram\n\n"
    "💼 <b>Управляйте вашим клубом</b> через удобный сайт sports.placeandplay.uz:\n"
    "• Просматривайте все бронирования в календаре\n"
    "• Управляйте расписанием и кортами\n"
    "• Отслеживайте аналитику и статистику\n"
    "• Общайтесь с клиентами в чате\n"
    "• Настраивайте цены и рабочие часы\n\n"
    "⚡ <b>Подключите уведомления</b> в настройках вашего клуба, чтобы не пропустить ни одного бронирования!\n\n"
    "🌐 <b>Начните работу:</b> перейдите в <a href='https://sports.placeandplay.uz'>sports.placeandplay.uz</a>"
)


        
        try:
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            logger.info(f"Приветственное сообщение отправлено пользователю {user.id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке приветственного сообщения: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке команды. Пожалуйста, попробуйте позже."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        help_text = (
    "📚 <b>Справка по командам</b>\n\n"
    "/start — Главное меню\n"
    "/help — Эта справка\n"
    "/connect — Подключить уведомления для организации\n\n"
    "🔔 <b>Уведомления о бронированиях:</b>\n"
    "Используйте команду <b>/connect</b> или перейдите по ссылке из настроек вашего клуба, "
    "чтобы подключить Telegram уведомления.\n\n"
    "После подключения вы будете получать:\n"
    "• 📅 Уведомления о новых бронированиях\n"
    "• ⏰ Информацию о времени и корте\n"
    "• 👤 Данные о клиенте (имя и телефон)\n"
    "• ✅ Кнопки «Подтвердить» / «Отклонить» для заявок на регистрацию\n"
    "• 🔗 Прямую ссылку на просмотр бронирования\n\n"
    "💼 <b>Управление клубом:</b>\n"
    "Перейдите на <a href='https://sports.placeandplay.uz'>sports.placeandplay.uz</a> для:\n"
    "• 📊 Просмотра всех бронирований в календаре\n"
    "• ⚙️ Настройки цен и рабочих часов\n"
    "• 📈 Просмотра аналитики и статистики\n"
    "• 💬 Общения с клиентами в чате\n"
    "• 👥 Управления участниками событий\n\n"
    "⚡ <b>Совет</b>: подключите уведомления, чтобы не пропустить ни одного бронирования!"
)
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /connect для подключения Telegram уведомлений"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        command_text = update.message.text or ""
        org_id = None
        branch_id = None

        if len(context.args) > 0:
            try:
                org_id = int(context.args[0])
            except ValueError:
                pass
            if len(context.args) > 1:
                try:
                    branch_id = int(context.args[1])
                except ValueError:
                    pass

        if org_id is None and 'connect_' in command_text:
            org_id, branch_id = parse_connect_tokens(
                command_text.split()[-1] if ' ' in command_text else command_text.replace('/connect', 'connect', 1)
            )

        if org_id is None:
            await update.message.reply_text(
                "❌ <b>Ошибка подключения</b>\n\n"
                "Для подключения уведомлений используйте команду из настроек вашего клуба в системе Place&Play.\n\n"
                "Если вы перешли по ссылке из настроек, но видите это сообщение, пожалуйста, обратитесь в поддержку.",
                parse_mode='HTML'
            )
            return
        
        try:
            # Отправляем chat_id на сервер для сохранения
            load_dotenv('config.env')
            # Events-Service работает на порту 8082
            events_service_url = os.getenv('PLACE_AND_PLAY_EVENTS_SERVICE_URL', 'http://localhost:8082/PlaceAndPlay')
            
            # Подготавливаем заголовки
            headers = {"Content-Type": "application/json"}
            
            # Добавляем API ключ, если он настроен
            bot_api_key = os.getenv('TELEGRAM_BOT_API_KEY')
            if bot_api_key:
                headers["X-Telegram-Bot-Key"] = bot_api_key
            
            # Формируем URL для запроса
            if branch_id is not None:
                api_url = f"{events_service_url}/organizations/branches/{branch_id}/telegram-chat"
                payload = {"telegramChatId": chat_id, "organizationId": org_id}
            else:
                api_url = f"{events_service_url}/organizations/{org_id}/telegram-chat"
                payload = {"telegramChatId": chat_id}
            
            # Логируем детали запроса
            logger.info(f"Отправка запроса на сохранение telegram chat_id:")
            logger.info(f"  URL: {api_url}")
            logger.info(f"  Method: PUT")
            logger.info(f"  Headers: {headers}")
            logger.info(f"  Payload: {payload}")
            logger.info(f"  Events Service URL из config: {events_service_url}")
            
            # Вызываем API для сохранения chat_id
            response = requests.put(
                api_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            logger.info(f"Ответ от сервера:")
            logger.info(f"  Status Code: {response.status_code}")
            logger.info(f"  Response: {response.text}")
            
            if response.status_code == 200:
                branch_line = (
                    f"Филиал ID: <code>{branch_id}</code>\n\n" if branch_id else "\n"
                )
                await update.message.reply_text(
                    f"✅ <b>Успешно подключено!</b>\n\n"
                    f"Теперь вы будете получать уведомления о событиях и бронированиях в Telegram.\n\n"
                    f"Chat ID: <code>{chat_id}</code>\n"
                    f"Организация ID: <code>{org_id}</code>\n"
                    f"{branch_line}"
                    f"Вы можете вернуться в настройки клуба и увидеть статус подключения.",
                    parse_mode='HTML'
                )
            else:
                error_text = response.text if hasattr(response, 'text') else 'Unknown error'
                logger.error(f"Failed to save telegram chat_id: {response.status_code} - {error_text}")
                await update.message.reply_text(
                    f"❌ <b>Ошибка подключения</b>\n\n"
                    f"Не удалось сохранить подключение. Пожалуйста, попробуйте позже или обратитесь в поддержку.\n\n"
                    f"Код ошибки: {response.status_code}",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Error in connect_command: {e}")
            await update.message.reply_text(
                "❌ <b>Ошибка подключения</b>\n\n"
                "Произошла ошибка при подключении. Пожалуйста, попробуйте позже или обратитесь в поддержку.",
                parse_mode='HTML'
            )
    
    async def sports_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать доступные спорты"""
        try:
            sports = await self.api.get_sports()
            
            if not sports:
                await update.message.reply_text("❌ Не удалось загрузить список спортов.")
                return
            
            # Создаем кнопки для каждого спорта
            keyboard = []
            for sport in sports[:10]:  # Ограничиваем 10 спортами
                keyboard.append([
                    InlineKeyboardButton(
                        f"{sport.name} {sport.emoji or '🏃'}",
                        web_app=WebAppInfo(url=f"{self.app_url}/sports/{sport.id}")
                    )
                ])
            
            # Добавляем кнопку для открытия полного списка в приложении
            keyboard.append([
                InlineKeyboardButton(
                    f"{EMOJIS['web_app']} Все спорты в приложении",
                    web_app=WebAppInfo(url=f"{self.app_url}/sports")
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🏃‍♂️ **Доступные спорты:**\n\n"
                "Выберите спорт для просмотра деталей или откройте приложение для полного списка.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении спортов: {e}")
            await update.message.reply_text("❌ Произошла ошибка при загрузке спортов.")
    
    async def places_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать места"""
        try:
            places = await self.api.get_places()
            
            if not places:
                await update.message.reply_text("❌ Не удалось загрузить список мест.")
                return
            
            # Создаем кнопки для каждого места
            keyboard = []
            for place in places[:10]:  # Ограничиваем 10 местами
                keyboard.append([
                    InlineKeyboardButton(
                        f"{place.name} 📍",
                        web_app=WebAppInfo(url=f"{self.app_url}/places/{place.id}")
                    )
                ])
            
            # Добавляем кнопку для открытия полного списка в приложении
            keyboard.append([
                InlineKeyboardButton(
                    f"{EMOJIS['web_app']} Все места в приложении",
                    web_app=WebAppInfo(url=f"{self.app_url}/places")
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📍 **Доступные места:**\n\n"
                "Выберите место для просмотра деталей или откройте приложение для полного списка.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении мест: {e}")
            await update.message.reply_text("❌ Произошла ошибка при загрузке мест.")
    
    async def events_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать события"""
        try:
            events = await self.api.get_events()
            
            if not events:
                await update.message.reply_text("❌ Не удалось загрузить список событий.")
                return
            
            # Создаем кнопки для каждого события
            keyboard = []
            for event in events[:10]:  # Ограничиваем 10 событиями
                keyboard.append([
                    InlineKeyboardButton(
                        f"{event.title} 📅",
                        web_app=WebAppInfo(url=f"{self.app_url}/events/{event.id}")
                    )
                ])
            
            # Добавляем кнопку для открытия полного списка в приложении
            keyboard.append([
                InlineKeyboardButton(
                    f"{EMOJIS['web_app']} Все события в приложении",
                    web_app=WebAppInfo(url=f"{self.app_url}/events")
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📅 **Доступные события:**\n\n"
                "Выберите событие для просмотра деталей или откройте приложение для полного списка.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении событий: {e}")
            await update.message.reply_text("❌ Произошла ошибка при загрузке событий.")
    
    async def handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка данных от веб-приложения"""
        try:
            webapp_data = update.message.web_app_data
            
            if webapp_data:
                # Здесь можно обработать данные от веб-приложения
                # Например, регистрация на событие, обновление профиля и т.д.
                logger.info(f"Получены данные от веб-приложения: {webapp_data.data}")
                
                # Отправляем подтверждение пользователю
                await update.message.reply_text(
                    "✅ Данные успешно получены! Обрабатываем ваш запрос..."
                )
                
                # Здесь можно добавить логику обработки данных
                # Например, парсинг JSON и выполнение соответствующих действий
                
        except Exception as e:
            logger.error(f"Ошибка при обработке данных веб-приложения: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке данных.")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback'ов от inline кнопок"""
        query = update.callback_query
        data = query.data or ""

        if data.startswith("reg_ok:") or data.startswith("reg_no:") or data.startswith("reg_cancel:"):
            await self.handle_registration_callback(query, context)
            return

        await query.answer()
        
        if query.data == 'about_project':
            await self.show_about_project(query, context)
        elif query.data == 'back_to_start':
            user = query.from_user
            welcome_text = (
    f"👋 <b>Привет, {user.first_name}!</b>\n\n"
    "🏟 <b>Добро пожаловать в Place&Play для бизнеса!</b>\n\n"
    "🔔 <b>Получайте моментальные уведомления</b> о новых бронированиях прямо в Telegram\n\n"
    "💼 <b>Управляйте вашим клубом</b> через удобный сайт sports.placeandplay.uz:\n"
    "• Просматривайте все бронирования в календаре\n"
    "• Управляйте расписанием и кортами\n"
    "• Отслеживайте аналитику и статистику\n"
    "• Общайтесь с клиентами в чате\n"
    "• Настраивайте цены и рабочие часы\n\n"
    "⚡ <b>Подключите уведомления</b> в настройках вашего клуба, чтобы не пропустить ни одного бронирования!\n\n"
    "🌐 <b>Начните работу:</b> перейдите в <a href='https://sports.placeandplay.uz'>sports.placeandplay.uz</a>"
)

            keyboard = [
                [InlineKeyboardButton(f"{EMOJIS['details']} О проекте", callback_data='about_project')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text("❌ Неизвестная команда.")

    def _registration_keyboard(self, event_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"reg_ok:{event_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reg_no:{event_id}"),
        ]])

    def _events_service_url(self) -> str:
        raw = os.getenv(
            'PLACE_AND_PLAY_EVENTS_SERVICE_URL',
            'https://placeandplay-events-service-production.up.railway.app/PlaceAndPlay',
        ).rstrip('/')
        parsed = urlparse(raw)
        # Bare *.railway.internal defaults to port 80; Events listens on 8082.
        if parsed.hostname and parsed.hostname.endswith('.railway.internal') and parsed.port is None:
            netloc = f"{parsed.hostname}:8082"
            raw = urlunparse((parsed.scheme or 'http', netloc, parsed.path or '', '', '', '')).rstrip('/')
            logger.warning(
                "PLACE_AND_PLAY_EVENTS_SERVICE_URL without port; using %s",
                raw,
            )
        return raw

    def _events_bot_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        bot_api_key = os.getenv('TELEGRAM_BOT_API_KEY')
        if bot_api_key:
            headers["X-Telegram-Bot-Key"] = bot_api_key
        return headers

    def _parse_event_id(self, data: str) -> Optional[int]:
        try:
            return int(data.split(":", 1)[1])
        except (IndexError, ValueError):
            return None

    def _extract_booking_details(self, text: str) -> str:
        if not text:
            return ""
        lines = [ln.rstrip() for ln in text.splitlines()]
        while lines and (not lines[0].strip() or "Новое бронирование" in lines[0]):
            lines.pop(0)
        cut_markers = (
            "Нажмите кнопку",
            "Открыть бронирование",
            "Напишите причину",
        )
        kept = []
        for ln in lines:
            if any(marker in ln for marker in cut_markers):
                break
            kept.append(ln)
        return "\n".join(kept).strip()

    def _format_decision_text(self, approved: bool, reason: Optional[str], original_text: str) -> str:
        if approved:
            header = "✅ Заявка подтверждена. Статус: ожидает оплаты."
        else:
            header = "❌ Заявка отклонена."
            if reason:
                header += f"\nПричина: {html.escape(reason)}"
        booking = self._extract_booking_details(original_text)
        if booking:
            return f"{header}\n\n{booking}"
        return header

    async def _show_registration_result(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        original_message_id: Optional[int],
        original_text: str,
        approved: bool,
        reason: Optional[str] = None,
        fallback_reply_to: Optional[int] = None,
    ):
        text = self._format_decision_text(approved, reason, original_text)
        if original_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=original_message_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=None,
                )
                return
            except Exception as e:
                logger.warning(f"Не удалось обновить исходное сообщение заявки: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_to_message_id=fallback_reply_to or original_message_id,
        )

    def _send_registration_decision(self, event_id: int, action: str, telegram_chat_id: int, reason: Optional[str] = None):
        url = f"{self._events_service_url()}/events/club-bot/registration-decision"
        payload = {
            "eventId": event_id,
            "action": action,
            "telegramChatId": telegram_chat_id,
        }
        if reason:
            payload["reason"] = reason
        logger.info(f"Club bot registration decision: {action} event_id={event_id} chat_id={telegram_chat_id} url={url}")
        try:
            response = requests.post(url, json=payload, headers=self._events_bot_headers(), timeout=20)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка HTTP к Events Service ({url}): {e}")
            raise
        message = None
        try:
            body = response.json()
            message = body.get("message")
        except Exception:
            message = response.text
        return response.status_code, message

    def _expire_stale_rejects(self):
        now = time.time()
        stale = [chat_id for chat_id, item in self.pending_rejects.items()
                 if now - item.get("started_at", 0) > 15 * 60]
        for chat_id in stale:
            self.pending_rejects.pop(chat_id, None)

    async def handle_registration_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        data = query.data or ""
        event_id = self._parse_event_id(data)
        chat_id = query.message.chat_id if query.message else None
        original_message_id = query.message.message_id if query.message else None

        if event_id is None or chat_id is None:
            await query.answer("Некорректные данные заявки", show_alert=True)
            return

        if data.startswith("reg_cancel:"):
            await query.answer("Отменено")
            pending = self.pending_rejects.get(chat_id)
            original_id = pending.get("original_message_id") if pending else original_message_id
            self.pending_rejects.pop(chat_id, None)
            try:
                await query.message.delete()
            except Exception:
                pass
            if original_id:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=original_id,
                        reply_markup=self._registration_keyboard(event_id),
                    )
                except Exception as e:
                    logger.warning(f"Не удалось вернуть кнопки заявки {event_id}: {e}")
            return

        if data.startswith("reg_ok:"):
            await query.answer("Подтверждаем…")
            original_text = query.message.text or query.message.caption or ""
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            try:
                status, message = self._send_registration_decision(event_id, "approve", chat_id)
            except Exception as e:
                logger.error(f"Ошибка подтверждения заявки {event_id}: {e}")
                await context.bot.send_message(chat_id=chat_id, text="❌ Не удалось подтвердить заявку. Попробуйте ещё раз.")
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=original_message_id,
                        reply_markup=self._registration_keyboard(event_id),
                    )
                except Exception:
                    pass
                return
            if status == 200:
                self.pending_rejects.pop(chat_id, None)
                await self._show_registration_result(
                    context,
                    chat_id,
                    original_message_id,
                    original_text,
                    approved=True,
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Не удалось подтвердить заявку.\n{html.escape(message or 'Ошибка сервера')}",
                    parse_mode="HTML",
                    reply_to_message_id=original_message_id,
                )
                if status >= 500:
                    try:
                        await context.bot.edit_message_reply_markup(
                            chat_id=chat_id,
                            message_id=original_message_id,
                            reply_markup=self._registration_keyboard(event_id),
                        )
                    except Exception:
                        pass
            return

        if data.startswith("reg_no:"):
            await query.answer("Укажите причину отклонения")
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            prompt = await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "✏️ Напишите причину отклонения <b>одним сообщением</b>.\n"
                    "Она будет отправлена участникам."
                ),
                parse_mode="HTML",
                reply_to_message_id=original_message_id,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Отмена", callback_data=f"reg_cancel:{event_id}")
                ]]),
            )
            self.pending_rejects[chat_id] = {
                "event_id": event_id,
                "original_message_id": original_message_id,
                "original_text": query.message.text or query.message.caption or "",
                "prompt_message_id": prompt.message_id,
                "started_at": time.time(),
            }

    async def handle_reject_reason_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_chat:
            return
        self._expire_stale_rejects()
        chat_id = update.effective_chat.id
        pending = self.pending_rejects.get(chat_id)
        if not pending:
            return

        reason = (update.message.text or "").strip()
        if not reason:
            await update.message.reply_text("Пожалуйста, напишите причину отклонения текстом.")
            return

        event_id = pending["event_id"]
        original_message_id = pending.get("original_message_id")
        original_text = pending.get("original_text") or ""
        prompt_message_id = pending.get("prompt_message_id")
        try:
            status, message = self._send_registration_decision(event_id, "reject", chat_id, reason)
        except Exception as e:
            logger.error(f"Ошибка отклонения заявки {event_id}: {e}")
            await update.message.reply_text("❌ Не удалось отклонить заявку. Попробуйте ещё раз или напишите причину повторно.")
            return

        if status == 200:
            self.pending_rejects.pop(chat_id, None)
            if prompt_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)
                except Exception:
                    pass
            await self._show_registration_result(
                context,
                chat_id,
                original_message_id,
                original_text,
                approved=False,
                reason=reason,
                fallback_reply_to=update.message.message_id,
            )
        else:
            await update.message.reply_text(
                f"❌ Не удалось отклонить заявку.\n{html.escape(message or 'Ошибка сервера')}",
                parse_mode="HTML",
            )
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=original_message_id,
                    reply_markup=self._registration_keyboard(event_id),
                )
            except Exception:
                pass
            self.pending_rejects.pop(chat_id, None)
    
    async def show_about_project(self, query, context):
        """Показать информацию о проекте"""
        about_text = (
    "🏟 <b>Place&Play для бизнеса — управление спортивным клубом</b>\n\n"
    "Современная платформа для управления спортивными клубами и площадками.\n\n"
    "🔔 <b>Моментальные уведомления:</b>\n"
    "— Получайте уведомления о новых бронированиях в Telegram\n"
    "— Информируйтесь о изменениях статусов бронирований\n"
    "— Следите за активностью клиентов в реальном времени\n\n"
    "💼 <b>Управление клубом:</b>\n"
    "— Просматривайте все бронирования в удобном календаре\n"
    "— Управляйте расписанием и доступностью кортов\n"
    "— Настраивайте цены и рабочие часы для каждого корта\n"
    "— Отслеживайте аналитику и статистику загрузки\n\n"
    "💬 <b>Общение с клиентами:</b>\n"
    "— Общайтесь с клиентами прямо в системе\n"
    "— Отвечайте на вопросы и уточняйте детали\n"
    "— Управляйте участниками тренировок и событий\n\n"
    "📊 <b>Аналитика и отчеты:</b>\n"
    "— Анализируйте загрузку кортов по времени\n"
    "— Отслеживайте популярные временные слоты\n"
    "— Получайте статистику по бронированиям\n\n"
    "🌐 <b>Начните работу:</b>\n"
    "<a href='https://sports.placeandplay.uz'>sports.placeandplay.uz</a>\n\n"
    "📧 <b>Поддержка:</b>\n"
    "Вопросы и предложения — @abramov_1"
)






        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_start')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            about_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    def run(self):
        """Запуск бота"""
        print("🤖 Бот запущен и готов к работе!")
        print(f"🌐 Веб-приложение доступно по адресу: {self.app_url}")
        logger.info("Запуск бота в режиме polling...")
        
        # Запускаем бота
        try:
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Критическая ошибка при запуске бота: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """Главная функция для запуска бота"""
    try:
        print("🚀 Запуск Place&Play Telegram Bot...")
        logger.info("Инициализация бота...")
        
        # Проверяем наличие токена
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            error_msg = "❌ Ошибка: TELEGRAM_BOT_TOKEN не найден в config.env"
            print(error_msg)
            logger.error(error_msg)
            return
        
        # Проверяем наличие URL приложения
        app_url = os.getenv('TELEGRAM_APP_URL')
        if not app_url:
            error_msg = "❌ Ошибка: TELEGRAM_APP_URL не найден в config.env"
            print(error_msg)
            logger.error(error_msg)
            return
        
        print(f"✅ Токен бота: {token[:10]}...")
        print(f"✅ URL приложения: {app_url}")
        logger.info(f"Токен загружен, длина: {len(token)}")
        logger.info(f"URL приложения: {app_url}")
        
        # Проверяем подключение к боту (синхронно, чтобы не создавать конфликт с event loop)
        try:
            bot_info_url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(bot_info_url, timeout=5)
            if response.status_code == 200:
                bot_data = response.json()
                if bot_data.get('ok'):
                    bot_info = bot_data.get('result', {})
                    username = bot_info.get('username', 'unknown')
                    first_name = bot_info.get('first_name', 'Unknown')
                    bot_id = bot_info.get('id', 0)
                    print(f"✅ Бот подключен: @{username} ({first_name})")
                    logger.info(f"Бот подключен: @{username}, ID: {bot_id}")
                    if username != "placeandplay_agent_bot":
                        warning = f"⚠️  ВНИМАНИЕ: Токен принадлежит боту @{username}, а не @placeandplay_agent_bot"
                        print(warning)
                        logger.warning(warning)
                else:
                    error_msg = f"❌ Ошибка API Telegram: {bot_data.get('description', 'Unknown error')}"
                    print(error_msg)
                    logger.error(error_msg)
                    return
            else:
                error_msg = f"❌ Ошибка HTTP при проверке бота: {response.status_code}"
                print(error_msg)
                logger.error(error_msg)
                return
        except Exception as e:
            error_msg = f"❌ Ошибка при проверке подключения к боту: {e}"
            print(error_msg)
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            return
        
        # Создаем и запускаем бота
        print("🔄 Создание экземпляра бота...")
        logger.info("Создание экземпляра PlaceAndPlayAppBot...")
        bot = PlaceAndPlayAppBot()
        print("✅ Бот создан, запуск polling...")
        logger.info("Экземпляр бота создан, запуск run()...")
        bot.run()
        
    except KeyboardInterrupt:
        print("\n⚠️  Получен сигнал остановки (Ctrl+C)")
        logger.info("Получен сигнал остановки от пользователя")
    except Exception as e:
        error_msg = f"❌ Ошибка при запуске бота: {e}"
        print(error_msg)
        logger.error(error_msg, exc_info=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
