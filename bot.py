import random
import string
import json
import time
import requests
import uuid
import pyotp
import base64
import io
import struct
from threading import Thread
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
import telebot
from flask import Flask

# ==========================================
# PHẦN LOGIC (GIỮ NGUYÊN TỪ MÃ NGUỒN GỐC)[span_1](start_span)[span_1](end_span)
# ==========================================

class FacebookPasswordEncryptor:
    @staticmethod
    def get_public_key():
        try:
            url = 'https://b-graph.facebook.com/pwd_key_fetch'
            params = {
                'version': '2',
                'flow': 'CONTROLLER_INITIALIZATION',
                'method': 'GET',
                'fb_api_req_friendly_name': 'pwdKeyFetch',
                'fb_api_caller_class': 'com.facebook.auth.login.AuthOperations',
                'access_token': '438142079694454|fc0a7caa49b192f64f6f5a6d9643bb28'
            }
            response = requests.post(url, params=params).json()
            return response.get('public_key'), str(response.get('key_id', '25'))
        except Exception as e:
            raise Exception(f"Không thể lấy public key: {e}")

    @staticmethod
    def encrypt(password, public_key=None, key_id="25"):
        if public_key is None:
            public_key, key_id = FacebookPasswordEncryptor.get_public_key()

        try:
            rand_key = get_random_bytes(32)
            iv = get_random_bytes(12)
            
            pubkey = RSA.import_key(public_key)
            cipher_rsa = PKCS1_v1_5.new(pubkey)
            encrypted_rand_key = cipher_rsa.encrypt(rand_key)
            
            cipher_aes = AES.new(rand_key, AES.MODE_GCM, nonce=iv)
            current_time = int(time.time())
            cipher_aes.update(str(current_time).encode("utf-8"))
            encrypted_passwd, auth_tag = cipher_aes.encrypt_and_digest(password.encode("utf-8"))
            
            buf = io.BytesIO()
            buf.write(bytes([1, int(key_id)]))
            buf.write(iv)
            buf.write(struct.pack("<h", len(encrypted_rand_key)))
            buf.write(encrypted_rand_key)
            buf.write(auth_tag)
            buf.write(encrypted_passwd)
            
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"#PWD_FB4A:2:{current_time}:{encoded}"
        except Exception as e:
            raise Exception(f"Lỗi khi mã hóa mật khẩu: {e}")


class FacebookAppTokens:
    APPS = {
        'FB_ANDROID': {'name': 'Facebook For Android', 'app_id': '350685531728'},
        'MESSENGER_ANDROID': {'name': 'Facebook Messenger For Android', 'app_id': '256002347743983'},
        'FB_LITE': {'name': 'Facebook For Lite', 'app_id': '275254692598279'},
        'MESSENGER_LITE': {'name': 'Facebook Messenger For Lite', 'app_id': '200424423651082'},
        'ADS_MANAGER_ANDROID': {'name': 'Ads Manager App For Android', 'app_id': '438142079694454'},
        'PAGES_MANAGER_ANDROID': {'name': 'Pages Manager For Android', 'app_id': '121876164619130'}
    }
    
    @staticmethod
    def get_app_id(app_key):
        app = FacebookAppTokens.APPS.get(app_key)
        return app['app_id'] if app else None
    
    @staticmethod
    def extract_token_prefix(token):
        for i, char in enumerate(token):
            if char.islower():
                return token[:i]
        return token


class FacebookLogin:
    API_URL = "https://b-graph.facebook.com/auth/login"
    ACCESS_TOKEN = "350685531728|62f8ce9f74b12f84c123cc23437a4a32"
    API_KEY = "882a8490361da98702bf97a021ddc14d"
    SIG = "214049b9f17c38bd767de53752b53946"
    
    BASE_HEADERS = {
        "content-type": "application/x-www-form-urlencoded",
        "x-fb-net-hni": "45201",
        "zero-rated": "0",
        "x-fb-sim-hni": "45201",
        "x-fb-connection-quality": "EXCELLENT",
        "x-fb-friendly-name": "authenticate",
        "x-fb-connection-bandwidth": "78032897",
        "x-tigon-is-retry": "False",
        "authorization": "OAuth null",
        "x-fb-connection-type": "WIFI",
        "x-fb-device-group": "3342",
        "priority": "u=3,i",
        "x-fb-http-engine": "Liger",
        "x-fb-client-ip": "True",
        "x-fb-server-cluster": "True"
    }
    
    def __init__(self, uid_phone_mail, password, twwwoo2fa="", convert_all_tokens=False):
        self.uid_phone_mail = uid_phone_mail
        self.twwwoo2fa = twwwoo2fa
        
        if password.startswith("#PWD_FB4A"):
            self.password = password
        else:
            self.password = FacebookPasswordEncryptor.encrypt(password)
        
        self.convert_token_to = FacebookAppTokens.get_all_app_keys() if convert_all_tokens else []
        self.session = requests.Session()
        
        self.device_id = str(uuid.uuid4())
        self.adid = str(uuid.uuid4())
        self.secure_family_device_id = str(uuid.uuid4())
        self.machine_id = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
        self.jazoest = ''.join(random.choices(string.digits, k=5))
        self.sim_serial = ''.join(random.choices(string.digits, k=20))
        
        self.headers = self._build_headers()
        self.data = self._build_data()
    
    def _build_headers(self):
        headers = self.BASE_HEADERS.copy()
        headers.update({
            "x-fb-request-analytics-tags": '{"network_tags":{"product":"350685531728","retry_attempt":"0"},"application_tags":"unknown"}',
            "user-agent": "Dalvik/2.1.0 (Linux; U; Android 9; 23113RKC6C Build/PQ3A.190705.08211809) [FBAN/FB4A;FBAV/417.0.0.33.65;FBPN/com.facebook.katana;FBLC/vi_VN;FBBV/480086274;FBCR/MobiFone;FBMF/Redmi;FBBD/Redmi;FBDV/23113RKC6C;FBSV/9;FBCA/x86:armeabi-v7a;FBDM/{density=1.5,width=1280,height=720};FB_FW/1;FBRV/0;]"
        })
        return headers
    
    def _build_data(self):
        return {
            "format": "json",
            "email": self.uid_phone_mail,
            "password": self.password,
            "credentials_type": "password",
            "generate_session_cookies": "1",
            "locale": "vi_VN",
            "client_country_code": "VN",
            "api_key": self.API_KEY,
            "access_token": self.ACCESS_TOKEN,
            "adid": self.adid,
            "device_id": self.device_id,
            "generate_analytics_claim": "1",
            "community_id": "",
            "linked_guest_account_userid": "",
            "cpl": "true",
            "try_num": "1",
            "family_device_id": self.device_id,
            "secure_family_device_id": self.secure_family_device_id,
            "sim_serials": f'["{self.sim_serial}"]',
            "openid_flow": "android_login",
            "openid_provider": "google",
            "openid_tokens": "[]",
            "account_switcher_uids": f'["{self.uid_phone_mail}"]',
            "enroll_misauth": "false",
            "error_detail_type": "button_with_disabled",
            "source": "login",
            "machine_id": self.machine_id,
            "jazoest": self.jazoest,
            "meta_inf_fbmeta": "V2_UNTAGGED",
            "advertiser_id": self.adid,
            "encrypted_msisdn": "",
            "currently_logged_in_userid": "0",
            "fb_api_req_friendly_name": "authenticate",
            "fb_api_caller_class": "Fb4aAuthHandler",
            "sig": self.SIG
        }
    
    def _handle_2fa(self, error_data):
        if not self.twwwoo2fa:
            return {'success': False, 'error': 'Cần mã 2FA nhưng chưa được cung cấp'}
        try:
            twofactor_code = pyotp.TOTP(self.twwwoo2fa).now()
            data_2fa = {
                'locale': 'vi_VN', 'format': 'json', 'email': self.uid_phone_mail,
                'device_id': self.device_id, 'access_token': self.ACCESS_TOKEN,
                'generate_session_cookies': 'true', 'generate_machine_id': '1',
                'twofactor_code': twofactor_code, 'credentials_type': 'two_factor',
                'error_detail_type': 'button_with_disabled',
                'first_factor': error_data['login_first_factor'],
                'password': self.password, 'userid': error_data['uid'],
                'machine_id': error_data['login_first_factor']
            }
            response = self.session.post(self.API_URL, data=data_2fa, headers=self.headers)
            res_json = response.json()
            if 'access_token' in res_json:
                return {'success': True, 'access_token': res_json.get('access_token')}
            return {'success': False, 'error': res_json.get('error', {}).get('message', '2FA Error')}
        except Exception as e:
            return {'success': False, 'error': f'Lỗi 2FA: {str(e)}'}
    
    def login(self):
        try:
            response = self.session.post(self.API_URL, headers=self.headers, data=self.data)
            res_json = response.json()
            if 'access_token' in res_json:
                return {'success': True, 'access_token': res_json.get('access_token')}
            if 'error' in res_json:
                err_data = res_json.get('error', {}).get('error_data', {})
                if 'login_first_factor' in err_data and 'uid' in err_data:
                    return self._handle_2fa(err_data)
                return {'success': False, 'error': res_json['error'].get('message', 'Unknown error')}
            return {'success': False, 'error': 'Unknown response format'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ==========================================
# PHẦN TELEGRAM BOT
# ==========================================

TOKEN = "8526195684:AAFbpznz8LijazNo7J7uelbLQsVOcoXTkac"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "🤖 **Facebook Token Tool Bot**\n\n"
        "👉 **Cách dùng đơn giản:**\n"
        "Gửi lệnh theo cú pháp:\n"
        "`/login uid|password|2fa_key`\n\n"
        "⚡ Hoặc **gửi file .txt** chứa danh sách tài khoản (định dạng `uid|pass|2fa`) trực tiếp vào đây để check hàng loạt!"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['login'])
def handle_login(message):
    try:
        parts = message.text.replace('/login', '').strip().split('|')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Sai cú pháp! Vui lòng dùng: `/login uid|password|2fa_key`", parse_mode="Markdown")
            return
        
        uid = parts[0].strip()
        pwd = parts[1].strip()
        twofa = parts[2].strip().replace(" ", "") if len(parts) > 2 else ""
        
        bot.reply_to(message, f"⏳ Đang xử lý đăng nhập cho UID: `{uid}`...", parse_mode="Markdown")
        
        fb = FacebookLogin(uid_phone_mail=uid, password=pwd, twwwoo2fa=twofa)
        res = fb.login()
        
        if res['success']:
            out = f"✅ **Đăng nhập thành công!**\n\n`{res['access_token']}`"
            bot.reply_to(message, out, parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ **Thất bại:** {res.get('error')}", parse_mode="Markdown")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi hệ thống: {str(e)}")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        lines = downloaded_file.decode('utf-8').splitlines()
        bot.reply_to(message, f"📂 Đã nhận file với {len(lines)} dòng. Đang tiến hành check hàng loạt...")
        
        success_tokens = []
        for line in lines:
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|')
            uid = parts[0].strip()
            pwd = parts[1].strip()
            twofa = parts[2].strip().replace(" ", "") if len(parts) > 2 else ""
            
            try:
                fb = FacebookLogin(uid_phone_mail=uid, password=pwd, twwwoo2fa=twofa)
                res = fb.login()
                if res['success']:
                    success_tokens.append(res['access_token'])
            except:
                pass
                
        # Gửi file kết quả trả về cho người dùng
        output_io = io.BytesIO('\n'.join(success_tokens).encode('utf-8'))
        output_io.name = f"tokens_result_{int(time.time())}.txt"
        output_io.seek(0)
        bot.send_document(message.chat.id, output_io, caption=f"🎉 Hoàn tất! Lấy thành công {len(success_tokens)} token.")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý file: {str(e)}")


# ==========================================
# FLASK SERVER (ĐỂ TREO TRÊN RENDER 24/7)
# ==========================================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app_web.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    # Chạy Web server ở background thread
    Thread(target=run_flask, daemon=True).start()
    # Chạy Telegram Bot
    bot.infinity_polling()
