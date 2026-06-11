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
                          disable_web_page_preview: bool = True) -> bool:
    """
    Отправка сообщения в Telegram (синхронный метод через requests)
    
    Args:
        chat_id: ID чата в Telegram
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML, Markdown)
    
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
        
        logger.debug(f"Отправка сообщения в Telegram: chat_id={chat_id}, parse_mode={parse_mode}, message={message[:200]}...")
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Сообщение отправлено в чат {chat_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
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
        
        # Отправляем сообщение
        success = send_telegram_message(chat_id, message, parse_mode, disable_preview)
        
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


if __name__ == '__main__':
    port = int(os.getenv('PORT', os.getenv('NOTIFICATION_SERVICE_PORT', '5000')))
    host = os.getenv('NOTIFICATION_SERVICE_HOST', '0.0.0.0')
    
    logger.info(f"🚀 Запуск сервиса уведомлений на {host}:{port}")
    app.run(host=host, port=port, debug=False)

