"""
Модели данных для Place&Play Telegram Bot
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class Sport:
    """Модель вида спорта"""
    id: int
    name: str
    
    def get_emoji(self) -> str:
        """Возвращает эмодзи для вида спорта"""
        sport_emojis = {
            1: "🎾",   # Теннис
            2: "⚽",   # Футбол
            3: "🏀",   # Баскетбол
            4: "🏐",   # Волейбол
            5: "🎱",   # Бильярд
            6: "🎳",   # Боулинг
            7: "🎯",   # Дартс
            8: "🏓",   # Настольный теннис
            9: "⛳",   # Гольф
            10: "🏉",  # Регби
            11: "🎾",  # Сквош
            12: "🏸",  # Бадминтон
            13: "🥋",  # Боевые искусства
            14: "🚣",  # Гребля
            15: "🧗",  # Скалолазание
            16: "🏄",  # Виндсёрфинг
            17: "⛷️",  # Горные лыжи / Сноуборд
            18: "🏇",  # Конный спорт
            19: "🏒",  # Хоккей
            20: "🏃",  # Лёгкая атлетика
            21: "🏊",  # Плавание
            22: "🏋️",  # Тяжёлая атлетика
            23: "🤺",  # Фехтование
            24: "🤾",  # Гандбол
            25: "🎮",  # Киберспорт
            26: "🏎️",  # Автоспорт
            27: "🎲",  # Настольные игры
        }
        return sport_emojis.get(self.id, "🏆")


@dataclass
class Place:
    """Модель спортивного заведения"""
    place_id: int
    name: str
    address: str
    latitude: float
    longitude: float
    type_id: int
    verified: bool
    description: str
    phone: str
    current_location_city_id: int
    current_location_country_id: int
    org_id: int
    
    def get_verified_badge(self) -> str:
        """Возвращает значок верификации
        🏆 - проверенное заведение (verified=True)
        🆕 - новое/непроверенное заведение (verified=False)
        """
        return "🏆" if self.verified else "🆕"
    
    def get_place_icon(self) -> str:
        """Возвращает иконку типа заведения"""
        place_icons = {
            1: "🎾",   # Теннис
            2: "⚽",   # Футбол
            3: "🏀",   # Баскетбол
            4: "🏐",   # Волейбол
            5: "🎱",   # Бильярд
            6: "🎳",   # Боулинг
            7: "🎯",   # Дартс
            8: "🏓",   # Настольный теннис
            9: "⛳",   # Гольф
            10: "🏉",  # Регби
            11: "🎾",  # Сквош
            12: "🏸",  # Бадминтон
            13: "🥋",  # Боевые искусства
            14: "🚣",  # Гребля
            15: "🧗",  # Скалолазание
            16: "🏄",  # Виндсёрфинг
            17: "⛷️",  # Горные лыжи / Сноуборд
            18: "🏇",  # Конный спорт
            19: "🏒",  # Хоккей
            20: "🏃",  # Лёгкая атлетика
            21: "🏊",  # Плавание
            22: "🏋️",  # Тяжёлая атлетика
            23: "🤺",  # Фехтование
            24: "🤾",  # Гандбол
            25: "🎮",  # Киберспорт
            26: "🏎️",  # Автоспорт
            27: "🎲",  # Настольные игры
        }
        return place_icons.get(self.type_id, "🏢")
    
    def get_full_badge(self) -> str:
        """Возвращает полный значок с типом и верификацией"""
        verified_badge = "🏆" if self.verified else "🆕"
        place_icon = self.get_place_icon()
        return f"{place_icon} {verified_badge}"


@dataclass
class Event:
    """Модель спортивного события"""
    id: int
    title: str
    description: str
    date: datetime
    place_name: str
    participants_count: int
    max_participants: int
    sport_name: str
    organizer: str
    status: str
    
    def get_formatted_info(self) -> str:
        """Возвращает отформатированную информацию о событии"""
        # Определяем эмодзи для спорта
        sport_emojis = {
            'Теннис': '🎾',
            'Футбол': '⚽',
            'Баскетбол': '🏀',
            'Волейбол': '🏐',
            'Бильярд': '🎱',
            'Боулинг': '🎳',
            'Дартс': '🎯',
            'Настольный теннис': '🏓',
            'Гольф': '⛳',
            'Регби': '🏉',
            'Сквош': '🎾',
            'Бадминтон': '🏸',
            'Боевые искусства': '🥋',
            'Гребля': '🚣',
            'Скалолазание': '🧗',
            'Виндсёрфинг': '🏄',
            'Горные лыжи': '⛷️',
            'Сноуборд': '⛷️',
            'Конный спорт': '🏇',
            'Хоккей': '🏒',
            'Лёгкая атлетика': '🏃',
            'Плавание': '🏊',
            'Тяжёлая атлетика': '🏋️',
            'Фехтование': '🤺',
            'Гандбол': '🤾',
            'Киберспорт': '🎮',
            'Автоспорт': '🏎️',
            'Настольные игры': '🎲'
        }
        
        sport_emoji = sport_emojis.get(self.sport_name, '🏆')
        
        # Определяем эмодзи для статуса
        status_emojis = {
            'CONFIRMED': '✅',
            'IN_PROGRESS': '🔄',
            'COMPLETED': '🏁',
            'EXPIRED': '⏰',
            'CANCELLED': '❌',
            'PENDING': '⏳'
        }
        
        status_emoji = status_emojis.get(self.status, '📋')
        
        return (
            f"{sport_emoji} **{self.title}**\n"
            f"📝 {self.description}\n"
            f"👤 **Организатор:** {self.organizer}\n"
            f"{status_emoji} **Статус:** {self.status}\n"
            f"📅 {self.date.strftime('%d.%m.%Y %H:%M')}\n"
            f"📍 {self.place_name}\n"
            f"👥 {self.participants_count}/{self.max_participants}"
        )


@dataclass
class UserState:
    """Состояние пользователя в боте"""
    user_id: int
    current_step: str = "start"
    selected_sport: Optional[Sport] = None
    selected_place: Optional[Place] = None
    selected_event: Optional[Event] = None
    auth_tokens: Optional[dict] = None 