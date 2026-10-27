"""
Сервис для отправки уведомлений в Telegram
Принимает HTTP запросы от основного приложения и отправляет уведомления в Telegram бот
"""
import os
import logging
from typing import Optional, Dict, List
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from functools import wraps

# Загружаем переменные окружения
load_dotenv('config.env')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask приложения
app = Flask(__name__)
CORS(app)  # Разрешаем CORS для запросов от основного приложения

# Инициализация Telegram бота
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в config.env")

# Используем синхронный подход через requests вместо async Bot
# Это избегает проблем с event loop в Flask
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Карточки «Присоединиться» должен готовить именно бот, из которого открывается Mini App
# (placeandplay_notification_bot). Если переменная не задана — используем основной токен.
SHARE_CARD_BOT_TOKEN = os.getenv('SHARE_CARD_BOT_TOKEN') or TELEGRAM_BOT_TOKEN
SHARE_CARD_API_URL = f"https://api.telegram.org/bot{SHARE_CARD_BOT_TOKEN}"

# API ключ для защиты endpoint (опционально)
API_KEY = os.getenv('NOTIFICATION_API_KEY', '')


# Удаляем async_to_sync декоратор, так как будем использовать синхронные запросы


def check_api_key(f):
    """Декоратор для проверки API ключа (если настроен)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if API_KEY:
            provided_key = request.headers.get('X-API-Key') or request.json.get('api_key') if request.is_json else None
            if provided_key != API_KEY:
                return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function


def send_telegram_message(chat_id: int, message: str, parse_mode: str = 'HTML',
                          disable_web_page_preview: bool = True,
                          reply_markup: Optional[Dict] = None) -> bool:
    """
    Отправка сообщения в Telegram (синхронный метод через requests)
    
    Args:
        chat_id: ID чата в Telegram
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML, Markdown)
        reply_markup: Опциональная клавиатура Telegram (inline_keyboard и т.д.)
    
    Returns:
        True если сообщение отправлено успешно, False в противном случае
    """
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        logger.debug(f"Отправка сообщения в Telegram: chat_id={chat_id}, parse_mode={parse_mode}, message={message[:200]}...")
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Сообщение отправлено в чат {chat_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Ответ Telegram: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке сообщения: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервиса"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/send-notification', methods=['POST'])
@check_api_key
def send_notification():
    """
    Endpoint для отправки уведомления в Telegram
    
    Request body:
    {
        "chat_id": 123456789,  # ID чата в Telegram (обязательно)
        "message": "Текст уведомления",  # Текст сообщения (обязательно)
        "parse_mode": "HTML"  # Опционально: HTML или Markdown
    }
    
    Returns:
    {
        "success": true/false,
        "message": "Сообщение отправлено" / "Ошибка",
        "error": "Описание ошибки" (если success=false)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        chat_id = data.get('chat_id')
        message = data.get('message')
        
        if not chat_id:
            return jsonify({
                'success': False,
                'error': 'chat_id is required'
            }), 400
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'message is required'
            }), 400
        
        parse_mode = data.get('parse_mode', 'HTML')
        disable_preview = data.get('disable_web_page_preview', True)
        if not isinstance(disable_preview, bool):
            disable_preview = True
        reply_markup = data.get('reply_markup')
        if reply_markup is not None and not isinstance(reply_markup, dict):
            reply_markup = None
        
        # Отправляем сообщение
        success = send_telegram_message(chat_id, message, parse_mode, disable_preview, reply_markup)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Notification sent successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send notification'
            }), 500
            
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/send-bulk-notifications', methods=['POST'])
@check_api_key
def send_bulk_notifications():
    """
    Endpoint для массовой отправки уведомлений
    
    Request body:
    {
        "notifications": [
            {
                "chat_id": 123456789,
                "message": "Текст уведомления",
                "parse_mode": "HTML"
            },
            ...
        ]
    }
    
    Returns:
    {
        "success": true/false,
        "sent": 5,  # Количество успешно отправленных
        "failed": 2,  # Количество неудачных
        "results": [...]  # Детали по каждому уведомлению
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        notifications = data.get('notifications', [])
        
        if not notifications or not isinstance(notifications, list):
            return jsonify({
                'success': False,
                'error': 'notifications array is required'
            }), 400
        
        results = []
        sent_count = 0
        failed_count = 0
        
        for notification in notifications:
            chat_id = notification.get('chat_id')
            message = notification.get('message')
            parse_mode = notification.get('parse_mode', 'HTML')
            
            if not chat_id or not message:
                results.append({
                    'chat_id': chat_id,
                    'success': False,
                    'error': 'chat_id and message are required'
                })
                failed_count += 1
                continue
            
            success = send_telegram_message(chat_id, message, parse_mode)
            
            if success:
                results.append({
                    'chat_id': chat_id,
                    'success': True
                })
                sent_count += 1
            else:
                results.append({
                    'chat_id': chat_id,
                    'success': False,
                    'error': 'Failed to send'
                })
                failed_count += 1
        
        return jsonify({
            'success': True,
            'sent': sent_count,
            'failed': failed_count,
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка при обработке массовой отправки: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/send-event-notification', methods=['POST'])
@check_api_key
def send_event_notification():
    """
    Специализированный endpoint для уведомлений о событиях
    
    Request body:
    {
        "chat_id": 123456789,
        "event": {
            "title": "Название события",
            "date": "2025-12-10",
            "time": "18:00",
            "place": "Название площадки",
            "court": "Корт 1",
            "type": "training" | "rental" | "open_booking",
            "status": "confirmed" | "cancelled" | ...
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        chat_id = data.get('chat_id')
        event = data.get('event', {})
        
        if not chat_id:
            return jsonify({
                'success': False,
                'error': 'chat_id is required'
            }), 400
        
        if not event:
            return jsonify({
                'success': False,
                'error': 'event data is required'
            }), 400
        
        # Формируем сообщение о событии
        title = event.get('title', 'Событие')
        date = event.get('date', '')
        time = event.get('time', '')
        place = event.get('place', '')
        court = event.get('court', '')
        event_type = event.get('type', '')
        status = event.get('status', '')
        
        # Эмодзи в зависимости от типа события
        emoji_map = {
            'training': '🏋️',
            'rental': '🏟️',
            'open_booking': '👥',
            'tournament': '🏆'
        }
        emoji = emoji_map.get(event_type, '📅')
        
        # Формируем сообщение
        message = f"{emoji} <b>{title}</b>\n\n"
        
        if date:
            message += f"📅 Дата: {date}\n"
        if time:
            message += f"🕐 Время: {time}\n"
        if place:
            message += f"📍 Место: {place}\n"
        if court:
            message += f"🏟️ Корт: {court}\n"
        if status:
            status_text = {
                'confirmed': '✅ Подтверждено',
                'cancelled': '❌ Отменено',
                'pending': '⏳ Ожидает подтверждения',
                'collecting_participants': '👥 Сбор участников',
                'participants_collected': '✅ Участники собраны'
            }.get(status, status)
            message += f"📊 Статус: {status_text}\n"
        
        # Отправляем сообщение
        success = send_telegram_message(chat_id, message)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Event notification sent successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send notification'
            }), 500
            
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о событии: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ---------------------------------------------------------------------------
# Карточка события для пересылки в чаты (Mini App shareMessage)
# ---------------------------------------------------------------------------

def _share_markup(button_text: str, button_url: str) -> Dict:
    return {"inline_keyboard": [[{"text": button_text, "url": button_url}]]}


@app.route('/prepare-share', methods=['POST'])
@check_api_key
def prepare_share():
    """
    Готовит «карточку» события от имени бота (savePreparedInlineMessage).
    Mini App потом вызывает Telegram.WebApp.shareMessage(id) — пользователь выбирает чат,
    и карточка уходит туда с кнопкой «Присоединиться».
    Тело: {telegramUserId, eventId, title, text (HTML), buttonText, buttonUrl}
    """
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get('telegramUserId'))
        event_id = int(data.get('eventId'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'telegramUserId and eventId are required'}), 400
    text = (data.get('text') or '').strip()
    button_url = (data.get('buttonUrl') or '').strip()
    if not text or not button_url.startswith('https://'):
        return jsonify({'success': False, 'error': 'text and https buttonUrl are required'}), 400

    result = {
        "type": "article",
        # id нужен, чтобы по chosen_inline_result понять, какое это событие
        "id": f"ev{event_id}",
        "title": (data.get('title') or 'Place&Play')[:100],
        "input_message_content": {
            "message_text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        },
        "reply_markup": _share_markup((data.get('buttonText') or 'Присоединиться')[:64], button_url),
    }
    payload = {
        "user_id": user_id,
        "result": result,
        "allow_user_chats": True,
        "allow_bot_chats": False,
        "allow_group_chats": True,
        "allow_channel_chats": False,
    }
    try:
        resp = requests.post(f"{SHARE_CARD_API_URL}/savePreparedInlineMessage", json=payload, timeout=10)
        body = resp.json() if resp.content else {}
        if not resp.ok or not body.get('ok'):
            logger.error(f"savePreparedInlineMessage failed: {resp.status_code} {resp.text[:300]}")
            return jsonify({'success': False, 'error': body.get('description', 'telegram error')}), 502
        prepared = body.get('result', {})
        return jsonify({'success': True, 'id': prepared.get('id'), 'expirationDate': prepared.get('expiration_date')})
    except requests.exceptions.RequestException as e:
        logger.error(f"savePreparedInlineMessage error: {e}")
        return jsonify({'success': False, 'error': 'telegram unreachable'}), 502


# ---------------------------------------------------------------------------
# Webhook Telegram: inline-режим для карточек «Присоединиться».
# Mini App вызывает switchInlineQuery("ev830"), Telegram присылает inline_query сюда,
# мы отвечаем карточкой события; после выбора приходит chosen_inline_result с
# inline_message_id — регистрируем его в Events, чтобы потом обновлять карточку в чате.
# ---------------------------------------------------------------------------
import re as _re

TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
# ev<id>[d<yyyymmdd>][_<inviterUserId>]
_INLINE_QUERY_RE = _re.compile(r'^\s*ev(\d+)(?:d(\d{8}))?(?:_(\d+))?\s*$')
_RESULT_ID_RE = _re.compile(r'^ev(\d+)(?:d(\d{8}))?$')


def _iso_from_compact(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else None


def _events_post(path: str, payload: Dict, timeout: int = 8):
    base = (os.getenv('EVENTS_INTERNAL_BASE_URL') or '').rstrip('/')
    key = os.getenv('EVENTS_CARD_REGISTER_KEY') or ''
    if not base or not key:
        logger.warning('EVENTS_INTERNAL_BASE_URL/EVENTS_CARD_REGISTER_KEY не заданы')
        return None
    return requests.post(f"{base}{path}", json=payload, headers={"X-Internal-Key": key}, timeout=timeout)


def _handle_inline_query(iq: Dict):
    m = _INLINE_QUERY_RE.match(iq.get('query') or '')
    results = []
    if m:
        event_id = int(m.group(1))
        compact_date = m.group(2)
        inviter = int(m.group(3)) if m.group(3) else None
        try:
            resp = _events_post('/bot/event-cards/render', {"eventId": event_id, "inviterUserId": inviter, "occurrenceDate": _iso_from_compact(compact_date)})
            if resp is not None and resp.ok:
                card = resp.json()
                results.append({
                    "type": "article",
                    "id": f"ev{event_id}" + (f"d{compact_date}" if compact_date else ""),
                    "title": (card.get('title') or 'Place&Play')[:100],
                    "description": "Отправить карточку с кнопкой «Присоединиться»",
                    "input_message_content": {
                        "message_text": card.get('text') or '',
                        "parse_mode": "HTML",
                        "link_preview_options": {"is_disabled": True},
                    },
                    "reply_markup": _share_markup((card.get('buttonText') or 'Присоединиться')[:64], card.get('buttonUrl') or ''),
                })
            else:
                logger.warning(f"inline_query: render event={event_id} -> {resp.status_code if resp is not None else 'no response'}")
        except Exception as e:
            logger.error(f"inline_query: render failed: {e}")
    try:
        requests.post(f"{SHARE_CARD_API_URL}/answerInlineQuery", json={
            "inline_query_id": iq.get('id'),
            "results": results,
            "cache_time": 0,
            "is_personal": True,
        }, timeout=8)
    except Exception as e:
        logger.error(f"answerInlineQuery failed: {e}")


def _handle_chosen_inline_result(chosen: Dict):
    result_id = chosen.get('result_id') or ''
    inline_message_id = chosen.get('inline_message_id')
    logger.info(f"CHOSEN_INLINE_RESULT result_id={result_id} inline_message_id={inline_message_id}")
    rm = _RESULT_ID_RE.match(result_id)
    if not rm or not inline_message_id:
        return
    event_id = int(rm.group(1))
    try:
        resp = _events_post('/bot/event-cards', {
            "eventId": event_id,
            "occurrenceDate": _iso_from_compact(rm.group(2)),
            "inlineMessageId": inline_message_id,
            "telegramUserId": (chosen.get('from') or {}).get('id'),
        })
        logger.info(f"Регистрация карточки события {event_id}: HTTP {resp.status_code if resp is not None else 'no response'}")
    except Exception as e:
        logger.error(f"Не удалось зарегистрировать карточку события {event_id}: {e}")


@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Приёмник обновлений бота (inline_query, chosen_inline_result). Защищён secret_token."""
    if not TELEGRAM_WEBHOOK_SECRET or request.headers.get('X-Telegram-Bot-Api-Secret-Token') != TELEGRAM_WEBHOOK_SECRET:
        return jsonify({'ok': False}), 403
    update = request.get_json(silent=True) or {}
    try:
        if update.get('inline_query'):
            _handle_inline_query(update['inline_query'])
        elif update.get('chosen_inline_result'):
            _handle_chosen_inline_result(update['chosen_inline_result'])
    except Exception as e:
        logger.error(f"telegram_webhook error: {e}")
    return jsonify({'ok': True})


@app.route('/refresh-share', methods=['POST'])
@check_api_key
def refresh_share():
    """
    Обновляет уже отправленную в чат карточку (editMessageText по inline_message_id).
    Тело: {inlineMessageId, text (HTML), buttonText, buttonUrl}
    """
    data = request.get_json(silent=True) or {}
    inline_message_id = (data.get('inlineMessageId') or '').strip()
    text = (data.get('text') or '').strip()
    button_url = (data.get('buttonUrl') or '').strip()
    if not inline_message_id or not text or not button_url.startswith('https://'):
        return jsonify({'success': False, 'error': 'inlineMessageId, text and https buttonUrl are required'}), 400
    payload = {
        "inline_message_id": inline_message_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
        "reply_markup": _share_markup((data.get('buttonText') or 'Присоединиться')[:64], button_url),
    }
    try:
        resp = requests.post(f"{SHARE_CARD_API_URL}/editMessageText", json=payload, timeout=10)
        body = resp.json() if resp.content else {}
        if resp.ok and body.get('ok'):
            return jsonify({'success': True})
        description = str(body.get('description', ''))
        if 'message is not modified' in description:
            return jsonify({'success': True, 'unchanged': True})
        logger.warning(f"editMessageText failed: {resp.status_code} {description[:200]}")
        # 400 «message to edit not found» и подобное — карточку уже не обновить, Events-Service её забудет
        return jsonify({'success': False, 'error': description or 'telegram error', 'gone': resp.status_code == 400}), 502
    except requests.exceptions.RequestException as e:
        logger.error(f"editMessageText error: {e}")
        return jsonify({'success': False, 'error': 'telegram unreachable'}), 502


if __name__ == '__main__':
    port = int(os.getenv('PORT', os.getenv('NOTIFICATION_SERVICE_PORT', '5000')))
    host = os.getenv('NOTIFICATION_SERVICE_HOST', '0.0.0.0')
    
    logger.info(f"🚀 Запуск сервиса уведомлений на {host}:{port}")
    app.run(host=host, port=port, debug=False)

