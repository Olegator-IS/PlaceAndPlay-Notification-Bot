"""
Сервис для работы с API Place&Play
"""
import requests
import json
from typing import List, Optional, Dict
from datetime import datetime
import logging
from models import Sport, Place, Event

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlaceAndPlayAPI:
    """Класс для работы с API Place&Play"""
    
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.auth_tokens = None
        
        # Устанавливаем заголовки по умолчанию
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PlaceAndPlay-TelegramBot/1.0',
            'language': 'ru',
            'isUser': 'true'
        })
    
    def authenticate(self) -> bool:
        """
        Аутентификация в API Place&Play
        Возвращает True при успешной аутентификации
        """
        try:
            login_data = {
                "email": self.email,
                "password": self.password
            }
            
            # Устанавливаем заголовки для аутентификации
            headers = {
                'language': 'ru'
            }
            
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json=login_data,
                headers=headers
            )
            
            if response.status_code == 200:
                # Сохраняем токены
                self.auth_tokens = response.json()
                logger.info("Успешная аутентификация в API")
                return True
            else:
                logger.error(f"Ошибка аутентификации: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при аутентификации: {e}")
            return False
    
    def get_sports_list(self) -> List[Sport]:
        """
        Получение списка видов спорта
        Возвращает список объектов Sport
        """
        try:
            # Устанавливаем заголовки для запроса
            headers = {
                'language': 'ru'
            }
            
            response = self.session.get(
                f"{self.base_url}/auth/getListOfSports",
                headers=headers
            )
            
            if response.status_code == 200:
                sports_data = response.json()
                sports = []
                
                for sport_data in sports_data:
                    sport = Sport(
                        id=sport_data['id'],
                        name=sport_data['name']
                    )
                    sports.append(sport)
                
                logger.info(f"Получено {len(sports)} видов спорта")
                return sports
            else:
                logger.error(f"Ошибка получения списка спорта: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка спорта: {e}")
            return []
    
    def get_places_by_city(self, city_id: int = 1) -> List[Place]:
        """
        Получение списка заведений по городу
        Возвращает список объектов Place
        """
        try:
            # Устанавливаем заголовки для запроса
            headers = {
                'language': 'ru'
            }
            
            response = self.session.get(
                f"{self.base_url}/private/places/allByCityForWeb",
                params={'currentCity': city_id},
                headers=headers
            )
            
            if response.status_code == 200:
                places_data = response.json()
                places = []
                
                for place_data in places_data:
                    place = Place(
                        place_id=place_data['placeId'],
                        name=place_data['name'],
                        address=place_data['address'],
                        latitude=place_data['latitude'],
                        longitude=place_data['longitude'],
                        type_id=place_data['typeId'],
                        verified=place_data['verified'],
                        description=place_data['description'],
                        phone=place_data['phone'],
                        current_location_city_id=place_data['currentLocationCityId'],
                        current_location_country_id=place_data['currentLocationCountryId'],
                        org_id=place_data['orgId']
                    )
                    places.append(place)
                
                logger.info(f"Получено {len(places)} заведений")
                return places
            else:
                logger.error(f"Ошибка получения списка заведений: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка заведений: {e}")
            return []
    
    def get_events_by_place(self, place_id: int, size: int = 100) -> List[Event]:
        """
        Получение событий по заведению
        Возвращает список объектов Event
        """
        try:
            # Проверяем аутентификацию
            if not self.auth_tokens:
                if not self.authenticate():
                    logger.error("Не удалось аутентифицироваться для получения событий")
                    return []
            
            # Устанавливаем заголовки с токенами
            headers = {
                'accessToken': self.auth_tokens.get('accessToken', ''),
                'refreshToken': self.auth_tokens.get('refreshToken', ''),
                'language': 'ru'
            }
            
            # Получаем события с текущей датой
            current_date = datetime.now().strftime('%Y-%m-%d')
            response = self.session.get(
                f"{self.base_url}/v1/events/pagination",
                params={
                    'placeId': place_id,
                    'size': size,
                    'sortDirection': 'DESC',
                    'date': current_date
                },
                headers=headers
            )
            
            logger.info(f"Запрос событий: {response.url}")
            logger.info(f"Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                events_data = response.json()
                logger.info(f"Структура ответа API: {list(events_data.keys()) if isinstance(events_data, dict) else 'Не словарь'}")
                
                events = []
                
                # Обрабатываем события (адаптируем под реальную структуру API)
                # API может возвращать данные в разных форматах
                if isinstance(events_data, dict):
                    # Если это словарь с content
                    events_list = events_data.get('content', [])
                elif isinstance(events_data, list):
                    # Если это прямой список
                    events_list = events_data
                else:
                    logger.error(f"Неожиданный формат ответа API: {type(events_data)}")
                    return []
                
                for event_data in events_list:
                    try:
                        logger.info(f"Обработка события: {event_data}")
                        
                        # Извлекаем данные события (адаптируем под реальную структуру)
                        event_id = event_data.get('id') or event_data.get('eventId') or 0
                        event_title = event_data.get('title') or event_data.get('name') or event_data.get('eventName') or 'Без названия'
                        event_description = event_data.get('description') or event_data.get('eventDescription') or 'Описание отсутствует'
                        
                        # Обработка даты
                        date_data = event_data.get('dateTime') or event_data.get('date') or event_data.get('eventDate') or event_data.get('startDate')
                        if date_data:
                            try:
                                # Проверяем, является ли дата списком [год, месяц, день, час, минута]
                                if isinstance(date_data, list) and len(date_data) >= 5:
                                    year, month, day, hour, minute = date_data[:5]
                                    event_date = datetime(year, month, day, hour, minute)
                                elif 'T' in str(date_data):
                                    event_date = datetime.fromisoformat(str(date_data).replace('Z', '+00:00'))
                                else:
                                    event_date = datetime.strptime(str(date_data), '%Y-%m-%d %H:%M:%S')
                            except Exception as e:
                                logger.warning(f"Ошибка парсинга даты {date_data}: {e}")
                                event_date = datetime.now()
                        else:
                            event_date = datetime.now()
                        
                        # Остальные поля
                        place_name = event_data.get('placeName') or event_data.get('place') or 'Место не указано'
                        participants_count = event_data.get('participantsCount') or event_data.get('currentParticipants') or 0
                        max_participants = event_data.get('maxParticipants') or event_data.get('maxParticipantsCount') or 10
                        sport_name = event_data.get('sportName') or event_data.get('sport') or 'Спорт не указан'
                        
                        # Извлекаем организатора
                        organizer_data = event_data.get('organizer', {})
                        if isinstance(organizer_data, dict):
                            organizer_name = organizer_data.get('name', 'Не указан')
                        else:
                            organizer_name = str(organizer_data) if organizer_data else 'Не указан'
                        
                        # Извлекаем статус
                        event_status = event_data.get('status', 'Не указан')
                        
                        event = Event(
                            id=event_id,
                            title=event_title,
                            description=event_description,
                            date=event_date,
                            place_name=place_name,
                            participants_count=participants_count,
                            max_participants=max_participants,
                            sport_name=sport_name,
                            organizer=organizer_name,
                            status=event_status
                        )
                        events.append(event)
                        
                    except Exception as e:
                        logger.warning(f"Ошибка обработки события: {e}")
                        continue
                
                logger.info(f"Получено {len(events)} событий для места {place_id}")
                return events
            else:
                logger.error(f"Ошибка получения событий: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при получении событий: {e}")
            return []
    
    def filter_places_by_sport(self, places: List[Place], sport_id: int) -> List[Place]:
        """
        Фильтрация заведений по виду спорта
        Возвращает отфильтрованный список заведений
        """
        filtered_places = [place for place in places if place.type_id == sport_id]
        logger.info(f"Отфильтровано {len(filtered_places)} заведений для спорта {sport_id}")
        return filtered_places 