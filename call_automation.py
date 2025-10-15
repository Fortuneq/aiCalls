#!/usr/bin/env python3
"""
AI автоматизация анализа звонков
Точное воспроизведение n8n workflow
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from pathlib import Path

import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import gspread
import io


class CallAutomation:
    def __init__(self, config_file: str = "config.json"):
        """Инициализация с конфигурацией"""
        self.config = self.load_config(config_file)
        self.setup_clients()
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Загрузка конфигурации"""
        if not os.path.exists(config_file):
            # Создаем пример конфигурации
            example_config = {
                "openai_api_key": "your_openai_api_key_here",
                "google_credentials_path": "path_to_service_account.json",
                "google_drive_folder_id": "1WX06lWTYYZBdLHngZE9eO37fGQKNKWoX",
                "spreadsheet_id": "15jsmGxHEI1GVjy2w6uhRWrdnXOdFqkp4mMeyVq8hiGk",
                "analysis_sheet_name": "Лист1",
                "checklist_sheet_name": "Входящие Елизавета",
                "manager_names": ["Елизавета"],
                "company_name": "Весткол"
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(example_config, f, indent=2, ensure_ascii=False)
            print(f"Создан пример конфигурации в {config_file}. Заполните его и запустите снова.")
            raise FileNotFoundError(f"Конфигурация не найдена. Создан пример в {config_file}")
            
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def setup_clients(self):
        """Настройка клиентов для API"""
        # OpenAI
        openai.api_key = self.config["openai_api_key"]
        self.openai_client = openai.OpenAI(api_key=self.config["openai_api_key"])
        
        # Google Services
        credentials = service_account.Credentials.from_service_account_file(
            self.config["google_credentials_path"],
            scopes=[
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
        )
        
        self.drive_service = build('drive', 'v3', credentials=credentials)
        self.gc = gspread.authorize(credentials)
        self.spreadsheet = self.gc.open_by_key(self.config["spreadsheet_id"])
        
        # Проверяем доступ
        self.test_access()

    def test_access(self):
        """Проверка доступа к Google Drive и Sheets"""
        print("🔐 Проверяю доступы...")
        
        try:
            # Проверяем доступ к папке Drive
            folder_info = self.drive_service.files().get(
                fileId=self.config["google_drive_folder_id"],
                fields="name,id,permissions"
            ).execute()
            print(f"✅ Доступ к папке Google Drive: {folder_info.get('name', 'Без имени')}")
            
        except Exception as e:
            print(f"❌ Нет доступа к папке Google Drive: {e}")
            print(f"🔧 Предоставьте доступ email: leisansa@clean-outcome-472421-k0.iam.gserviceaccount.com")
            print(f"📁 К папке: https://drive.google.com/drive/folders/{self.config['google_drive_folder_id']}")
            
            # Показываем доступные папки
            self.list_available_folders()
        
        try:
            # Проверяем доступ к таблице
            sheet_info = self.spreadsheet.title
            print(f"✅ Доступ к Google Sheets: {sheet_info}")
            
            # Проверяем доступные листы
            worksheets = self.spreadsheet.worksheets()
            print("📋 Доступные листы:")
            for ws in worksheets:
                print(f"  - {ws.title}")
            
            # Проверяем нужные листы
            analysis_sheet_name = self.config["analysis_sheet_name"]
            checklist_sheet_name = self.config["checklist_sheet_name"]
            
            sheet_names = [ws.title for ws in worksheets]
            if analysis_sheet_name not in sheet_names:
                print(f"⚠️  Лист '{analysis_sheet_name}' не найден")
            if checklist_sheet_name not in sheet_names:
                print(f"⚠️  Лист '{checklist_sheet_name}' не найден")
            
        except Exception as e:
            print(f"❌ Нет доступа к Google Sheets: {e}")
            print(f"🔧 Предоставьте доступ email: leisansa@clean-outcome-472421-k0.iam.gserviceaccount.com")
            print(f"📊 К таблице: https://docs.google.com/spreadsheets/d/{self.config['spreadsheet_id']}")
    
    def list_available_folders(self):
        """Показать все доступные папки"""
        try:
            print("\n📂 Ищу доступные папки...")
            results = self.drive_service.files().list(
                q="mimeType='application/vnd.google-apps.folder'",
                pageSize=20,
                fields="files(id, name, parents)"
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                print("Найденные папки (скопируйте нужный ID в config.json):")
                for folder in folders:
                    print(f"  📁 {folder['name']} | ID: {folder['id']}")
            else:
                print("❌ Нет доступных папок. Создайте папку и предоставьте доступ Service Account.")
                
        except Exception as e:
            print(f"❌ Ошибка при поиске папок: {e}")

    def monitor_drive_folder(self):
        """Мониторинг папки Google Drive на новые файлы"""
        print("Начинаю мониторинг папки Google Drive...")
        print(f"Папка ID: {self.config['google_drive_folder_id']}")
        
        processed_files = set()
        check_count = 0
        
        while True:
            try:
                check_count += 1
                print(f"\n🔍 Проверка #{check_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Получаем список файлов из папки
                results = self.drive_service.files().list(
                    q=f"'{self.config['google_drive_folder_id']}' in parents and trashed=false",
                    orderBy='modifiedTime desc',
                    pageSize=10,
                    fields="files(id, name, modifiedTime, mimeType)"
                ).execute()
                
                files = results.get('files', [])
                print(f"Найдено файлов в папке: {len(files)}")
                
                if files:
                    print("Файлы в папке:")
                    for file in files:
                        status = "✅ ОБРАБОТАН" if file['id'] in processed_files else "🔄 НОВЫЙ"
                        audio_check = "🎵 АУДИО" if self.is_audio_file(file) else "📄 НЕ АУДИО"
                        print(f"  - {file['name']} | {audio_check} | {status}")
                
                new_audio_files = 0
                for file in files:
                    file_id = file['id']
                    
                    # Проверяем, не обрабатывали ли уже этот файл
                    if file_id not in processed_files:
                        # Проверяем, что это аудиофайл
                        if self.is_audio_file(file):
                            print(f"\n🎵 Обнаружен новый аудиофайл: {file['name']}")
                            self.process_audio_file(file)
                            processed_files.add(file_id)
                            new_audio_files += 1
                        else:
                            print(f"⏭️ Пропускаю не аудио файл: {file['name']}")
                            processed_files.add(file_id)  # Добавляем чтобы не проверять снова
                
                if new_audio_files == 0:
                    print("Новых аудиофайлов не найдено")
                
                print(f"⏰ Следующая проверка через 60 секунд...")
                # Ждем перед следующей проверкой (аналог pollTimes: everyMinute)
                time.sleep(60)
                
            except Exception as e:
                print(f"❌ Ошибка при мониторинге: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)
    
    def is_audio_file(self, file: Dict[str, Any]) -> bool:
        """Проверка, является ли файл аудио"""
        audio_types = [
            'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/m4a',
            'audio/mp4', 'audio/ogg', 'audio/webm'
        ]
        return file.get('mimeType', '').startswith('audio/') or \
               any(file.get('name', '').lower().endswith(ext) 
                   for ext in ['.mp3', '.wav', '.m4a', '.mp4', '.ogg', '.webm'])
    
    def process_audio_file(self, file: Dict[str, Any]):
        """Обработка одного аудиофайла - основной workflow"""
        try:
            print(f"Начинаю обработку файла: {file['name']}")
            
            # 1. Скачивание файла (аналог Download file1)
            audio_content = self.download_file(file['id'])
            
            # 2. Транскрибация (аналог Transcribe1)
            transcript = self.transcribe_audio(audio_content, file['name'])
            
            # 3. Разметка ролей (аналог Message a model1)
            labeled_transcript = self.label_speakers(transcript)
            
            # 4. Параллельный анализ
            # AI Agent1 - детальный анализ продаж
            sales_analysis = self.analyze_sales_call(labeled_transcript)
            
            # AI Agent2 - анализ чеклиста
            checklist_analysis = self.analyze_checklist(labeled_transcript)
            
            # 5. Запись результатов в Google Sheets
            self.save_to_sheets(labeled_transcript, sales_analysis, checklist_analysis)
            
            print(f"✅ Файл {file['name']} успешно обработан")
            
        except Exception as e:
            print(f"❌ Ошибка при обработке файла {file['name']}: {e}")
    
    def download_file(self, file_id: str) -> bytes:
        """Скачивание файла из Google Drive"""
        request = self.drive_service.files().get_media(fileId=file_id)
        file_io = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        return file_io.getvalue()
    
    def transcribe_audio(self, audio_content: bytes, filename: str) -> str:
        """Транскрибация аудио через OpenAI"""
        # Сохраняем во временный файл
        temp_path = f"/tmp/{filename}"
        with open(temp_path, 'wb') as f:
            f.write(audio_content)
        
        try:
            with open(temp_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
            return transcript.text
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def label_speakers(self, transcript: str) -> str:
        """Разметка кто говорит в диалоге"""
        prompt = f"""# Обзор
Ты являешься супер экспертом, который специализируется на глубоком анализе записей встреч

Ты получаешь полную транскрибацию звонка в виде сплошного текста. Твоя задача — сохранить весь исходный текст, но разделить его на реплики и явно пометить, где говорит продавец, а где говорит клиент.

# Продавцы компании
Имена Продавцов: {', '.join(self.config['manager_names'])}

# Название компании
{self.config['company_name']}

# Роль
Прочитай транскрибацию и добавь перед каждой репликой соответствующую приписку:
Если говорит продавец, добавь в начале строки "Продавец:".
Если говорит клиент, добавь в начале строки "Клиент:".

Текст не сокращай, структуру не меняй, ничего не удаляй и не переписывай, только добавляй нужные приписки.

#Вывод
Вывод должен быть в таком формате через новую строчку!

Клиент:
Продавец:

# Задача

Твоя задача - корректно и четко распределить роли. Продавец как правило рассказывает про клуб, преимущества. Следи за этим перед распределением. Не должно быть такого, что текст клиента приписывается менеджеру

Текущая дата и время: {datetime.now().strftime('%d-%m-%Y %H:%M')}"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": transcript}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Ошибка при разметке ролей: {e}")
            return transcript
    
    def analyze_sales_call(self, labeled_transcript: str) -> Dict[str, Any]:
        """Детальный анализ продажного звонка"""
        system_prompt = """# Overview
Ты — профессиональный аналитик продаж и коммуникаций, твоя задача — по тексту диалога анализировать эффективность работы менеджера, определять этапы воронки, выявлять потребности клиента и указывать зоны роста.

Тебе надо сформировать следующие переменные. В тексте дается пример того, что надо писать. НЕ ЖАДНИЧАЙ НА ТЕКСТ. ОТВЕЧАЙ ПОДРОБНО И РАЗВЕРНУТО.

Тебе передается реальный диалог между менеджером и клиентом (текст аудио)

# Role

Твоя задача — строго по структуре output (см. ниже) заполнить все поля, даже если какие-то данные отсутствуют — в этом случае пиши "нет данных" или давай максимально вероятный ответ по контексту.

Вся логика должна быть развернута и обоснована — особенно там, где ты выставляешь проценты или даёшь субъективные оценки. Не додумывай имена и факты, если их нет в тексте, но логически интерпретируй смысл сказанного.

Перед анализом внимательно изучи структуру и описание каждого поля.

# Output 

ВОТ ПЕРЕМЕННЫЕ КОТОРЫЕ НУЖНО СФОРМИРОВАТЬ:

"summary" — Краткое резюме разговора (5–15 предложений):
Что обсудили, на чем сделали акцент, каков общий настрой клиента, какой результат по итогу встречи.

"client_talks_most" — Кто говорил больше (да/нет + краткое пояснение). Да/Нет. Объясни, почему: например, клиент активно делился опытом и вопросами или, наоборот, отвечал коротко, а инициативу держал менеджер.

client_name — Имя клиента (по возможности ФИО). Пример: Иванов Иван.

style_adaptation — Адаптация стиля менеджера под клиента (да/нет + пояснение). Да/Нет. Поясни — использовал ли менеджер лексику и темп, близкий клиенту, подстраивался ли под его энергетику. 5-8 предложений с цитатами

target_client — Целевой ли клиент для клуба. Да/Нет. Владелец агентства, есть запрос на рост и развитие.

client_needs — Основные потребности и мотивация клиента.Зачем в клуб, чего ожидает, какой результат хочет получить. 5-8 предложений с цитатами

contact_establishment.value — Оценка установления контакта (0–100).  Насколько успешно менеджер установил контакт: был ли смолток, удалось ли расположить клиента, плавность перехода к делу.

contact_establishment.explanation — Пояснение по установлению контакта. Как прошел первый этап, были ли барьеры, насколько быстро удалось перейти к сути. 5-8 предложений с цитатами

qualification.value — Квалификация клиента (0–100). Насколько глубоко выяснили, кто клиент, его контекст, источник знакомства с клубом, мотивацию на данном этапе.

qualification.explanation — Пояснение по квалификации. Какие вопросы были заданы, насколько полно менеджер раскрыл контекст и мотивацию клиента. 5-8 предложений с цитатами

needs_identification.value — Оценка выявления потребностей (0–100). Насколько четко и глубоко выявлены реальные потребности и цели клиента.

needs_identification.explanation — Пояснение по выявлению потребностей. Какие запросы и задачи клиента были зафиксированы, насколько полно менеджер понял ожидания. 5-8 предложений с цитатами


product_presentation.value — Оценка презентации продукта (0–100). Насколько презентация продукта была адаптирована под задачи клиента.

product_presentation.explanation — Пояснение по презентации. Какие выгоды и решения были показаны, насколько персонализированно менеджер рассказывал о клубе. 5-8 предложений с цитатами

objection_handling.value — Оценка работы с возражениями (0–100). Как менеджер работал с возражениями, насколько эффективно снял опасения клиента.

objection_handling.explanation — Пояснение по работе с возражениями. Какие вопросы или возражения звучали, как менеджер их закрыл. 5-8 предложений с цитатами

hidden_objections — Скрытые возражения, которые не были отработаны. Запиши неочевидные опасения, которые могли остаться. 5-8 предложений с цитатами


closing.value — Оценка закрытия сделки (0–100). Была ли попытка закрытия (например, предложен ван-тайм оффер), насколько корректно и уверенно.

closing.explanation — Пояснение по закрытию сделки. Что именно предложил менеджер, как отреагировал клиент, было ли согласие или нет. 5-8 предложений с цитатами

sale_probability.value — Вероятность продажи (0–100). Твоя субъективная оценка, насколько клиент готов купить.

sale_probability.explanation — Краткое объяснение вероятности продажи. Что говорит за и против, какие сигналы дал клиент. 5-8 предложений с цитатами


next_step — Следующий шаг после встречи. Что согласовали, какие действия стоит сделать менеджеру дальше, чтобы не терять динамику.

В ответ иногда включай цитаты из ответов"""

        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "client_talks_most": {"type": "string"},
                "client_name": {"type": "string"},
                "style_adaptation": {"type": "string"},
                "target_client": {"type": "string"},
                "client_needs": {"type": "string"},
                "contact_establishment": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "qualification": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "needs_identification": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "product_presentation": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "objection_handling": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "hidden_objections": {"type": "string"},
                "closing": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "sale_probability": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "explanation": {"type": "string"}
                    }
                },
                "next_step": {"type": "string"}
            }
        }

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Текст аудио: {labeled_transcript}"}
                ],
                response_format={"type": "json_schema", "json_schema": {"name": "sales_analysis", "schema": schema}}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Ошибка при анализе продаж: {e}")
            return {}
    
    def analyze_checklist(self, labeled_transcript: str) -> Dict[str, Any]:
        """Анализ по чеклисту критериев"""
        system_prompt = """# Overview
Ты — эксперт по контролю качества звонков.  
У тебя есть транскрибация звонка.  
Твоя задача:
1. Определить — звонок входящий (клиент позвонил в компанию) или исходящий (продавец звонит клиенту).  
2. Выставить оценку по каждому чеклист-пункту.  
3. Вернуть иерархический JSON в точности по структуре таблицы.  

# Rules
- Формат ответа: строго JSON-объект.  
- В ответе ДОЛЖЕН быть только один JSON-объект.  
- Никакого текста, пояснений или комментариев.  
- Для каждого чеклист-пункта укажи число:  
  - `1` — пункт выполнен явно  
  - `0.5` — выполнен частично  
  - `0` — не выполнен  
- Если информации нет — ставь `0`.  
- В каждом блоке добавляй поле `"Итого"`, где суммируешь все значения этого блока (кроме самого Итого).  
- В конце добавь `"ВСЕГО"`, где сумма всех Итого блоков.  
- Обязательно добавь поле `"Тип звонка"` со значением `"Входящий"` или `"Исходящий"`.  

# Output
Верни только JSON в этом формате.  
Без текста, пояснений или схемы."""

        schema = {
            "type": "object",
            "properties": {
                "Тип звонка": {"type": "string"},
                "Этап ПРИВЕТСТВИЕ": {
                    "type": "object",
                    "properties": {
                        "Время до соединения с менеджером": {"type": "number"},
                        "Корпоративное приветсвие": {"type": "number"},
                        "Тон добродушный, приветливый, есть улыбка в голосе": {"type": "number"},
                        "Не тараторит, не съедает слова": {"type": "number"},
                        "Озвучивает цель звонка\\ инфоповод": {"type": "number"},
                        "Не использует фразу 'вам удобно разговаривать'": {"type": "number"},
                        "Не использует фразу 'как к вам можно обращаться'": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "Этап УСТАНОВЛЕНИЕ КОНТАКТА": {
                    "type": "object",
                    "properties": {
                        "Обращается по имени, минимум 2 раза": {"type": "number"},
                        "Не перебивает, дослушивает до конца": {"type": "number"},
                        "Говорит на простом понятном языке": {"type": "number"},
                        "Отсутствует сухой формальный тон": {"type": "number"},
                        "Общается на 'равных'": {"type": "number"},
                        "Использует приемы Small talk": {"type": "number"},
                        "Говорит комплимент, похвалу": {"type": "number"},
                        "Использует юмор": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "Этап ПРОГРАММИРОВАНИЯ": {
                    "type": "object",
                    "properties": {
                        "Использует программирование в начале разговора": {"type": "number"},
                        "На протяжении всего диалога менеджер 'ведет'": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "Этап СОЗДАНИЯ ПОТРЕБНОСТИ": {
                    "type": "object",
                    "properties": {
                        "Задал обязательные вопросы": {"type": "number"},
                        "Делает презентацию компании": {"type": "number"},
                        "Не говорит 'Мы оператор/провайдер интернет услуг'": {"type": "number"},
                        "Выясняет чем занимается компания": {"type": "number"},
                        "Выясняет подключена ли услуга интернет": {"type": "number"},
                        "Если все устраивает, узнает про резервный канал": {"type": "number"},
                        "Узнает о случаях атак": {"type": "number"},
                        "Задает вопросы про доп. услуги": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "Этап ПРЕЗЕНТАЦИЯ": {
                    "type": "object",
                    "properties": {
                        "Делает презентацию 2-3 услуг": {"type": "number"},
                        "Рассказывает о кейсах или отзывах": {"type": "number"},
                        "Предлагает отправить КП или тестовый период": {"type": "number"},
                        "Менеджер знает продукт": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "Этап РАБОТА С СОМНЕНИЯМИ": {
                    "type": "object",
                    "properties": {
                        "Отрабатывает все возражения": {"type": "number"},
                        "Присоединяется при отработке возражений": {"type": "number"},
                        "Аргументы соответствуют возражению": {"type": "number"},
                        "Не спорит с клиентом": {"type": "number"},
                        "Предлагает отправить КП после отработки": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "ЭТАП ЗАВЕРШЕНИЯ": {
                    "type": "object",
                    "properties": {
                        "Уточняет остались ли вопросы": {"type": "number"},
                        "Уточняет куда отправить КП": {"type": "number"},
                        "Спросить к какой дате нужна услуга": {"type": "number"},
                        "Резюмировал разговор": {"type": "number"},
                        "Озвучивает следующие шаги": {"type": "number"},
                        "Оставил контакты и поблагодарил": {"type": "number"},
                        "Итого": {"type": "number"}
                    }
                },
                "ВСЕГО": {"type": "number"}
            }
        }

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Текст аудио: {labeled_transcript}"}
                ],
                response_format={"type": "json_schema", "json_schema": {"name": "checklist_analysis", "schema": schema}}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Ошибка при анализе чеклиста: {e}")
            return {}
    
    def save_to_sheets(self, transcript: str, sales_analysis: Dict[str, Any], checklist_analysis: Dict[str, Any]):
        """Сохранение результатов в Google Sheets"""
        current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
        
        # Сохраняем в лист анализа продаж - ТОЧНЫЙ порядок как в n8n
        try:
            analysis_sheet = self.spreadsheet.worksheet(self.config["analysis_sheet_name"])
            analysis_row = [
                current_time,  # Дата и время
                sales_analysis.get("summary", ""),  # Резюме разговора (коротко)
                transcript,  # Транскрибация звонка
                sales_analysis.get("client_talks_most", ""),  # Преимущественно говорит клиент
                sales_analysis.get("style_adaptation", ""),  # Адаптация под стиль и речь клиента
                sales_analysis.get("client_name", ""),  # Имя клиента
                sales_analysis.get("target_client", ""),  # Целевой клиент
                sales_analysis.get("client_needs", ""),  # Потребности
                sales_analysis.get("contact_establishment", {}).get("value", ""),  # Установление контакта (в том числе смол ток)
                sales_analysis.get("contact_establishment", {}).get("explanation", ""),  # Объяснение оценки - контакт
                sales_analysis.get("qualification", {}).get("value", ""),  # Квалификация 
                sales_analysis.get("qualification", {}).get("explanation", ""),  # Объяснение оценки - квалификация
                sales_analysis.get("needs_identification", {}).get("value", ""),  # Выявление потребности
                sales_analysis.get("needs_identification", {}).get("explanation", ""),  # Объяснение оценки - потребность
                sales_analysis.get("product_presentation", {}).get("value", ""),  # Презентация продукта / услуги
                sales_analysis.get("product_presentation", {}).get("explanation", ""),  # Объяснение оценки - презентация
                sales_analysis.get("objection_handling", {}).get("value", ""),  # Отработка возражения
                sales_analysis.get("objection_handling", {}).get("explanation", ""),  # Объяснение оценки - возражения
                sales_analysis.get("hidden_objections", ""),  # Скрытые возражения, которые не закрыты
                sales_analysis.get("closing", {}).get("value", ""),  # Закрытие
                sales_analysis.get("closing", {}).get("explanation", ""),  # Объяснение оценки - закрытие
                sales_analysis.get("sale_probability", {}).get("value", ""),  # Вероятность продажи
                sales_analysis.get("sale_probability", {}).get("explanation", ""),  # Объяснение оценки - вероятность продажи
                sales_analysis.get("next_step", "")  # Следующий шаг
            ]
            analysis_sheet.append_row(analysis_row)
            print("✅ Данные анализа продаж сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения анализа продаж: {e}")
        
        # Сохраняем в лист чеклиста - ТОЧНЫЙ порядок как в n8n
        try:
            checklist_sheet = self.spreadsheet.worksheet(self.config["checklist_sheet_name"])
            
            # Формируем строку для чеклиста - правильный порядок полей
            checklist_row = [
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Время до соединения с менеджером", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Корпоративное приветсвие", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Тон добродушный, приветливый, есть улыбка в голосе", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Не тараторит, не съедает слова", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Озвучивает цель звонка\\ инфоповод", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Не использует фразу 'вам удобно разговаривать'", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Не использует фразу 'как к вам можно обращаться'", ""),
                checklist_analysis.get("Этап ПРИВЕТСТВИЕ", {}).get("Итого", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Обращается по имени, минимум 2 раза", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Не перебивает, дослушивает до конца", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Говорит на простом понятном языке", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Отсутствует сухой формальный тон", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Общается на 'равных'", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Использует приемы Small talk", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Говорит комплимент, похвалу", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Использует юмор", ""),
                checklist_analysis.get("Этап УСТАНОВЛЕНИЕ КОНТАКТА", {}).get("Итого", ""),
                checklist_analysis.get("Этап ПРОГРАММИРОВАНИЯ", {}).get("Использует программирование в начале разговора", ""),
                checklist_analysis.get("Этап ПРОГРАММИРОВАНИЯ", {}).get("На протяжении всего диалога менеджер 'ведет'", ""),
                checklist_analysis.get("Этап ПРОГРАММИРОВАНИЯ", {}).get("Итого", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Задал обязательные вопросы", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Делает презентацию компании", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Не говорит 'Мы оператор/провайдер интернет услуг'", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Выясняет чем занимается компания", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Выясняет подключена ли услуга интернет", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Если все устраивает, узнает про резервный канал", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Узнает о случаях атак", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Задает вопросы про доп. услуги", ""),
                checklist_analysis.get("Этап СОЗДАНИЯ ПОТРЕБНОСТИ", {}).get("Итого", ""),
                checklist_analysis.get("Этап ПРЕЗЕНТАЦИЯ", {}).get("Делает презентацию 2-3 услуг", ""),
                checklist_analysis.get("Этап ПРЕЗЕНТАЦИЯ", {}).get("Рассказывает о кейсах или отзывах", ""),
                checklist_analysis.get("Этап ПРЕЗЕНТАЦИЯ", {}).get("Предлагает отправить КП или тестовый период", ""),
                checklist_analysis.get("Этап ПРЕЗЕНТАЦИЯ", {}).get("Менеджер знает продукт", ""),
                checklist_analysis.get("Этап ПРЕЗЕНТАЦИЯ", {}).get("Итого", ""),
                checklist_analysis.get("Этап РАБОТА С СОМНЕНИЯМИ", {}).get("Отрабатывает все возражения", ""),
                checklist_analysis.get("Этап РАБОТА С СОМНЕНИЯМИ", {}).get("Присоединяется при отработке возражений", ""),
                checklist_analysis.get("Этап РАБОТА С СОМНЕНИЯМИ", {}).get("Аргументы соответствуют возражению", ""),
                checklist_analysis.get("Этап РАБОТА С СОМНЕНИЯМИ", {}).get("Не спорит с клиентом", ""),
                checklist_analysis.get("Этап РАБОТА С СОМНЕНИЯМИ", {}).get("Предлагает отправить КП после отработки", ""),
                checklist_analysis.get("Этап РАБОТА С СОМНЕНИЯМИ", {}).get("Итого", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Уточняет остались ли вопросы", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Уточняет куда отправить КП", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Спросить к какой дате нужна услуга", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Резюмировал разговор", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Озвучивает следующие шаги", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Оставил контакты и поблагодарил", ""),
                checklist_analysis.get("ЭТАП ЗАВЕРШЕНИЯ", {}).get("Итого", ""),
                checklist_analysis.get("ВСЕГО", ""),
                transcript  # Транскрибация
            ]
            
            checklist_sheet.append_row(checklist_row)
            print("✅ Данные чеклиста сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения чеклиста: {e}")

    def process_single_file(self, file_path: str):
        """Обработка одного локального файла (для тестирования)"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        print(f"Обрабатываю файл: {file_path}")
        
        # Читаем файл
        with open(file_path, 'rb') as f:
            audio_content = f.read()
        
        filename = os.path.basename(file_path)
        
        # Транскрибация
        transcript = self.transcribe_audio(audio_content, filename)
        print("✅ Транскрибация завершена")
        
        # Разметка ролей
        labeled_transcript = self.label_speakers(transcript)
        print("✅ Разметка ролей завершена")
        
        # Анализ
        sales_analysis = self.analyze_sales_call(labeled_transcript)
        print("✅ Анализ продаж завершен")
        
        checklist_analysis = self.analyze_checklist(labeled_transcript)
        print("✅ Анализ чеклиста завершен")
        
        # Сохранение
        self.save_to_sheets(labeled_transcript, sales_analysis, checklist_analysis)
        print("✅ Результаты сохранены в Google Sheets")


def main():
    """Основная функция"""
    import sys
    import traceback
    
    try:
        automation = CallAutomation()
        
        if len(sys.argv) > 1:
            # Обработка конкретного файла
            file_path = sys.argv[1]
            automation.process_single_file(file_path)
        else:
            # Мониторинг папки
            automation.monitor_drive_folder()
            
    except FileNotFoundError as e:
        print(f"Ошибка конфигурации: {e}")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        print(f"Подробности:")
        traceback.print_exc()


if __name__ == "__main__":
    main()