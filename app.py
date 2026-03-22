import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import os
import requests
from io import BytesIO
import hashlib
import tempfile
import re
import sys

# === ОТЛАДКА ===
class StreamToLogger:
    def __init__(self):
        self.logs = []
    def write(self, message):
        if message.strip():
            self.logs.append(message.strip())
    def flush(self):
        pass

logger = StreamToLogger()
sys.stderr = logger
sys.stdout = logger

def debug_print(*args):
    message = " ".join(str(a) for a in args)
    logger.write(message)

# --- Настройка страницы (мобильная) ---
st.set_page_config(
    page_title="DocControl Mobile",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .stButton > button {
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .metric-card {
        background: var(--background-color);
        border-radius: 16px;
        padding: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid var(--border-color);
        text-align: center;
    }
    
    .metric-card div:first-child {
        font-size: 28px;
        font-weight: 700;
        color: var(--text-color);
    }
    
    .metric-card div:last-child {
        font-size: 14px;
        color: var(--text-color-secondary);
    }
    
    .user-info {
        background: var(--background-color);
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 12px;
        text-align: center;
        border: 1px solid var(--border-color);
        font-size: 14px;
        line-height: 1.5;
    }
    
    .user-info strong {
        color: var(--primary-color);
    }
    
    @media (max-width: 768px) {
        .metric-card div:first-child {
            font-size: 24px !important;
        }
        .stButton > button {
            font-size: 14px;
            padding: 8px 12px;
        }
    }
    
    [data-testid="stSidebar"] {
        display: none;
    }
    [data-testid="collapsedControl"] {
        display: none;
    }
    .main > div {
        padding-top: 0.5rem;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ==================== КОНФИГУРАЦИЯ ====================
YANDEX_TOKEN = "y0__xCSoI7HARiCoj8gmJWg6RYwg7TKiggf83bV1Q-ufqbt9dsQa23N7Xe2bQ"
YANDEX_FILE_PATH = "/doc_control/control_system.db"

def check_internet():
    try:
        requests.get("https://cloud-api.yandex.net", timeout=5)
        return True
    except:
        return False

def create_folder_if_not_exists():
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    params = {"path": "/doc_control"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            response = requests.put(url, headers=headers, params=params, timeout=10)
            return response.status_code == 201
        return False
    except Exception as e:
        return False

def download_from_yandex():
    url = "https://cloud-api.yandex.net/v1/disk/resources/download"
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    try:
        params = {"path": YANDEX_FILE_PATH}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            download_url = response.json()["href"]
            file_response = requests.get(download_url, timeout=30)
            if file_response.status_code == 200:
                with open("control_system.db", "wb") as f:
                    f.write(file_response.content)
                return True
        elif response.status_code == 404:
            return True
        return False
    except Exception as e:
        return False

def upload_to_yandex():
    if not os.path.exists("control_system.db"):
        return False
    if not create_folder_if_not_exists():
        return False
    url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    try:
        params = {"path": YANDEX_FILE_PATH, "overwrite": "true"}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            upload_url = response.json()["href"]
            with open("control_system.db", "rb") as f:
                file_response = requests.put(upload_url, data=f, timeout=30)
            return file_response.status_code in [200, 201]
        return False
    except Exception as e:
        return False

def sync_to_cloud():
    if not check_internet():
        return False, "Нет интернета"
    if upload_to_yandex():
        return True, "Синхронизация выполнена"
    return False, "Ошибка синхронизации"

def download_from_cloud():
    if not check_internet():
        return False, "Нет интернета"
    if download_from_yandex():
        return True, "База обновлена"
    return False, "Ошибка загрузки"

# --- Функции для работы с БД ---
def normalize_fio(fio):
    parts = fio.strip().split()
    normalized_parts = []
    for part in parts:
        if part:
            normalized_parts.append(part[0].upper() + part[1:].lower())
    return " ".join(normalized_parts)

def transliterate(text):
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    result = ''
    for char in text.lower():
        if char in translit_map:
            result += translit_map[char]
        elif char.isalpha():
            result += char
    return result

def generate_login(conn, fio):
    parts = fio.strip().split()
    if len(parts) < 3:
        return None
    surname, name, patronymic = parts[0], parts[1], parts[2]
    surname_lat = transliterate(surname)
    name_lat = transliterate(name)
    patronymic_lat = transliterate(patronymic)
    name_initial = name_lat[0] if name_lat else ''
    patronymic_initial = patronymic_lat[0] if patronymic_lat else ''
    base_login = f"{surname_lat}_{name_initial}{patronymic_initial}"
    c = conn.cursor()
    existing = c.execute("SELECT login FROM staff WHERE login LIKE ?", (f"{base_login}%",)).fetchall()
    if not existing:
        return base_login
    numbers = []
    for login in existing:
        if login[0] == base_login:
            numbers.append(0)
        elif login[0].startswith(base_login):
            try:
                num = int(login[0][len(base_login):])
                numbers.append(num)
            except:
                pass
    max_num = max(numbers) if numbers else 0
    new_num = max_num + 1
    return base_login if new_num == 0 else f"{base_login}{new_num}"

def hash_pin(pin):
    return hashlib.sha256(str(pin).encode()).hexdigest()

def create_admin_if_not_exists(conn):
    c = conn.cursor()
    admin = c.execute("SELECT id FROM staff WHERE login = 'admin3452'").fetchone()
    if not admin:
        admin_pin_hash = hash_pin("6799")
        c.execute("INSERT INTO staff (fio, login, department, is_user) VALUES (?, ?, ?, ?)",
                  ("Администратор", "admin3452", "Администрация", 1))
        admin_id = c.lastrowid
        c.execute("INSERT INTO users (user_id, pin_code, created_at) VALUES (?, ?, ?)",
                  (admin_id, admin_pin_hash, datetime.now().date()))
        conn.commit()

def init_db():
    local_db_path = "control_system.db"
    if os.path.exists(local_db_path):
        conn = sqlite3.connect(local_db_path, check_same_thread=False)
        create_admin_if_not_exists(conn)
        return conn
    
    conn = sqlite3.connect(local_db_path, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fio TEXT,
        login TEXT UNIQUE,
        department TEXT,
        is_user INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pin_code TEXT,
        created_at DATE,
        FOREIGN KEY (user_id) REFERENCES staff(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS doc_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        doc_type TEXT,
        doc_number TEXT,
        reg_date DATE,
        sender TEXT,
        summary TEXT,
        with_who_login TEXT,
        with_who_fio TEXT,
        transfer_date DATE,
        deadline DATE,
        status TEXT DEFAULT 'В работе',
        status_history TEXT,
        comment TEXT,
        priority INTEGER DEFAULT 0,
        starred INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    conn.commit()
    
    initial_doc_types = [
        "КУСП", "Обращение", "Служебная проверка", "Представление",
        "Указание", "Уголовное дело", "Поручение", "Рапорт",
        "Докладная записка", "Протокол", "Требование", "Запрос",
        "Справка", "Информация"
    ]
    for dt in initial_doc_types:
        c.execute("INSERT OR IGNORE INTO doc_types (name) VALUES (?)", (dt,))
    
    initial_departments = [
        "ДЧ УМВД России по Тюменской области", "ИЦ УМВД России по Тюменской области",
        "КРО УМВД России по Тюменской области", "ОРЧ ГЗ УМВД России по Тюменской области",
        "ОРЧ СБ УМВД России по Тюменской области", "УДиР УМВД России по Тюменской области",
        "ОИиОС УМВД России по Тюменской области", "ООД УМВД России по Тюменской области",
        "ЦФО УМВД России по Тюменской области", "ПО УМВД России по Тюменской области",
        "СУ УМВД России по Тюменской области", "СЧ СУ УМВД России по Тюменской области",
        "Тыл УМВД России по Тюменской области", "УГИБДД УМВД России по Тюменской области",
        "УОООП УМВД России по Тюменской области", "УРЛС УМВД России по Тюменской области",
        "УУР УМВД России по Тюменской области", "УЭБиПК УМВД России по Тюменской области",
        "УНК УМВД России по Тюменской области", "УВМ УМВД России по Тюменской области",
        "УОДУУПиПДН УМВД России по Тюменской области", "ЦКС УМВД России по Тюменской области",
        "ЦПЭ УМВД России по Тюменской области", "ЦИТСиЗИ УМВД России по Тюменской области",
        "Штаб УМВД России по Тюменской области", "ЭКЦ УМВД России по Тюменской области",
        "ОО УМВД России по Тюменской области", "ФКУ \"ЦХ и СО УМВД России по Тюменской области\"",
        "ОНЦБ Интерпола УМВД России по Тюменской области", "МО ГИБДД РЭР и ТН АМТС УМВД России по Тюменской области",
        "УМВД России по г.Тюмени", "ДЧ УМВД России по г. Тюмени", "ОДиР УМВД России по г. Тюмени",
        "ОД УМВД России по г. Тюмени", "ПО УМВД России по г. Тюмени", "СЧ СУ УМВД России по г. Тюмени",
        "Тыл УМВД России по г. Тюмени", "ОГИБДД УМВД России по г. Тюмени", "ОО УМВД России по г. Тюмени",
        "ОУР УМВД России по г. Тюмени", "ОЭБиПК УМВД России по г. Тюмени", "ОУУПиПДН УМВД России по г. Тюмени",
        "ОБ ППСП УМВД России по г. Тюмени", "ОБ ОКПО УМВД России по г. Тюмени", "ОРЛС УМВД России по г. Тюмени",
        "СУ УМВД России по г.Тюмени", "ОВМ УМВД России по г.Тюмени",
        "ОП № 1 УМВД России по г.Тюмени", "ОП № 2 УМВД России по г.Тюмени",
        "ОП № 3 УМВД России по г.Тюмени", "ОП № 4 УМВД России по г.Тюмени",
        "ОП № 5 УМВД России по г.Тюмени", "ОП № 6 УМВД России по г.Тюмени",
        "ОП № 7 УМВД России по г.Тюмени", "ОП № 8 УМВД России по г.Тюмени",
        "МО МВД России «Голышмановский»", "МО МВД России «Заводоуковский»",
        "МО МВД России «Ишимский»", "МО МВД России «Омутинский»",
        "МО МВД России «Тобольский»", "МО МВД России «Тюменский»",
        "МО МВД России «Ялуторовский»", "Отделение МВД России по Казанскому району",
        "Отдел МВД России по Уватскому району", "МВД России", "ГУСБ МВД России",
        "ГУРЛС МВД России", "ГУТ МВД России", "ГУУР МВД России",
        "ГУЭБиПК МВД России", "ГУНК МВД России", "ГУВМ МВД России"
    ]
    for dept in initial_departments:
        c.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)", (dept,))
    
    conn.commit()
    create_admin_if_not_exists(conn)
    return conn

conn = init_db()

def get_doc_types():
    types = conn.execute("SELECT name FROM doc_types ORDER BY name").fetchall()
    return [t[0] for t in types]

def add_doc_type(doc_type_name):
    if doc_type_name and doc_type_name.strip():
        try:
            conn.execute("INSERT OR IGNORE INTO doc_types (name) VALUES (?)", (doc_type_name.strip(),))
            conn.commit()
            return True
        except:
            return False
    return False

def register_user(login, fio, department, pin):
    c = conn.cursor()
    pin_hash = hash_pin(pin)
    try:
        existing = c.execute("SELECT id FROM staff WHERE login = ?", (login,)).fetchone()
        if existing:
            return None, "Логин уже существует"
        c.execute("INSERT INTO staff (fio, login, department, is_user) VALUES (?, ?, ?, 1)", (fio, login, department))
        staff_id = c.lastrowid
        c.execute("INSERT INTO users (user_id, pin_code, created_at) VALUES (?, ?, ?)", (staff_id, pin_hash, datetime.now().date()))
        c.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)", (department,))
        conn.commit()
        return staff_id, None
    except Exception as e:
        return None, str(e)

def verify_user(login, pin):
    c = conn.cursor()
    pin_hash = hash_pin(pin)
    result = c.execute("""
        SELECT s.id, s.fio, s.login, s.department 
        FROM staff s
        JOIN users u ON s.id = u.user_id
        WHERE s.login = ? AND u.pin_code = ?
    """, (login, pin_hash)).fetchone()
    if result:
        return result[0], result[1], result[2], result[3]
    return None, None, None, None

def get_staff_list():
    staff = conn.execute("""
        SELECT fio, login, department, is_user 
        FROM staff 
        WHERE login != 'admin3452'
        ORDER BY fio, department
    """).fetchall()
    result = []
    for fio, login, dept, is_user in staff:
        fio_parts = fio.split()
        if len(fio_parts) >= 3:
            display_name = f"{fio_parts[0]} {fio_parts[1][0]}.{fio_parts[2][0]}."
        elif len(fio_parts) == 2:
            display_name = f"{fio_parts[0]} {fio_parts[1][0]}."
        else:
            display_name = fio
        display = f"{display_name} ({dept})"
        result.append({'display': display, 'login': login, 'fio': fio, 'department': dept, 'is_user': is_user})
    return result

def get_departments():
    depts = conn.execute("SELECT name FROM departments ORDER BY name").fetchall()
    return [d[0] for d in depts]

def add_department(dept_name):
    if dept_name and dept_name.strip():
        try:
            conn.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)", (dept_name.strip(),))
            conn.commit()
            return True
        except:
            return False
    return False

def get_user_docs(user_id, user_login):
    """Получает документы, где пользователь является владельцем ИЛИ исполнителем"""
    query = """
        SELECT d.*, s.fio as executor_fio, s.department as executor_dept
        FROM docs d
        LEFT JOIN staff s ON d.with_who_login = s.login
        WHERE d.user_id = ? OR d.with_who_login = ?
        ORDER BY d.starred DESC, d.deadline ASC, d.reg_date DESC
    """
    debug_print(f"[DEBUG] get_user_docs: user_id={user_id}, user_login={user_login}")
    result = pd.read_sql(query, conn, params=(user_id, user_login))
    debug_print(f"[DEBUG] Найдено документов: {len(result)}")
    return result

def add_document(user_id, doc_type, doc_number, reg_date, sender, summary, 
                 with_who_login, with_who_fio, deadline, comment, starred):
    c = conn.cursor()
    deadline_value = deadline if deadline else None
    c.execute("""
        INSERT INTO docs 
        (user_id, doc_type, doc_number, reg_date, sender, summary, 
         with_who_login, with_who_fio, transfer_date, deadline, status, status_history, comment, starred)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user_id, doc_type, doc_number, reg_date, sender, summary,
          with_who_login, with_who_fio, datetime.now().date(), deadline_value, 
          "В работе", "", comment, 1 if starred else 0))
    conn.commit()
    debug_print(f"[DEBUG] Добавлен документ: user_id={user_id}, with_who_login={with_who_login}, with_who_fio={with_who_fio}")

def update_document(doc_id, user_id, doc_number, sender, summary, 
                    with_who_login, with_who_fio, deadline, comment, starred):
    c = conn.cursor()
    deadline_value = deadline if deadline else None
    c.execute("""
        UPDATE docs SET 
        doc_number=?, sender=?, summary=?, with_who_login=?, with_who_fio=?,
        deadline=?, comment=?, starred=?
        WHERE id=? AND user_id=?
    """, (doc_number, sender, summary, with_who_login, with_who_fio,
          deadline_value, comment, 1 if starred else 0, doc_id, user_id))
    conn.commit()
    debug_print(f"[DEBUG] Обновлен документ {doc_id}: with_who_login={with_who_login}, with_who_fio={with_who_fio}")

def update_status(doc_id, user_id, new_status, comment="", new_with_who_login=None, new_with_who_fio=None):
    c = conn.cursor()
    doc = c.execute("SELECT status, status_history FROM docs WHERE id=? AND user_id=?", (doc_id, user_id)).fetchone()
    if not doc:
        return
    old_status = doc[0]
    history = doc[1] if doc[1] else ""
    now = datetime.now()
    timestamp = now.strftime('%d.%m.%Y %H:%M:%S')
    new_entry = f"{timestamp}: {old_status} → {new_status}"
    if new_status == "Передан" and new_with_who_fio:
        new_entry += f" (передан {new_with_who_fio})"
        debug_print(f"[DEBUG] Передача документа {doc_id}: новому исполнителю {new_with_who_fio} (логин: {new_with_who_login})")
    elif comment:
        new_entry += f" ({comment})"
    updated_history = f"{history}\n{new_entry}".strip()
    
    if new_with_who_login:
        c.execute("""
            UPDATE docs SET 
            status=?, status_history=?, transfer_date=?, 
            with_who_login=?, with_who_fio=?
            WHERE id=? AND user_id=?
        """, (new_status, updated_history, now.date(), new_with_who_login, new_with_who_fio, doc_id, user_id))
        debug_print(f"[DEBUG] Обновлен статус документа {doc_id}: новый статус={new_status}, исполнитель={new_with_who_fio}")
    else:
        c.execute("""
            UPDATE docs SET 
            status=?, status_history=?, transfer_date=?
            WHERE id=? AND user_id=?
        """, (new_status, updated_history, now.date(), doc_id, user_id))
    conn.commit()

def toggle_star(doc_id, user_id):
    current = conn.execute("SELECT starred FROM docs WHERE id=? AND user_id=?", (doc_id, user_id)).fetchone()
    if current:
        new_value = 1 if current[0] == 0 else 0
        conn.execute("UPDATE docs SET starred=? WHERE id=? AND user_id=?", (new_value, doc_id, user_id))
        conn.commit()

# --- Сессия ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_fio' not in st.session_state:
    st.session_state.user_fio = None
if 'user_login' not in st.session_state:
    st.session_state.user_login = None
if 'user_dept' not in st.session_state:
    st.session_state.user_dept = None
if 'selected_doc_id' not in st.session_state:
    st.session_state.selected_doc_id = None
if 'quick_filter' not in st.session_state:
    st.session_state.quick_filter = 'all'
if 'show_login_message' not in st.session_state:
    st.session_state.show_login_message = False
if 'temp_login' not in st.session_state:
    st.session_state.temp_login = None
if 'show_debug' not in st.session_state:
    st.session_state.show_debug = False

# ==================== ЭКРАН ВХОДА / РЕГИСТРАЦИИ ====================
if st.session_state.user_id is None:
    st.title("📱 DocControl Mobile")
    
    if st.session_state.show_login_message and st.session_state.temp_login:
        st.success(f"✅ Регистрация успешна! Ваш логин: **{st.session_state.temp_login}**")
        st.info("Сохраните этот логин для входа!")
        st.session_state.show_login_message = False
    
    mode = st.radio(
        "Выберите действие",
        ["🔐 Вход", "📝 Регистрация"],
        horizontal=True
    )
    
    if mode == "🔐 Вход":
        col1, col2 = st.columns([1, 1])
        with col1:
            login = st.text_input("Логин", placeholder="ivanov_ii")
            pin = st.text_input("PIN-код", type="password", max_chars=4)
            if st.button("Войти", type="primary", use_container_width=True):
                if login and pin and len(pin) == 4 and pin.isdigit():
                    user_id, fio, user_login, dept = verify_user(login, pin)
                    if user_id:
                        st.session_state.user_id = user_id
                        st.session_state.user_fio = fio
                        st.session_state.user_login = user_login
                        st.session_state.user_dept = dept
                        st.success(f"Добро пожаловать!")
                        st.rerun()
                    else:
                        st.error("Неверный логин или PIN-код")
                else:
                    st.error("PIN-код должен быть 4 цифры")
        with col2:
            st.info("ℹ️ Логин формируется автоматически из ФИО")
    
    else:
        st.markdown("### Регистрация")
        col1, col2 = st.columns(2)
        with col1:
            last_name = st.text_input("Фамилия")
            first_name = st.text_input("Имя")
            patronymic = st.text_input("Отчество")
        with col2:
            dept_options = get_departments()
            department = st.selectbox("Подразделение", [""] + dept_options, format_func=lambda x: "Выберите" if x == "" else x)
            if department == "":
                department = st.text_input("Или введите новое")
            pin = st.text_input("PIN-код (4 цифры)", type="password", max_chars=4)
            confirm_pin = st.text_input("Подтвердите PIN-код", type="password", max_chars=4)
        
        if st.button("Зарегистрироваться", type="primary", use_container_width=True):
            if last_name and first_name and patronymic and department and pin and pin == confirm_pin and len(pin) == 4 and pin.isdigit():
                full_fio = f"{last_name} {first_name} {patronymic}"
                normalized_fio = normalize_fio(full_fio)
                generated_login = generate_login(conn, normalized_fio)
                if generated_login:
                    user_id, error = register_user(generated_login, normalized_fio, department, pin)
                    if user_id:
                        st.session_state.temp_login = generated_login
                        st.session_state.show_login_message = True
                        st.session_state.user_id = user_id
                        st.session_state.user_fio = normalized_fio
                        st.session_state.user_login = generated_login
                        st.session_state.user_dept = department
                        st.rerun()
                    else:
                        st.error(error)
                else:
                    st.error("Ошибка формирования логина")
            else:
                st.error("Проверьте правильность заполнения")
    st.stop()

# ==================== ОСНОВНОЕ ПРИЛОЖЕНИЕ ====================
is_admin = (st.session_state.user_login == "admin3452")

# Верхняя панель с информацией о пользователе и кнопкой выхода
col1, col2, col3 = st.columns([3, 2, 1])
with col1:
    fio_parts = st.session_state.user_fio.split()
    if len(fio_parts) >= 3:
        display_name = f"{fio_parts[0]} {fio_parts[1][0]}.{fio_parts[2][0]}."
    elif len(fio_parts) == 2:
        display_name = f"{fio_parts[0]} {fio_parts[1][0]}."
    else:
        display_name = st.session_state.user_fio
    
    st.markdown(f"""
    <div class="user-info">
        👤 {display_name}<br>
        🏢 {st.session_state.user_dept}<br>
        🔑 Логин: <strong>{st.session_state.user_login}</strong>
    </div>
    """, unsafe_allow_html=True)
with col3:
    if st.button("🚪 Выход", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Кнопка просмотра логов (только для администратора)
if is_admin:
    col_debug1, col_debug2 = st.columns([4, 1])
    with col_debug2:
        if st.button("🐛 Логи", help="Показать отладочные сообщения"):
            st.session_state.show_debug = not st.session_state.get('show_debug', False)
    
    if st.session_state.get('show_debug', False):
        with st.expander("📋 Отладочные сообщения", expanded=True):
            if logger.logs:
                for log in logger.logs[-50:]:
                    st.code(log, language="text")
            else:
                st.info("Нет сообщений")

# Кнопка синхронизации (только для админа)
if is_admin:
    col_sync1, col_sync2 = st.columns(2)
    with col_sync1:
        if st.button("🔄 Синхронизировать", use_container_width=True, help="Сохранить данные в облако"):
            success, msg = sync_to_cloud()
            st.toast(msg, icon="✅" if success else "❌")
    with col_sync2:
        if st.button("⬇️ Загрузить с диска", use_container_width=True, help="Обновить данные из облака"):
            success, msg = download_from_cloud()
            if success:
                st.toast(msg, icon="✅")
                st.rerun()
            else:
                st.toast(msg, icon="❌")

# Навигация для администратора и обычного пользователя
if is_admin:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Главная", "📋 Документы", "📅 Календарь", "➕ Добавить", "⚙️ Управление"])
else:
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Главная", "📋 Документы", "📅 Календарь", "➕ Добавить"])

# ==================== ГЛАВНАЯ ====================
with tab1:
    df_all = get_user_docs(st.session_state.user_id, st.session_state.user_login)
    if not df_all.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего", len(df_all))
        with col2:
            active = len(df_all[df_all['status'] != 'Исполнен'])
            st.metric("В работе", active)
        with col3:
            completed = len(df_all[df_all['status'] == 'Исполнен'])
            st.metric("Исполнено", completed)
        
        st.markdown("---")
        st.subheader("⭐ Закрепленные")
        starred = df_all[df_all['starred'] == 1].head(3)
        for _, row in starred.iterrows():
            st.markdown(f"**{row['doc_type']}** {f'№{row['doc_number']}' if row['doc_number'] else ''}")
            st.caption(f"📅 {row['reg_date']} | {row['status']}")
            st.markdown("---")
    else:
        st.info("Нет документов")

# ==================== ДОКУМЕНТЫ ====================
with tab2:
    st.markdown("### 🔍 Фильтры")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_type = st.selectbox("Вид", ["Все"] + get_doc_types())
    with col_f2:
        filter_status = st.selectbox("Статус", ["Все", "В работе", "Передан", "Исполнен"])
    
    today = datetime.now().date()
    df_all = get_user_docs(st.session_state.user_id, st.session_state.user_login)
    
    if filter_type != "Все":
        df_all = df_all[df_all['doc_type'] == filter_type]
    if filter_status != "Все":
        df_all = df_all[df_all['status'] == filter_status]
    
    if df_all.empty:
        st.info("Нет документов")
    else:
        for _, row in df_all.iterrows():
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['doc_type']}** {f'№{row['doc_number']}' if row['doc_number'] else ''}")
                    st.caption(f"📅 {row['reg_date']}")
                with col2:
                    st.markdown(f"**{row['status']}**")
                
                if row['deadline']:
                    deadline = pd.to_datetime(row['deadline']).date()
                    days_left = (deadline - today).days
                    if row['status'] != 'Исполнен':
                        if days_left < 0:
                            st.warning(f"⚠️ Просрочено на {abs(days_left)} дн.")
                        elif days_left <= 3:
                            st.warning(f"🟡 Срок через {days_left} дн.")
                        else:
                            st.caption(f"📅 Срок: {deadline}")
                
                st.markdown(f"📄 {row['summary'][:100]}...")
                
                if row['executor_fio']:
                    exec_parts = row['executor_fio'].split()
                    if len(exec_parts) >= 3:
                        exec_display = f"{exec_parts[0]} {exec_parts[1][0]}.{exec_parts[2][0]}."
                    else:
                        exec_display = row['executor_fio']
                    st.caption(f"👤 {exec_display}")
                else:
                    st.caption(f"👤 {row['with_who_fio'] if row['with_who_fio'] else 'Не указан'}")
                
                # История изменений
                if row['status_history'] and row['status_history'].strip():
                    with st.expander("📜 История изменений", expanded=False):
                        for line in row['status_history'].strip().split('\n'):
                            st.text(line)
                
                if st.button(f"✏️ Редактировать", key=f"edit_{row['id']}", use_container_width=True):
                    st.session_state.selected_doc_id = row['id']
                    st.rerun()
                
                if st.session_state.selected_doc_id == row['id']:
                    # Получаем данные документа
                    doc = conn.execute("""
                        SELECT d.*, s.fio as executor_fio, s.department as executor_dept
                        FROM docs d
                        LEFT JOIN staff s ON d.with_who_login = s.login
                        WHERE d.id = ? AND d.user_id = ?
                    """, (row['id'], st.session_state.user_id)).fetchone()
                    
                    if doc:
                        # Блок выбора статуса (вне формы)
                        status_options = ["В работе", "Передан", "Исполнен"]
                        current_status = doc[11] if doc[11] else "В работе"
                        status_index = status_options.index(current_status) if current_status in status_options else 0
                        new_status = st.selectbox("Статус", status_options, index=status_index, key=f"status_select_{row['id']}")
                        
                        # Блок выбора исполнителя (появляется только если статус "Передан")
                        selected_login = st.session_state.user_login
                        selected_fio = st.session_state.user_fio
                        
                        if new_status == "Передан":
                            st.warning("⚠️ Выберите исполнителя для передачи документа")
                            executor_mode = st.radio(
                                "Способ указания исполнителя",
                                ["Выбрать из списка", "Ввести вручную"],
                                horizontal=True,
                                key=f"executor_mode_{row['id']}"
                            )
                            
                            if executor_mode == "Выбрать из списка":
                                staff_list = get_staff_list()
                                if staff_list:
                                    staff_displays = [s['display'] for s in staff_list]
                                    current_with_who_login = doc[8] if doc[8] else st.session_state.user_login
                                    default_display = None
                                    for s in staff_list:
                                        if s['login'] == current_with_who_login:
                                            default_display = s['display']
                                            break
                                    default_index = 0
                                    if default_display and default_display in staff_displays:
                                        default_index = staff_displays.index(default_display)
                                    with_who = st.selectbox(
                                        "Выберите исполнителя",
                                        staff_displays,
                                        index=default_index,
                                        key=f"executor_select_{row['id']}"
                                    )
                                    selected_login = with_who.split("(")[-1].split(")")[0].strip()
                                    selected_fio = with_who.split("(")[0].strip()
                                else:
                                    st.error("Нет зарегистрированных сотрудников")
                                    selected_login = ""
                                    selected_fio = ""
                            else:
                                selected_fio = st.text_input(
                                    "Введите фамилию и инициалы",
                                    value=doc[9] if doc[9] else "",
                                    placeholder="например: Сидоров П.П.",
                                    key=f"executor_manual_{row['id']}"
                                )
                                selected_login = selected_fio
                            
                            if not selected_fio:
                                st.error("⚠️ Укажите исполнителя для передачи документа")
                        elif new_status == "В работе":
                            selected_login = st.session_state.user_login
                            selected_fio = st.session_state.user_fio
                            fio_parts = st.session_state.user_fio.split()
                            if len(fio_parts) >= 3:
                                display_name = f"{fio_parts[0]} {fio_parts[1][0]}.{fio_parts[2][0]}."
                            else:
                                display_name = st.session_state.user_fio
                            st.info(f"Исполнитель: {display_name}")
                        
                        # Форма с остальными полями
                        with st.form(key=f"edit_form_{row['id']}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                doc_number = st.text_input("Номер документа", value=doc[3] if doc[3] else "", key=f"doc_num_{row['id']}")
                                
                                dept_options = get_departments()
                                current_sender = doc[5] if doc[5] else ""
                                if current_sender in dept_options:
                                    sender_index = dept_options.index(current_sender) + 1
                                else:
                                    sender_index = 0
                                sender_select = st.selectbox(
                                    "От кого поступил",
                                    options=[""] + dept_options,
                                    index=sender_index,
                                    key=f"sender_select_{row['id']}"
                                )
                                sender_new = st.text_input(
                                    "Или введите новое",
                                    value=current_sender if current_sender not in dept_options else "",
                                    key=f"sender_new_{row['id']}"
                                )
                                sender = sender_new if sender_new else sender_select
                                
                                summary = st.text_area("Содержание", value=doc[6] if doc[6] else "", height=100, key=f"summary_{row['id']}")
                                
                                current_deadline = pd.to_datetime(doc[10]).date() if doc[10] else None
                                deadline = st.date_input(
                                    "Срок исполнения (необязательно)",
                                    value=current_deadline if current_deadline else None,
                                    key=f"deadline_{row['id']}"
                                )
                            
                            with col2:
                                # Если статус "Исполнен" — можно изменить исполнителя
                                if new_status == "Исполнен":
                                    change_executor = st.checkbox("Изменить исполнителя", key=f"change_executor_{row['id']}")
                                    if change_executor:
                                        executor_mode = st.radio(
                                            "Способ указания",
                                            ["Выбрать из списка", "Ввести вручную"],
                                            horizontal=True,
                                            key=f"executor_mode_completed_{row['id']}"
                                        )
                                        if executor_mode == "Выбрать из списка":
                                            staff_list = get_staff_list()
                                            if staff_list:
                                                staff_displays = [s['display'] for s in staff_list]
                                                current_with_who_login = doc[8] if doc[8] else st.session_state.user_login
                                                default_display = None
                                                for s in staff_list:
                                                    if s['login'] == current_with_who_login:
                                                        default_display = s['display']
                                                        break
                                                default_index = 0
                                                if default_display and default_display in staff_displays:
                                                    default_index = staff_displays.index(default_display)
                                                with_who = st.selectbox(
                                                    "Выберите исполнителя",
                                                    staff_displays,
                                                    index=default_index,
                                                    key=f"executor_select_completed_{row['id']}"
                                                )
                                                selected_login = with_who.split("(")[-1].split(")")[0].strip()
                                                selected_fio = with_who.split("(")[0].strip()
                                            else:
                                                selected_login = doc[8] if doc[8] else st.session_state.user_login
                                                selected_fio = doc[9] if doc[9] else st.session_state.user_fio
                                        else:
                                            selected_fio = st.text_input(
                                                "Введите фамилию и инициалы",
                                                value=doc[9] if doc[9] else "",
                                                key=f"executor_manual_completed_{row['id']}"
                                            )
                                            selected_login = selected_fio
                                    else:
                                        selected_login = doc[8] if doc[8] else st.session_state.user_login
                                        selected_fio = doc[9] if doc[9] else st.session_state.user_fio
                                
                                status_comment = st.text_input("Комментарий к изменению статуса", key=f"status_comment_{row['id']}")
                                comment = st.text_area("Примечание", value=doc[13] if doc[13] else "", key=f"comment_{row['id']}")
                                starred = st.checkbox("⭐ Закрепить документ", value=doc[15] == 1, key=f"starred_{row['id']}")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.form_submit_button("💾 Сохранить", use_container_width=True):
                                    if new_status == "Передан" and not selected_fio:
                                        st.error("Для передачи документа необходимо указать исполнителя")
                                    else:
                                        if sender_new and sender_new not in dept_options:
                                            add_department(sender_new)
                                        
                                        update_document(doc[0], st.session_state.user_id, doc_number, sender, summary,
                                                      selected_login, selected_fio, deadline, comment, starred)
                                        
                                        if new_status != current_status:
                                            update_status(doc[0], st.session_state.user_id, new_status, status_comment,
                                                        selected_login if new_status == "Передан" else None,
                                                        selected_fio if new_status == "Передан" else None)
                                        
                                        st.success("Сохранено!")
                                        st.session_state.selected_doc_id = None
                                        st.rerun()
                            with col_btn2:
                                if st.form_submit_button("❌ Отменить", use_container_width=True):
                                    st.session_state.selected_doc_id = None
                                    st.rerun()
                
                st.markdown("---")

# ==================== КАЛЕНДАРЬ ====================
with tab3:
    df_all = get_user_docs(st.session_state.user_id, st.session_state.user_login)
    if not df_all.empty:
        today = datetime.now().date()
        selected_month = st.date_input("Месяц", today, format="YYYY/MM/DD")
        month_start = selected_month.replace(day=1)
        if selected_month.month == 12:
            month_end = selected_month.replace(year=selected_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = selected_month.replace(month=selected_month.month + 1, day=1) - timedelta(days=1)
        
        deadlines = {}
        for _, row in df_all.iterrows():
            if row['deadline']:
                date_obj = pd.to_datetime(row['deadline']).date()
                if month_start <= date_obj <= month_end:
                    if date_obj not in deadlines:
                        deadlines[date_obj] = []
                    deadlines[date_obj].append({'doc': row, 'status': row['status']})
        
        start_weekday = month_start.weekday()
        days_in_month = (month_end - month_start).days + 1
        
        cols = st.columns(7)
        weekdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        for i, col in enumerate(cols):
            col.markdown(f"<div style='text-align: center; font-weight: bold;'>{weekdays[i]}</div>", unsafe_allow_html=True)
        
        current_day = 1
        for week in range(6):
            cols = st.columns(7)
            for day_idx in range(7):
                if week == 0 and day_idx < start_weekday:
                    cols[day_idx].empty()
                elif current_day > days_in_month:
                    cols[day_idx].empty()
                else:
                    current_date = month_start + timedelta(days=current_day - 1)
                    date_obj = current_date
                    
                    if date_obj in deadlines:
                        has_overdue = any(d['status'] != 'Исполнен' and date_obj < today for d in deadlines[date_obj])
                        has_upcoming = any(d['status'] != 'Исполнен' and (date_obj - today).days <= 7 for d in deadlines[date_obj])
                        if has_overdue:
                            color = "🔴"
                        elif has_upcoming:
                            color = "🟡"
                        else:
                            color = "🟢"
                    else:
                        color = "⚪"
                    
                    if date_obj == today:
                        color = "🔵"
                    
                    with cols[day_idx]:
                        st.markdown(f"<div style='text-align: center; padding: 8px; background: #f0f2f6; border-radius: 8px;'>{color}<br><strong>{current_day}</strong></div>", unsafe_allow_html=True)
                    
                    current_day += 1
    else:
        st.info("Нет документов")

# ==================== ДОБАВИТЬ ДОКУМЕНТ ====================
with tab4:
    with st.form("add_doc", clear_on_submit=True):
        doc_type = st.selectbox("Вид документа", get_doc_types())
        doc_number = st.text_input("Номер (необязательно)")
        
        dept_options = get_departments()
        sender = st.selectbox("От кого поступил", [""] + dept_options, format_func=lambda x: "Выберите" if x == "" else x)
        if sender == "":
            sender = st.text_input("Или введите новое")
        
        reg_date = st.date_input("Дата поступления", datetime.now().date())
        deadline = st.date_input("Срок исполнения (необязательно)", value=None)
        
        st.markdown("**У кого находится**")
        st.info("По умолчанию — вы")
        selected_login = st.session_state.user_login
        selected_fio = st.session_state.user_fio
        
        summary = st.text_area("Содержание", height=100)
        comment = st.text_area("Примечание")
        starred = st.checkbox("⭐ Закрепить")
        
        if st.form_submit_button("➕ Добавить", use_container_width=True, type="primary"):
            if summary:
                if sender and sender not in dept_options:
                    add_department(sender)
                add_document(
                    st.session_state.user_id, doc_type, doc_number, reg_date, sender, summary,
                    selected_login, selected_fio, deadline, comment, starred
                )
                st.success("✅ Документ добавлен!")
                st.toast("Документ добавлен!", icon="✅")
                st.rerun()
            else:
                st.error("Введите содержание")

# ==================== УПРАВЛЕНИЕ (только для администратора) ====================
if is_admin and 'tab5' in locals():
    with tab5:
        st.title("⚙️ Управление")
        
        tab_a, tab_b, tab_c, tab_d = st.tabs(["👥 Сотрудники", "🏢 Подразделения", "📄 Виды документов", "👤 Пользователи"])
        
        with tab_a:
            st.subheader("Список сотрудников")
            df_staff = pd.read_sql("""
                SELECT id, fio, login, department, 
                       CASE WHEN is_user = 1 THEN 'Да' ELSE 'Нет' END as registered
                FROM staff 
                WHERE login != 'admin3452'
                ORDER BY fio
            """, conn)
            if not df_staff.empty:
                display_data = []
                for _, row in df_staff.iterrows():
                    parts = row['fio'].split()
                    if len(parts) >= 3:
                        display_fio = f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
                    else:
                        display_fio = row['fio']
                    display_data.append({
                        'id': row['id'],
                        'ФИО': display_fio,
                        'Логин': row['login'],
                        'Подразделение': row['department'],
                        'Зарегистрирован': row['registered']
                    })
                st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
                
                del_id = st.number_input("ID для удаления", min_value=1, step=1)
                if st.button("🗑️ Удалить сотрудника"):
                    used = conn.execute("SELECT COUNT(*) FROM docs WHERE with_who_login = (SELECT login FROM staff WHERE id=?)", (del_id,)).fetchone()[0]
                    if used > 0:
                        st.error(f"Нельзя удалить — сотрудник указан в {used} документе(ах)")
                    else:
                        conn.execute("DELETE FROM staff WHERE id=?", (del_id,))
                        conn.commit()
                        st.success("Удалено")
                        st.rerun()
            else:
                st.info("Сотрудников пока нет")
            
            st.markdown("---")
            st.subheader("➕ Добавить сотрудника")
            new_fio = st.text_input("ФИО (полностью)")
            new_login = st.text_input("Логин")
            new_dept = st.text_input("Подразделение")
            if st.button("Добавить сотрудника", use_container_width=True):
                if new_fio and new_login and new_dept:
                    try:
                        conn.execute("INSERT INTO staff (fio, login, department, is_user) VALUES (?, ?, ?, 0)", (new_fio, new_login, new_dept))
                        conn.commit()
                        add_department(new_dept)
                        st.success(f"Добавлен: {new_fio}")
                        st.rerun()
                    except:
                        st.error("Ошибка: логин уже существует")
                else:
                    st.error("Заполните все поля")
        
        with tab_b:
            st.subheader("Список подразделений")
            df_depts = pd.read_sql("SELECT id, name FROM departments ORDER BY name", conn)
            if not df_depts.empty:
                st.dataframe(df_depts, use_container_width=True, hide_index=True)
                del_id = st.number_input("ID для удаления", min_value=1, step=1, key="del_dept")
                if st.button("🗑️ Удалить подразделение"):
                    conn.execute("DELETE FROM departments WHERE id=?", (del_id,))
                    conn.commit()
                    st.success("Удалено")
                    st.rerun()
            else:
                st.info("Подразделений пока нет")
            
            st.markdown("---")
            st.subheader("➕ Добавить подразделение")
            new_dept = st.text_input("Новое подразделение")
            if st.button("Добавить подразделение", use_container_width=True):
                if new_dept:
                    add_department(new_dept)
                    st.success(f"Добавлено: {new_dept}")
                    st.rerun()
        
        with tab_c:
            st.subheader("Список видов документов")
            df_doc_types = pd.read_sql("SELECT id, name FROM doc_types ORDER BY name", conn)
            if not df_doc_types.empty:
                st.dataframe(df_doc_types, use_container_width=True, hide_index=True)
                del_id = st.number_input("ID для удаления", min_value=1, step=1, key="del_doc_type")
                if st.button("🗑️ Удалить вид документа"):
                    doc_name = df_doc_types[df_doc_types['id'] == del_id]['name'].values
                    if len(doc_name) > 0:
                        used = conn.execute("SELECT COUNT(*) FROM docs WHERE doc_type = ?", (doc_name[0],)).fetchone()[0]
                        if used > 0:
                            st.error(f"Нельзя удалить — вид используется в {used} документе(ах)")
                        else:
                            conn.execute("DELETE FROM doc_types WHERE id=?", (del_id,))
                            conn.commit()
                            st.success("Удалено")
                            st.rerun()
            else:
                st.info("Видов документов пока нет")
            
            st.markdown("---")
            st.subheader("➕ Добавить вид документа")
            new_doc_type = st.text_input("Новый вид документа")
            if st.button("Добавить вид документа", use_container_width=True):
                if new_doc_type:
                    if add_doc_type(new_doc_type):
                        st.success(f"Добавлено: {new_doc_type}")
                        st.rerun()
                    else:
                        st.error("Ошибка: такой вид уже существует")
        
        with tab_d:
            st.subheader("Список зарегистрированных пользователей")
            df_users = pd.read_sql("""
                SELECT s.id, s.fio, s.login, s.department, u.created_at
                FROM staff s
                JOIN users u ON s.id = u.user_id
                WHERE s.login != 'admin3452'
                ORDER BY s.fio
            """, conn)
            if not df_users.empty:
                display_data = []
                for _, row in df_users.iterrows():
                    parts = row['fio'].split()
                    if len(parts) >= 3:
                        display_fio = f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
                    else:
                        display_fio = row['fio']
                    display_data.append({
                        'id': row['id'],
                        'ФИО': display_fio,
                        'Логин': row['login'],
                        'Подразделение': row['department'],
                        'Дата регистрации': row['created_at']
                    })
                st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
                
                del_user_id = st.number_input("ID пользователя для удаления", min_value=1, step=1)
                if st.button("🗑️ Удалить пользователя", type="secondary"):
                    if del_user_id == st.session_state.user_id:
                        st.error("Нельзя удалить самого себя")
                    else:
                        conn.execute("DELETE FROM docs WHERE user_id = ?", (del_user_id,))
                        conn.execute("DELETE FROM users WHERE user_id = ?", (del_user_id,))
                        conn.execute("UPDATE staff SET is_user = 0 WHERE id = ?", (del_user_id,))
                        conn.commit()
                        st.success("Пользователь удален")
                        st.rerun()
            else:
                st.info("Пользователей пока нет")
            
            st.markdown("---")
            st.subheader("✏️ Редактирование пользователя")
            user_options = {f"{row['fio']} ({row['login']})": row['id'] for _, row in df_users.iterrows()}
            if user_options:
                selected_user_display = st.selectbox("Выберите пользователя", list(user_options.keys()))
                selected_user_id = user_options[selected_user_display]
                user_data = df_users[df_users['id'] == selected_user_id].iloc[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    new_pin = st.text_input("Новый PIN-код", type="password", max_chars=4)
                    confirm_pin = st.text_input("Подтвердите PIN-код", type="password", max_chars=4)
                    if st.button("Изменить PIN-код", use_container_width=True):
                        if new_pin and confirm_pin and new_pin == confirm_pin and len(new_pin) == 4 and new_pin.isdigit():
                            new_pin_hash = hash_pin(new_pin)
                            conn.execute("UPDATE users SET pin_code = ? WHERE user_id = ?", (new_pin_hash, selected_user_id))
                            conn.commit()
                            st.success("PIN-код изменен!")
                            st.rerun()
                        else:
                            st.error("PIN-код должен быть 4 цифры и совпадать")
                
                with col2:
                    dept_options = get_departments()
                    current_dept = user_data['department']
                    new_dept = st.selectbox("Новое подразделение", dept_options, index=dept_options.index(current_dept) if current_dept in dept_options else 0)
                    if st.button("Изменить подразделение", use_container_width=True):
                        if new_dept != current_dept:
                            conn.execute("UPDATE staff SET department = ? WHERE id = ?", (new_dept, selected_user_id))
                            conn.commit()
                            add_department(new_dept)
                            st.success("Подразделение изменено!")
                            st.rerun()
            else:
                st.info("Нет пользователей для редактирования")