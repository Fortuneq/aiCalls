# AI Автоматизация Анализа Звонков

Точное воспроизведение n8n workflow для автоматизации анализа звонков с помощью Python.

## Описание

Система автоматически:
1. Мониторит папку Google Drive на новые аудиофайлы
2. Скачивает и транскрибирует аудио через OpenAI Whisper
3. Размечает роли участников диалога (продавец/клиент)
4. Проводит детальный AI анализ:
   - Анализ этапов продажного процесса
   - Оценка по чеклисту критериев качества
5. Сохраняет результаты в Google Sheets

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте Google API:
   - Создайте проект в Google Cloud Console
   - Включите Google Drive API и Google Sheets API
   - Создайте Service Account и скачайте JSON ключ
   - Предоставьте доступ к папке Drive и таблице Sheets

3. Получите OpenAI API ключ

4. Запустите программу для создания config.json:
```bash
python call_automation.py
```

5. Заполните config.json вашими данными:
```json
{
  "openai_api_key": "ваш_openai_ключ",
  "google_credentials_path": "путь_к_service_account.json",
  "google_drive_folder_id": "ID_папки_с_аудио",
  "spreadsheet_id": "ID_Google_таблицы",
  "analysis_sheet_name": "Лист1",
  "checklist_sheet_name": "Входящие Елизавета",
  "manager_names": ["Елизавета"],
  "company_name": "Весткол"
}
```

## Использование

### Мониторинг папки Google Drive
```bash
python call_automation.py
```

### Обработка одного файла
```bash
python call_automation.py путь/к/аудиофайлу.mp3
```

## Структура workflow

1. **Google Drive Trigger** - мониторинг папки каждую минуту
2. **Download file** - скачивание аудиофайла
3. **Transcribe** - транскрибация через OpenAI Whisper
4. **Message a model** - разметка ролей (продавец/клиент)
5. **Параллельный анализ**:
   - **AI Agent1**: детальный анализ продаж
   - **AI Agent2**: анализ по чеклисту
6. **Google Sheets**: сохранение результатов в две таблицы

## Поддерживаемые форматы аудио

- MP3, WAV, M4A, MP4, OGG, WebM

## Анализ включает

### Детальный анализ продаж:
- Резюме разговора
- Оценка установления контакта
- Квалификация клиента
- Выявление потребностей
- Презентация продукта
- Работа с возражениями
- Закрытие сделки
- Вероятность продажи

### Чеклист качества:
- Этап приветствия
- Установление контакта
- Программирование
- Создание потребности
- Презентация
- Работа с сомнениями
- Завершение звонка

## Требования

- Python 3.7+
- OpenAI API ключ
- Google Cloud Service Account
- Доступ к Google Drive и Google Sheets# aiCalls
