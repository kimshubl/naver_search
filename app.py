from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort
from functools import wraps
import time
from collections import defaultdict
import secrets
import sqlite3
import datetime
import json # Add json import
from utils import *
import config # Import config file
import toss_utils # Import toss utils
import csv
import io

# 로그인 데코레이터 (이미 있다면 이 부분은 수정 불필요)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- 새로운 구독 확인 데코레이터 ---
def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for('login'))

        user_id = session['user_id']

        # 관리자는 구독 체크 건너뛰기
        if user_id == 'admin':
            return f(*args, **kwargs)

        conn = None
        try:
            conn = sqlite3.connect(USERS_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT subscription_status, subscription_expiry FROM users WHERE username = ?", (user_id,))
            user = cursor.fetchone()
        except sqlite3.Error as e:
            flash(f"데이터베이스 오류: {e}", "danger")
            return redirect(url_for('home')) # 오류 시 홈으로 리디렉션
        finally:
            if conn:
                conn.close()

        is_subscribed = False
        if user:
            expiry_date = None
            if user['subscription_expiry']:
                try:
                    # 저장된 문자열을 datetime 객체로 변환 (형식: YYYY-MM-DD HH:MM:SS)
                    expiry_date = datetime.datetime.strptime(user['subscription_expiry'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print(f"User {user_id} has invalid subscription_expiry format: {user['subscription_expiry']}")
                    expiry_date = None # 유효하지 않은 날짜로 간주
                except TypeError: # None 값 처리
                     expiry_date = None


            if user['subscription_status'] == 'active' and expiry_date and expiry_date > datetime.datetime.now():
                is_subscribed = True

        if is_subscribed:
            return f(*args, **kwargs)
        else:
            flash("구독 회원 전용 기능입니다. 구독 후 이용해주세요.", "warning")
            # '/subscribe' 라우트로 리디렉션
            return redirect(url_for('subscribe')) # '/subscribe' 라우트 생성 필요

    return decorated_function
# --- 데코레이터 끝 ---


# Import the rank finder class
from test4 import NaverMapSearchRankFinder
# Import the search volume function from the original script
from blog_rank_test import get_monthly_search_volume
# Import the restaurant name extractor
from id_rank import extract_restaurant_name
# Import the single rank update function
from rank_chart import update_single_rank

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Database names
USERS_DB = 'users.db'
REQUESTS_DB = 'requests.db'
RANK_CHART_DB = 'rank_chart.db' # Define rank chart DB name

# 로그인 시도 기록
login_attempts = defaultdict(list)
email_send_times = defaultdict(float)

# 로그인 시도 횟수 제한
MAX_ATTEMPTS = 5
LOCK_TIME = 60 * 5  # 5분
# 이메일 인증 토큰 제한 시간
MAX_TOKEN_AGE = 3600  # 1시간
# 전송 제한
REQUEST_SEND_INTERVAL = 30  # 최소 30초 간격
EMAIL_SEND_INTERVAL = 30  # 최소 5분 간격

# --- Context Processor ---
@app.context_processor
def inject_user_info():
    user_info = {'current_points': None, 'subscription_status': None, 'is_admin': False, 'user_id': None}
    if 'user_id' in session:
        user_id = session['user_id']
        user_info['user_id'] = user_id
        user_info['is_admin'] = (user_id == 'admin')

        if user_info['is_admin']:
            user_info['current_points'] = "무제한"
            user_info['subscription_status'] = "관리자"
        else:
            conn = None
            try:
                conn = sqlite3.connect(USERS_DB)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Fetch points and subscription status in one query
                cursor.execute("SELECT points, subscription_status, subscription_expiry FROM users WHERE username = ?", (user_id,))
                user = cursor.fetchone()
                if user:
                    user_info['current_points'] = user['points']
                    # Check subscription validity
                    is_subscribed = False
                    if user['subscription_status'] == 'active' and user['subscription_expiry']:
                         try:
                             expiry_dt = datetime.datetime.strptime(user['subscription_expiry'], '%Y-%m-%d %H:%M:%S')
                             if expiry_dt > datetime.datetime.now():
                                 is_subscribed = True
                         except (ValueError, TypeError):
                             pass # Invalid format or None
                    user_info['subscription_status'] = 'active' if is_subscribed else 'inactive'
                else:
                    # User not found in DB (edge case, maybe after DB reset)
                    user_info['current_points'] = 0
                    user_info['subscription_status'] = 'inactive'
            except sqlite3.Error as e:
                print(f"Error fetching user info for navbar: {e}")
                user_info['current_points'] = "오류"
                user_info['subscription_status'] = "오류"
            finally:
                if conn:
                    conn.close()
    # Return as a dictionary to be merged into the template context
    return dict(user_info=user_info)
# --- End Context Processor ---


###############################################################################
# render 함수들 ###############################################################

# 메인 화면
@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        user_id = session['user_id'] # 현재 로그인된 사용자 ID

        # --- 포인트 확인 및 차감 로직 (관리자 제외) ---
        required_points = 0 # POST 요청 시작 시 초기화
        user_points = 0 # 초기화
        new_points = 0 # 초기화

        if user_id != 'admin':
            conn = None
            try:
                conn = sqlite3.connect(USERS_DB)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT points FROM users WHERE username = ?", (user_id,))
                user = cursor.fetchone()
                user_points = user['points'] if user else 0
            except sqlite3.Error as e:
                flash(f"포인트 조회 중 오류 발생: {e}", "danger")
                return redirect(url_for('home'))
            finally:
                if conn:
                    conn.close()

            # 필요한 포인트 계산
            required_points = 500
            service_str_check = request.form.get('service') # 변수명 변경
            if service_str_check == "트래픽":
                try:
                    traffic_amount = int(request.form.get('traffic_amount', 0))
                    if traffic_amount < 0: traffic_amount = 0 # 음수 방지
                except (ValueError, TypeError):
                    traffic_amount = 0
                required_points += traffic_amount * 10

            # 포인트 비교
            if user_points < required_points:
                flash(f"포인트가 부족합니다. (현재: {user_points}P, 필요: {required_points}P)", "warning")
                # '/charge-points' 라우트로 리디렉션
                return redirect(url_for('charge_points')) # '/charge-points' 라우트 생성 필요
        # --- 포인트 확인 끝 ---


        # 시간 제한 걸기 (기존 로직 유지)
        last_request_time = session.get('last_request_time', 0)
        if is_request_too_soon('last_request_time', REQUEST_SEND_INTERVAL):
            flash(f"요청은 {REQUEST_SEND_INTERVAL}초에 한 번만 보낼 수 있습니다.", "danger")
            return redirect(url_for('home'))
        session['last_request_time'] = time.time()

        # Service Value Validation and Conversion (기존 로직 유지)
        service_str = request.form.get('service') # 여기서 다시 가져옴
        service_int = None
        if service_str == "저장하기":
            service_int = 1
        elif service_str == "트래픽":
            service_int = 2
        else:
            # Handle invalid or missing service selection
            flash("유효한 서비스를 선택해주세요.", "danger")
            return redirect(url_for('home'))
        # --- End Validation ---

        # 요청 데이터 받아오기 (Corrected Indentation)
        keyword_value = request.form.get('keyword') # Get keyword from form
        request_data = {
            'name': request.form.get('name'),
            'keyword': keyword_value, # Add keyword to data
            'merchandise': 1 if request.form.get('merchandise') == '네이버 플레이스' else 0, # Convert checkbox value
            'service': service_int, # Use the converted integer value
            'sub_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            'traffic_amount': request.form.get('traffic_amount') if service_int == 2 else None, # Only store traffic if service is '트래픽' (2)
            'state': '대기중',
            'link': request.form.get('link'),
            'user_id': user_id # 위에서 가져온 user_id 사용
        }

        # 요청 데이터 저장 (기존 로직 유지)
        save_to_db(REQUESTS_DB, 'requests', request_data)

        # --- 포인트 차감 실행 (관리자 제외) ---
        if user_id != 'admin':
            conn = None
            try:
                # user_points와 required_points는 위에서 이미 계산됨
                new_points = user_points - required_points
                conn = sqlite3.connect(USERS_DB)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET points = ? WHERE username = ?", (new_points, user_id))
                conn.commit()
            except sqlite3.Error as e:
                flash(f"포인트 차감 중 오류 발생: {e}", "danger")
                # 여기서 요청 취소 로직을 추가할 수도 있음 (선택 사항)
                # 예: delete_from_db(REQUESTS_DB, 'requests', {'sub_time': request_data['sub_time']})
                return redirect(url_for('home'))
            finally:
                if conn:
                    conn.close()
        # --- 포인트 차감 끝 ---

        flash(f'전송이 완료되었습니다! (차감 후 포인트: {new_points if user_id != "admin" else "관리자"})', 'success')
        return redirect(url_for('home'))

    # GET 요청 처리: Context processor가 정보를 주입하므로 별도 전달 불필요
    return render_template('index.html', session=session) # current_points 제거

# 계정 페이지
@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    # 사용자 정보 확인
    user_id = session['user_id']
    user_data_raw = load_from_db('users.db', 'users', {'username': user_id})

    # Check if user exists in DB (might have been deleted after DB recreation)
    if not user_data_raw:
        session.pop('user_id', None) # Log out user
        flash("사용자 정보를 찾을 수 없습니다. 다시 로그인해주세요.", "warning")
        return redirect(url_for('login'))

    # Convert row to dictionary (only if user_data_raw is not empty)
    user_data = [dict(row) for row in user_data_raw] 

    # 어드민 전용 설정
    session['is_admin'] = user_id == "admin"

    # 이메일 session에 저장
    session['email'] = user_data[0].get('email', '')

    # requests속 각각 request에 대하여 정보를 각 순서마다 담은 딕셔너리의 리스트로 변환
    requests_raw = load_from_db('requests.db', 'requests', {'user_id': user_id} if not session['is_admin'] else None)
    requests = []
    for row in requests_raw:
        # Access data by column name using the sqlite3.Row object
        request_item = {
            'name': row['name'],
            'keyword': row['keyword'] if 'keyword' in row.keys() else 'N/A', # Get keyword, handle if column doesn't exist yet
            'sub_time': row['sub_time'],
            'user_id': row['user_id'],
            'merchandise': row['merchandise'], # Assuming these are stored correctly
            'service': row['service'],         # Assuming these are stored correctly
            'traffic_amount': row['traffic_amount'],
            'state': row['state'],
            'link': row['link'] if 'link' in row.keys() else None
        }
        # Optional: Convert merchandise/service to int if needed for template logic, but access by name first
        try:
            request_item['merchandise'] = int(request_item['merchandise']) if request_item['merchandise'] is not None else 0
            request_item['service'] = int(request_item['service']) if request_item['service'] is not None else 0
        except (ValueError, TypeError):
             request_item['merchandise'] = 0 # Default on conversion error
             request_item['service'] = 0     # Default on conversion error

        requests.append(request_item)

    if request.method == 'POST':
        if 'reset_password' in request.form:
            last_email_time = session.get('last_email_time', 0)
            if time.time() - last_email_time < EMAIL_SEND_INTERVAL:
                flash("너무 자주 비밀번호 변경 메일을 보낼 수 없습니다. 잠시 후 다시 시도하세요.", "danger")
                return redirect(url_for('account'))
            # 제한을 넘겼으면 시간 갱신
            session['last_email_time'] = time.time()

            # 비밀번호 재설정 토큰 생성: 사용자가 본인임을 확인하고 비밀번호를 변경할 수 있도록 임시 토큰 생성
            token = secrets.token_urlsafe(32)
            session['reset_token'] = { # 세션에 이메일, 토큰, 생성 시간 저장
                'email': session['email'],
                'token': token, # 생성된 비밀번호 재설정 토큰
                'token_time': time.time()
            }

            link = url_for('reset_password', token=token, _external=True)
            send_password_reset(session['email'], link)  # utils.py 함수

            flash(f"{session['email']} 주소로 비밀번호 재설정 링크가 전송되었습니다.", "warning")
            return redirect(url_for('account'))

    # Context processor가 user_info를 주입하므로 user_details 전달 제거
    return render_template('account.html', requests=requests, session=session) # user_details 제거


# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register.html')

# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password') # Note: Password field is still needed in the form, but won't be used for admin

        # --- Admin Login Special Handling ---
        if username == 'admin' and password == 'password123':
            # Check email send interval for admin login attempts
            last_admin_email_time = session.get('last_admin_email_time', 0)
            if time.time() - last_admin_email_time < EMAIL_SEND_INTERVAL: # Reuse existing interval
                flash(f"관리자 로그인 인증 메일은 {EMAIL_SEND_INTERVAL // 60}분에 한 번만 보낼 수 있습니다.", "danger")
                return render_template('login.html', session=session)

            admin_email = "sonyeon465@gmail.com" # Hardcoded as requested
            # Optional: Could fetch from DB:
            # admin_user = load_from_db('users.db', 'users', {'username': 'admin'})
            # if not admin_user or not admin_user[0].get('email'):
            #     flash("관리자 계정에 이메일이 등록되지 않았습니다.", "danger")
            #     return render_template('login.html', session=session)
            # admin_email = admin_user[0]['email']

            # 관리자 로그인 인증 토큰 생성: 관리자 이메일로 링크를 보내 로그인을 인증하기 위한 임시 토큰
            token = secrets.token_urlsafe(32)
            session['admin_login_token'] = { # 세션에 토큰과 생성 시간 저장
                'token': token, # 생성된 관리자 로그인 토큰
                'token_time': time.time()
            }
            session['last_admin_email_time'] = time.time() # Update last send time

            link = url_for('verify_admin_login', token=token, _external=True)
            send_admin_login_verification(admin_email, link) # Use the new function from utils

            flash(f"{admin_email} 주소로 관리자 로그인 인증 링크를 전송했습니다. 이메일을 확인해주세요.", "info")
            return render_template('login.html', session=session)
        # --- End Admin Login Special Handling ---

        # --- Regular User Login ---
        # 로그인 시도 기록 확인 (브루트 포스 감지)
        if username in login_attempts:
            attempts = login_attempts[username]
            attempts = [t for t in attempts if t > time.time() - LOCK_TIME]  # 유효한 시도만 남김
            login_attempts[username] = attempts
            if len(attempts) >= MAX_ATTEMPTS:
                flash("로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.", 'danger')
                return render_template('login.html', session=session)

        users = load_from_db('users.db', 'users', {'username': username})

        # 로그인 성공 시
        if users and check_password(users[0]['password_hash'], password):
            session['user_id'] = username
            login_attempts[username] = []  # 로그인 성공 시 시도 기록 초기화
            return redirect(url_for('home'))

        # 로그인 실패 기록
        login_attempts[username].append(time.time())
        flash("로그인에 실패하였습니다!", 'danger')
        return render_template('login.html', session=session)

    return render_template('login.html')

# 로그아웃
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # 세션에 저장된 비밀번호 재설정 토큰 정보 확인
    token_data = session.get('reset_token')

    # 비밀번호 재설정 토큰 유효성 검사: URL의 토큰과 세션의 토큰이 일치하는지 확인
    if not token_data or token_data['token'] != token:
        flash("유효하지 않거나 만료된 토큰입니다.", "danger")
        return redirect(url_for('login'))

    # 토큰 유효 시간 검사 (예: 30분)
    if is_token_expired(token_data, 1800):
        session.pop('reset_token', None)
        flash("토큰이 만료되었습니다. 다시 요청해주세요.", "warning")
        return redirect(url_for('login'))

    # POST: 비밀번호 변경 처리
    if request.method == 'POST':
        new_password = request.form.get('password')
        # --- Password Length Validation ---
        if not new_password or len(new_password) > 25:
            flash("새 비밀번호는 1자 이상 25자 이하여야 합니다.", "danger")
            # Redirect back to the same reset page, keeping the token in the URL
            return redirect(url_for('reset_password', token=token))
        # --- End Validation ---

        # 비밀번호 해싱 후 업데이트
        hashed = hash_password(new_password)
        update_db('users.db', 'users', {'email': token_data['email']}, {'password_hash': hashed})
        flash("비밀번호가 성공적으로 변경되었습니다.", "success")

        session.pop('reset_token', None)  # 사용된 비밀번호 재설정 토큰 제거
        return redirect(url_for('login'))

    return render_template('reset_password.html', email=token_data['email'])


###############################################################################
# 처리 관련 라우터들 ##################################################################

# 요청 완료
@app.route('/complete_request/<sub_time>', methods=['POST'])
@login_required
def complete_request(sub_time):
    # SQLite에서 요청 시간이 일치하는 데이터를 수정
    update_db('requests.db', 'requests', {'sub_time': sub_time}, {'state': '완료됨'})
    return redirect(url_for('account'))

# 요청 취소
@app.route('/cancel_request/<sub_time>', methods=['POST'])
@login_required
def cancel_request(sub_time):
    # SQLite에서 요청 시간이 일치하는 데이터를 수정
    update_db('requests.db', 'requests', {'sub_time': sub_time}, {'state': '취소됨'})
    return redirect(url_for('account'))

@app.route('/send_verification_email', methods=['POST'])
def send_verification_email_route():
    email = request.form.get('email')

    # 제한 검사
    if time.time() - email_send_times[email] < EMAIL_SEND_INTERVAL:
        flash("너무 자주 인증 메일을 보낼 수 없습니다. 잠시 후 다시 시도하세요.", 'danger')
        return redirect(url_for('register'))
    email_send_times[email] = time.time()

    username = request.form.get('username')
    password = request.form.get('password')

    # --- Username Length Validation ---
    if not username or len(username) > 15:
        flash("사용자 이름은 1자 이상 15자 이하여야 합니다.", 'danger')
        return redirect(url_for('register'))
    # --- End Validation ---

    # --- Password Length Validation ---
    if not password or len(password) > 25:
        flash("패스워드는 1자 이상 25자 이하여야 합니다.", 'danger')
        return redirect(url_for('register'))
    # --- End Validation ---

    # 중복 확인
    if load_from_db('users.db', 'users', {'username': username}) or load_from_db('users.db', 'users', {'email': email}):
        flash("이미 존재하는 계정 정보입니다.", 'danger')
        return redirect(url_for('register'))

    # 이메일 인증 토큰 생성: 사용자가 제공한 이메일 주소의 소유권을 확인하기 위한 임시 토큰
    token = secrets.token_urlsafe(32)
    session['pending_user'] = { # 회원가입 완료 전 임시 사용자 정보를 세션에 저장
        'username': username,
        'password': hash_password(password),
        'email': email,
        'token': token, # 생성된 이메일 인증 토큰
        'token_time': time.time()
    }

    link = url_for('verify_email', token=token, _external=True)
    send_verification_email(email, link)

    flash("이메일로 인증 링크를 보냈습니다. 인증 후 회원가입이 완료됩니다.", "info")
    return redirect(url_for('register'))


@app.route('/verify_email')
def verify_email():
    # URL에서 이메일 인증 토큰 가져오기
    token = request.args.get('token')
    # 세션에서 임시 사용자 정보 가져오기
    pending = session.get('pending_user')

    # 이메일 인증 토큰 유효성 검사: 세션에 정보가 없거나 토큰이 일치하지 않는 경우
    if not pending or pending.get('token') != token:
        flash("잘못된 또는 만료된 토큰입니다.", 'danger')
        return redirect(url_for('register'))

    # 이메일 인증 토큰 시간 제한 검증
    if time.time() - pending['token_time'] > MAX_TOKEN_AGE:
        session.pop('pending_user', None)
        flash("인증 시간이 만료되었습니다.", 'danger')
        return redirect(url_for('register'))

    # 회원가입 처리 (DB에 사용자 정보 저장)
    save_to_db('users.db', 'users', {
        'username': pending['username'],
        'password_hash': pending['password'],
        'email': pending['email'],
    })

    session.pop('pending_user', None) # 사용된 임시 사용자 정보 제거
    flash("이메일 인증 및 회원가입이 완료되었습니다. 로그인해주세요.", 'success')
    return redirect(url_for('login'))

# 아이디 찾기
@app.route('/forgot_username', methods=['GET', 'POST'])
def forgot_username():
    if request.method == 'POST':
        email = request.form.get('email')
        last_email_time = session.get('last_email_time', 0)
        if time.time() - last_email_time < EMAIL_SEND_INTERVAL:
            flash("너무 자주 전송할 수 없습니다. 잠시 후 다시 시도해주세요.", "danger")
            return redirect(url_for('forgot_password'))

        users = load_from_db('users.db', 'users', {'email': email})


        if users:
            username = users[0]['username']
            send_username_email(email, username)  # utils.py에 정의
            flash(f"{email}로 아이디를 전송했습니다.", "info")
        else:
            flash("해당 이메일로 등록된 아이디가 없습니다.", "danger")

        return redirect(url_for('login'))

    return render_template('forgot_username.html')

# 비밀번호 재설정 요청
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        users = load_from_db('users.db', 'users', {'email': email})

        if not users:
            flash("해당 이메일로 등록된 계정이 없습니다.", "danger")
            return redirect(url_for('forgot_password'))

        last_email_time = session.get('last_email_time', 0)
        if time.time() - last_email_time < EMAIL_SEND_INTERVAL:
            flash("너무 자주 전송할 수 없습니다. 잠시 후 다시 시도해주세요.", "danger")
            return redirect(url_for('login'))

        session['last_email_time'] = time.time()
        # 비밀번호 재설정 토큰 생성 (계정 페이지에서 요청하는 경우와 동일)
        token = secrets.token_urlsafe(32)
        session['reset_token'] = {
            'email': email,
            'token': token, # 생성된 비밀번호 재설정 토큰
            'token_time': time.time()
        }

        link = url_for('reset_password', token=token, _external=True)
        send_password_reset(email, link)
        flash(f"{email}로 비밀번호 재설정 링크를 전송했습니다.", "info")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

# 관리자 로그인 인증 처리
@app.route('/verify_admin_login/<token>')
def verify_admin_login(token):
    # 세션에서 관리자 로그인 토큰 정보 가져오기
    token_data = session.get('admin_login_token')

    # 관리자 로그인 토큰 유효성 검사: URL 토큰과 세션 토큰 비교
    if not token_data or token_data.get('token') != token:
        flash("유효하지 않거나 만료된 관리자 로그인 토큰입니다.", 'danger')
        return redirect(url_for('login'))

    # 관리자 로그인 토큰 만료 시간 검사 (예: 10분)
    if is_token_expired(token_data, 600): # Use 10 minutes expiry for admin login
        session.pop('admin_login_token', None)
        flash("관리자 로그인 토큰이 만료되었습니다. 다시 로그인을 시도해주세요.", 'warning')
        return redirect(url_for('login'))

    # 인증 성공: admin 로그인 처리
    session['user_id'] = 'admin'
    session.pop('admin_login_token', None) # 사용된 관리자 로그인 토큰 제거
    login_attempts['admin'] = [] # 로그인 시도 기록 초기화 (필요시)
    flash("관리자 로그인 인증이 완료되었습니다.", 'success')
    return redirect(url_for('home')) # 로그인 후 홈으로 이동

# 계정 탈퇴 처리
@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = session.get('user_id')

    # 관리자 계정 삭제 방지
    if user_id == 'admin':
        flash("관리자 계정은 탈퇴할 수 없습니다.", "danger")
        return redirect(url_for('account'))

    try:
        # 사용자 정보 삭제 (users.db)
        delete_from_db('users.db', 'users', {'username': user_id})

        # 해당 사용자의 요청 기록 삭제 (requests.db)
        delete_from_db('requests.db', 'requests', {'user_id': user_id})

        # 로그아웃 처리
        session.pop('user_id', None)
        session.clear() # 세션 전체 클리어 (선택적)

        flash("계정이 성공적으로 삭제되었습니다.", "success")
        return redirect(url_for('login'))

    except Exception as e:
        # 데이터베이스 오류 등 예외 처리
        flash(f"계정 삭제 중 오류가 발생했습니다: {e}", "danger")
        return redirect(url_for('account'))

# Route for Feature 1: Naver Map Rank Search Page
@app.route('/feature1_rank_search', methods=['GET', 'POST'])
@login_required
@subscription_required # <-- 데코레이터 추가
def feature1_rank_search():
    result_message = None
    keyword = None
    site_url = None # Changed from store_name
    extracted_store_name = None # To store the name from id_rank.py

    if request.method == 'POST':
        keyword = request.form.get('keyword')
        site_url = request.form.get('site_url') # Get site_url from form

        if not keyword or not site_url:
            result_message = "오류: 검색 키워드와 사이트 주소를 모두 입력해주세요."
        else:
            # 1. Extract store name from URL
            print(f"Attempting to extract store name from URL: {site_url}")
            extracted_store_name = extract_restaurant_name(site_url) # Call function from id_rank

            if extracted_store_name is None:
                result_message = "오류: 입력된 사이트 주소에서 업체명을 추출하지 못했습니다. URL을 확인하거나 지원하지 않는 페이지일 수 있습니다."
            else:
                # 2. Find rank using extracted name and keyword
                print(f"Extracted store name: {extracted_store_name}. Searching rank with keyword: {keyword}")
                finder = NaverMapSearchRankFinder()
                try:
                    top_100_places = finder.fetch_top_100_places(keyword=keyword)

                    if top_100_places is None:
                        result_message = "오류: 네이버 지도 검색 결과를 가져오는 데 실패했습니다."
                    else:
                        rank = finder.find_rank_by_name(top_100_places, extracted_store_name)
                        if rank is not None:
                            result_message = f"'{extracted_store_name}' 가게는 '{keyword}' 검색 결과 상위 100위 중 {rank}위입니다. (URL: {site_url})"
                        else:
                            result_message = f"'{extracted_store_name}' 가게는 '{keyword}' 검색 결과 상위 100위 안에 없습니다. (URL: {site_url})"
                except Exception as e:
                    print(f"Rank search error after name extraction: {e}") # Server log
                    result_message = "오류: 순위 검색 중 예기치 않은 오류가 발생했습니다."

    # Render the template, passing the result message and submitted values back
    return render_template('feature1_rank_search.html',
                           result_message=result_message,
                           keyword=keyword,
                           site_url=site_url) # Pass site_url back

# Route for Feature 2: Naver Keyword Search Volume
@app.route('/feature2_search_volume', methods=['GET', 'POST'])
@login_required
@subscription_required # <-- 데코레이터 추가
def feature2_search_volume():
    result_data = None
    error_message = None
    keyword = None

    if request.method == 'POST':
        keyword = request.form.get('keyword')
        if not keyword:
            error_message = "오류: 검색할 키워드를 입력해주세요."
        else:
            try:
                print(f"Fetching search volume for '{keyword}'...") # Server log
                # Call the function directly from the imported script
                result_data = get_monthly_search_volume(keyword)
                if result_data is None:
                    # Function might have printed an error, or keyword wasn't found
                    error_message = f"'{keyword}'에 대한 검색량 정보를 가져오지 못했거나 해당 키워드가 API 결과에 없습니다."
            except Exception as e:
                print(f"Search volume error: {e}") # Server log
                error_message = "오류: 검색량 조회 중 예기치 않은 오류가 발생했습니다."

    return render_template('feature2_search_volume.html',
                           result_data=result_data,
                           error_message=error_message,
                           keyword=keyword)

# --- Rank Tracking Feature Routes ---

def get_db_connection(db_name):
    """Helper function to get DB connection and cursor"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

@app.route('/manage_targets', methods=['GET', 'POST'])
@login_required
@subscription_required # <-- 데코레이터 추가
def manage_targets():
    """Manage the list of store/keyword pairs to track."""
    conn = get_db_connection(RANK_CHART_DB)
    cursor = conn.cursor()

    if request.method == 'POST':
        site_url = request.form.get('site_url') # Get URL instead of store name
        keyword = request.form.get('keyword')

        if not site_url or not keyword:
            flash("네이버 플레이스 URL과 키워드를 모두 입력해주세요.", "danger")
        else:
            # Extract store name from URL
            extracted_store_name = extract_restaurant_name(site_url)

            if extracted_store_name is None:
                flash("입력된 URL에서 가게 이름을 추출하지 못했습니다. URL을 확인해주세요.", "danger")
            else:
                try:
                    cursor.execute(
                        "INSERT INTO tracked_items (store_name, keyword) VALUES (?, ?)",
                        (extracted_store_name, keyword) # Save extracted name
                     )
                    conn.commit()
                    flash(f"'{extracted_store_name}' - '{keyword}' 항목 추가 완료. 초기 순위 기록 중...", "info") # Indicate rank fetching

                     # --- Immediately fetch and record the first rank ---
                    try:
                         initial_rank = update_single_rank(extracted_store_name, keyword)
                         if initial_rank is not None:
                             flash(f"초기 순위: {initial_rank}위", "success")
                         else:
                             flash("초기 순위: 100위 안에 없음 (또는 조회 오류)", "warning")
                    except Exception as e:
                         flash(f"초기 순위 조회 중 오류 발생: {e}", "danger")
                     # --- End initial rank fetch ---

                except sqlite3.IntegrityError:
                     flash(f"이미 '{extracted_store_name}' - '{keyword}' 조합으로 추적 중입니다.", "warning")
                except sqlite3.Error as e:
                    flash(f"데이터베이스 오류 발생: {e}", "danger")

        conn.close()
        return redirect(url_for('manage_targets')) # Redirect after POST
        flash(f"데이터베이스 오류 발생: {e}", "danger")

        conn.close()
        return redirect(url_for('manage_targets')) # Redirect after POST

    # GET request: Fetch and display current targets
    cursor.execute("SELECT id, store_name, keyword FROM tracked_items ORDER BY id DESC")
    tracked_items = cursor.fetchall()
    conn.close()
    return render_template('manage_targets.html', tracked_items=tracked_items, session=session)

@app.route('/delete_target/<int:item_id>', methods=['POST'])
@login_required
def delete_target(item_id):
    """Delete a tracked item."""
    conn = get_db_connection(RANK_CHART_DB)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tracked_items WHERE id = ?", (item_id,))
        # Optionally, delete related history from requests table too?
        # cursor.execute("DELETE FROM requests WHERE store_name = ? AND keyword = ?", (store_name, keyword)) # Need to fetch name/keyword first if doing this
        conn.commit()
        flash("추적 항목이 삭제되었습니다.", "success")
    except sqlite3.Error as e:
        flash(f"삭제 중 데이터베이스 오류 발생: {e}", "danger")
    finally:
        if conn:
            conn.close()
    return redirect(url_for('manage_targets'))

@app.route('/rank_history/<int:item_id>')
@login_required
@subscription_required
def rank_history(item_id):
    conn = None
    rank_data_map = {}
    store_name = "N/A"
    keyword = "N/A"
    date_list_31 = []
    display_range_str = ""

    try:
        conn = get_db_connection(RANK_CHART_DB)
        cursor = conn.cursor()

        cursor.execute("SELECT store_name, keyword FROM tracked_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            flash("해당 추적 항목을 찾을 수 없습니다.", "danger")
            return redirect(url_for('manage_targets'))

        store_name = item['store_name']
        keyword = item['keyword']

        today = datetime.date.today()
        date_list_31 = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, -1, -1)]
        start_date_str_obj = today - datetime.timedelta(days=30)
        display_range_str = f"{start_date_str_obj.strftime('%Y년 %m월 %d일')} ~ {today.strftime('%Y년 %m월 %d일')}"

        # rank, visitor_reviews, blog_reviews, saved_count 컬럼 조회
        cursor.execute(
            """
            SELECT DATE(date) as event_date, rank, visitor_reviews, blog_reviews, saved_count
            FROM requests r1
            WHERE store_name = ? AND keyword = ?
              AND DATE(r1.date) BETWEEN ? AND ?
              AND r1.rowid = (
                  SELECT r2.rowid
                  FROM requests r2
                  WHERE r2.store_name = r1.store_name
                    AND r2.keyword = r1.keyword
                    AND DATE(r2.date) = DATE(r1.date)
                  ORDER BY r2.date DESC
                  LIMIT 1
              )
            ORDER BY event_date ASC;
            """,
            (store_name, keyword, (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
        )
        history_data = cursor.fetchall()

        for record in history_data:
            event_date = record['event_date']
            rank_data_map[event_date] = {
                'rank': record['rank'],
                'visitor_reviews': record['visitor_reviews'],
                'blog_reviews': record['blog_reviews'],
                'saved_count': record['saved_count']  # << 저장하기 수 추가
            }

    except sqlite3.Error as e:
        flash(f"기록 조회 중 데이터베이스 오류 발생: {e}", "danger")
        return redirect(url_for('manage_targets'))
    except Exception as e:
         flash(f"기록 조회 중 오류 발생: {e}", "danger")
         return redirect(url_for('manage_targets'))
    finally:
        if conn:
            conn.close()

    return render_template('rank_history.html',
                           item_id=item_id,
                           store_name=store_name,
                           keyword=keyword,
                           rank_data_map=rank_data_map,
                           date_list_31=date_list_31,
                           display_range_str=display_range_str,
                           session=session)

# --- End Rank Tracking Feature Routes ---

# --- Toss Payments Routes ---

# 구독 신청 페이지 (결제 시작)
@app.route('/subscribe')
@login_required
def subscribe():
    user_id = session['user_id']
    # 관리자는 구독 불가
    if user_id == 'admin':
        flash("관리자는 구독 기능을 사용할 수 없습니다.", "warning")
        return redirect(url_for('home'))

    # 고유 주문 ID 생성
    order_id = toss_utils.generate_unique_order_id("sub_")

    # 템플릿에 전달할 정보
    payment_data = {
        "amount": config.SUBSCRIPTION_PRICE,
        "orderId": order_id,
        "orderName": config.SUBSCRIPTION_NAME,
        "customerName": user_id, # 사용자 이름 또는 식별자
        "customerKey": user_id, # 빌링키 발급 시 고객 식별용 키
        "successUrl": url_for('toss_callback_subscribe', _external=True),
        "failUrl": url_for('toss_fail', _external=True),
    }
    return render_template('subscribe.html',
                           client_key=config.TOSS_CLIENT_KEY,
                           payment_data=payment_data)

# 포인트 충전 페이지 (결제 시작)
@app.route('/charge-points')
@login_required
def charge_points():
    user_id = session['user_id']
    # 관리자는 충전 불가
    if user_id == 'admin':
        flash("관리자는 포인트 충전 기능을 사용할 수 없습니다.", "warning")
        return redirect(url_for('home'))

    # 고유 주문 ID 생성
    order_id = toss_utils.generate_unique_order_id("point_")

    # 템플릿에 전달할 정보
    payment_data = {
        "amount": config.POINT_PACKAGE_PRICE,
        "orderId": order_id,
        "orderName": config.POINT_PACKAGE_NAME,
        "customerName": user_id,
        "successUrl": url_for('toss_callback_charge', _external=True),
        "failUrl": url_for('toss_fail', _external=True),
    }
    return render_template('charge_points.html',
                           client_key=config.TOSS_CLIENT_KEY,
                           payment_data=payment_data)

# 구독 결제 성공 콜백
@app.route('/toss/callback/subscribe')
@login_required
def toss_callback_subscribe():
    payment_key = request.args.get('paymentKey')
    order_id = request.args.get('orderId')
    amount = request.args.get('amount')

    if not payment_key or not order_id or not amount:
        flash("결제 정보가 올바르지 않습니다.", "danger")
        return redirect(url_for('subscribe'))

    try:
        amount = int(amount)
    except ValueError:
        flash("결제 금액 정보가 올바르지 않습니다.", "danger")
        return redirect(url_for('subscribe'))

    # 가격 검증 (config.py와 비교)
    if amount != config.SUBSCRIPTION_PRICE:
         flash("결제 금액이 상품 가격과 일치하지 않습니다.", "danger")
         # 여기서는 결제 승인 전이므로 바로 실패 처리 가능
         return redirect(url_for('toss_fail', message="결제 금액 불일치"))

    # Toss Payments에 결제 승인 요청
    approval_response = toss_utils.request_toss_payment_approval(payment_key, order_id, amount)

    if approval_response and approval_response.get('status') == 'DONE':
        # 결제 성공 처리
        user_id = session['user_id']
        billing_key = approval_response.get('billingKey')
        customer_key = approval_response.get('customerKey') # customerKey 확인

        # customerKey가 현재 로그인 사용자와 일치하는지 확인 (보안 강화)
        if customer_key != user_id:
             flash("결제 정보의 사용자 ID가 일치하지 않습니다.", "danger")
             # TODO: 결제 취소 로직 필요 (승인된 결제 취소 API 호출)
             return redirect(url_for('toss_fail', message="사용자 ID 불일치"))


        if not billing_key:
             flash("빌링키 발급에 실패했습니다. 고객센터에 문의해주세요.", "danger")
             # TODO: 결제 취소 로직 필요
             return redirect(url_for('toss_fail', message="빌링키 발급 실패"))

        # DB 업데이트
        conn = None
        try:
            conn = sqlite3.connect(USERS_DB)
            cursor = conn.cursor()
            # 구독 만료일 계산 (예: 1개월 후)
            expiry_date = datetime.datetime.now() + datetime.timedelta(days=30) # 단순 30일로 계산
            expiry_date_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                UPDATE users
                SET subscription_status = ?, subscription_expiry = ?, toss_billing_key = ?
                WHERE username = ?
            """, ('active', expiry_date_str, billing_key, user_id))
            conn.commit()

            flash("구독이 성공적으로 활성화되었습니다!", "success")
            return redirect(url_for('payment_success')) # 성공 페이지로 리디렉션

        except sqlite3.Error as e:
            flash(f"DB 업데이트 중 오류 발생: {e}", "danger")
            # TODO: 결제 취소 로직 필요
            return redirect(url_for('toss_fail', message="DB 오류"))
        finally:
            if conn:
                conn.close()

    else:
        # 결제 승인 실패
        error_msg = approval_response.get('message', '알 수 없는 오류') if approval_response else '승인 요청 실패'
        error_code = approval_response.get('code', 'UNKNOWN') if approval_response else 'REQUEST_FAIL'
        flash(f"결제 승인에 실패했습니다: {error_msg} ({error_code})", "danger")
        return redirect(url_for('toss_fail', message=error_msg, code=error_code))


# 포인트 충전 성공 콜백
@app.route('/toss/callback/charge')
@login_required
def toss_callback_charge():
    payment_key = request.args.get('paymentKey')
    order_id = request.args.get('orderId')
    amount = request.args.get('amount')

    if not payment_key or not order_id or not amount:
        flash("결제 정보가 올바르지 않습니다.", "danger")
        return redirect(url_for('charge_points'))

    try:
        amount = int(amount)
    except ValueError:
        flash("결제 금액 정보가 올바르지 않습니다.", "danger")
        return redirect(url_for('charge_points'))

    # 가격 검증
    if amount != config.POINT_PACKAGE_PRICE:
         flash("결제 금액이 상품 가격과 일치하지 않습니다.", "danger")
         return redirect(url_for('toss_fail', message="결제 금액 불일치"))

    # Toss Payments에 결제 승인 요청
    approval_response = toss_utils.request_toss_payment_approval(payment_key, order_id, amount)

    if approval_response and approval_response.get('status') == 'DONE':
        # 결제 성공 처리
        user_id = session['user_id']

        # DB 업데이트 (포인트 추가)
        conn = None
        try:
            conn = sqlite3.connect(USERS_DB)
            cursor = conn.cursor()
            # 포인트 추가 (기존 포인트 + 충전량)
            cursor.execute("UPDATE users SET points = points + ? WHERE username = ?",
                           (config.POINT_PACKAGE_AMOUNT, user_id))
            conn.commit()

            flash(f"{config.POINT_PACKAGE_AMOUNT} 포인트가 성공적으로 충전되었습니다!", "success")
            return redirect(url_for('payment_success'))

        except sqlite3.Error as e:
            flash(f"포인트 충전 중 DB 오류 발생: {e}", "danger")
            # TODO: 결제 취소 로직 필요
            return redirect(url_for('toss_fail', message="DB 오류"))
        finally:
            if conn:
                conn.close()
    else:
        # 결제 승인 실패
        error_msg = approval_response.get('message', '알 수 없는 오류') if approval_response else '승인 요청 실패'
        error_code = approval_response.get('code', 'UNKNOWN') if approval_response else 'REQUEST_FAIL'
        flash(f"결제 승인에 실패했습니다: {error_msg} ({error_code})", "danger")
        return redirect(url_for('toss_fail', message=error_msg, code=error_code))


# 결제 실패 페이지
@app.route('/toss/fail')
def toss_fail():
    message = request.args.get('message', '알 수 없는 이유로 결제에 실패했습니다.')
    code = request.args.get('code')
    return render_template('payment_fail.html', message=message, code=code)

# 결제 성공 페이지
@app.route('/payment/success')
@login_required
def payment_success():
    return render_template('payment_success.html')


# Toss Payments 웹훅 수신 엔드포인트
@app.route('/toss/webhook', methods=['POST'])
def toss_webhook():
    # 1. 서명 검증
    signature = request.headers.get('TossPayments-Signature')
    request_body = request.data # raw body (bytes)

    if not toss_utils.verify_toss_webhook_signature(request_body, signature):
        print("웹훅 서명 검증 실패")
        return jsonify({"status": "forbidden"}), 403

    # 2. 이벤트 데이터 파싱
    try:
        event_data = json.loads(request_body.decode('utf-8'))
        event_type = event_data.get('eventType')
        data = event_data.get('data')
        print(f"웹훅 수신: {event_type}") # 로깅
    except json.JSONDecodeError:
        print("웹훅 데이터 파싱 실패")
        return jsonify({"status": "bad_request"}), 400

        # 3. 이벤트 타입별 처리
    if event_type == 'PAYMENT_STATUS_CHANGED':
        status = data.get('status')
        order_id = data.get('orderId')
        payment_key = data.get('paymentKey')
        # >>> 추가: customerKey 추출 시도 <<<
        customer_key = data.get('customerKey') # 사용자 식별을 위해 필요

        print(f"결제 상태 변경: orderId={order_id}, status={status}, customerKey={customer_key}") # 로깅 강화

        if status == 'CANCELED':
            # 결제 취소 처리 (예: 구독 비활성화)
            # orderId 또는 paymentKey를 사용하여 관련 사용자 정보 업데이트
            # 예시: orderId가 'sub_'로 시작하면 구독 관련 처리
            # >>> 수정 시작: pass 부분을 아래 로직으로 교체 <<<
            if customer_key: # customerKey가 웹훅 데이터에 포함된 경우
                conn = None
                try:
                    print(f"결제 취소 처리 시작: 사용자 ID = {customer_key}")
                    conn = sqlite3.connect(USERS_DB)
                    cursor = conn.cursor()
                    # 해당 사용자의 구독 상태를 비활성화하고 만료일 제거
                    cursor.execute("""
                        UPDATE users
                        SET subscription_status = ?, subscription_expiry = NULL
                        WHERE username = ? AND subscription_status = ?
                    """, ('inactive', customer_key, 'active')) # 현재 active인 경우만 inactive로 변경
                    
                    updated_rows = cursor.rowcount # 영향받은 행 수 확인
                    conn.commit()
                    
                    if updated_rows > 0:
                         print(f"사용자 {customer_key}의 구독 상태가 'inactive'로 업데이트되었습니다. (결제 취소)")
                    else:
                         print(f"사용자 {customer_key}를 찾지 못했거나 이미 비활성 상태입니다. (결제 취소)")

                except sqlite3.Error as e:
                    print(f"결제 취소 처리 중 DB 오류 발생 (사용자: {customer_key}): {e}")
                    # 오류 발생 시 Toss에 5xx 에러를 반환하여 재시도 유도 가능 (선택적)
                    # return jsonify({"status": "error", "message": "DB error"}), 500
                finally:
                    if conn:
                        conn.close()
            else:
                 # customerKey가 없는 경우, 다른 방법으로 사용자 식별 필요
                 # 예를 들어, 결제 성공 시 paymentKey나 orderId를 별도 테이블에 저장하고 조회
                 print(f"경고: 결제 취소 웹훅에 customerKey가 없습니다. (orderId: {order_id}). 사용자 식별 로직 추가 필요.")
            # >>> 수정 끝 <<<
            pass # 원래 있던 pass는 제거하거나 주석 처리
        elif status == 'PARTIAL_CANCELED':
            # 부분 취소 처리 (이 프로젝트에서는 해당 없을 수 있음)
            print(f"부분 결제 취소 이벤트 수신 (처리 로직 필요): orderId={order_id}")
            pass
        # 기타 상태 처리 (ABORTED, EXPIRED 등)
        elif status in ['ABORTED', 'EXPIRED']:
             print(f"결제 상태 {status} 이벤트 수신 (처리 로직 필요 시 추가): orderId={order_id}")
             # 필요 시 관련 처리 로직 추가
             pass

    
        # ...(기존 빌링키 상태 변경 처리 로직 유지)...
    elif event_type == 'BILLING_STATUS_CHANGED':
        status = data.get('status')
        billing_key = data.get('billingKey')
        customer_key = data.get('customerKey') # 사용자 식별자

        print(f"빌링키 상태 변경: customerKey={customer_key}, status={status}")

        if status == 'INACTIVE':
            # 빌링키 비활성화 처리 (예: 카드 만료, 삭제 등)
            # customer_key (user_id)를 사용하여 해당 사용자의 구독 상태 변경
            conn = None
            try:
                 conn = sqlite3.connect(USERS_DB)
                 cursor = conn.cursor()
                 cursor.execute("UPDATE users SET subscription_status = 'inactive', toss_billing_key = NULL WHERE username = ?", (customer_key,))
                 conn.commit()
                 print(f"사용자 {customer_key}의 빌링키 비활성화 및 구독 상태 변경 완료")
            except sqlite3.Error as e:
                 print(f"빌링키 비활성화 처리 중 DB 오류: {e}")
            finally:
                 if conn:
                     conn.close()
            pass

    # 기타 필요한 이벤트 타입 처리 (예: METHOD_CHANGED, CUSTOMER_STATUS_CHANGED)

    # Toss Payments에 정상 수신 응답 전달
    return jsonify({"status": "success"}), 200


# --- End Toss Payments Routes ---

@app.route('/download_today_requests')
@login_required
def download_today_requests():
    # --- 권한 확인 (관리자만 다운로드 가능하도록) ---
    if session.get('user_id') != 'admin':
        flash("다운로드 권한이 없습니다.", "danger")
        return redirect(url_for('account'))

    conn = None
    try:
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        conn = get_db_connection(REQUESTS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests WHERE DATE(sub_time) = ?", (today_str,))
        requests_today = cursor.fetchall()

        # --- CSV 데이터 생성 ---
        output = io.StringIO()
        writer = csv.writer(output)

        # CSV 헤더 작성 (컬럼명 및 순서 유지 또는 변경 가능)
        header = ['ID', 'Name', 'Keyword', 'Merchandise', 'Service', 'Traffic Amount', 'Submission Time', 'State', 'Link', 'User ID']
        writer.writerow(header)

        # 데이터 행 작성
        for row in requests_today:
            # --- 요청하신 변환 로직 적용 ---
            # merchandise: 1이면 '저장하기', 0이면 '해당 없음'
            merchandise_str = "네이버 플레이스" if row['merchandise'] == 1 else "해당 없음"

            # service: 1이면 '저장하기', 2이면 '트래픽', 그 외는 '알 수 없음'
            service_str = "" # 기본값 초기화
            if row['service'] == 1:
                service_str = "저장하기"
            elif row['service'] == 2:
                service_str = "트래픽"
            else:
                service_str = "알 수 없음" # 예상치 못한 값 처리
            # --- 변환 로직 끝 ---

            writer.writerow([
                row['id'],
                row['name'],
                row['keyword'],
                merchandise_str, # 변환된 값 사용
                service_str,     # 변환된 값 사용
                row['traffic_amount'] if row['traffic_amount'] is not None else '',
                row['sub_time'],
                row['state'],
                row['link'] if row['link'] is not None else '',
                row['user_id']
            ])

        output.seek(0)

        filename = f"requests_{today_str}.csv"
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    except sqlite3.Error as e:
        flash(f"데이터베이스 조회 중 오류 발생: {e}", "danger")
        return redirect(url_for('account'))
    except Exception as e:
        flash(f"CSV 생성 중 오류 발생: {e}", "danger")
        return redirect(url_for('account'))
    finally:
        if conn:
            conn.close()




if __name__ == '__main__':
    app.run(debug=True)
