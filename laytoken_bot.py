import os
import sys
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
import asyncio
import tempfile
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

try:
    from telegram import Update, InputFile
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes,
    )
    from telegram.constants import ParseMode
except ImportError:
    print("Thieu thu vien telegram. Chay: pip install python-telegram-bot==21.6")
    raise


# ==========================================
# PHAN LOGIC (GIU NGUYEN 100%)
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
            raise Exception(f"Khong the lay public key: {e}")

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
            raise Exception(f"Loi khi ma hoa mat khau: {e}")


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
    def get_all_app_keys():
        return list(FacebookAppTokens.APPS.keys())

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

    def __init__(self, uid_phone_mail, password, twwwoo2fa="", machine_id=None, convert_token_to=None, convert_all_tokens=False):
        self.uid_phone_mail = uid_phone_mail
        self.twwwoo2fa = twwwoo2fa

        if password.startswith("#PWD_FB4A"):
            self.password = password
        else:
            self.password = FacebookPasswordEncryptor.encrypt(password)

        if convert_all_tokens:
            self.convert_token_to = FacebookAppTokens.get_all_app_keys()
        elif convert_token_to:
            self.convert_token_to = convert_token_to if isinstance(convert_token_to, list) else [convert_token_to]
        else:
            self.convert_token_to = []

        self.session = requests.Session()

        self.device_id = str(uuid.uuid4())
        self.adid = str(uuid.uuid4())
        self.secure_family_device_id = str(uuid.uuid4())
        self.machine_id = machine_id if machine_id else self._generate_machine_id()
        self.jazoest = ''.join(random.choices(string.digits, k=5))
        self.sim_serial = ''.join(random.choices(string.digits, k=20))

        self.headers = self._build_headers()
        self.data = self._build_data()

    @staticmethod
    def _generate_machine_id():
        return ''.join(random.choices(string.ascii_letters + string.digits, k=24))

    def _build_headers(self):
        headers = self.BASE_HEADERS.copy()
        headers.update({
            "x-fb-request-analytics-tags": '{"network_tags":{"product":"350685531728","retry_attempt":"0"},"application_tags":"unknown"}',
            "user-agent": "Dalvik/2.1.0 (Linux; U; Android 9; 23113RKC6C Build/PQ3A.190705.08211809) [FBAN/FB4A;FBAV/417.0.0.33.65;FBPN/com.facebook.katana;FBLC/vi_VN;FBBV/480086274;FBCR/MobiFone;FBMF/Redmi;FBBD/Redmi;FBDV/23113RKC6C;FBSV/9;FBCA/x86:armeabi-v7a;FBDM/{density=1.5,width=1280,height=720};FB_FW/1;FBRV/0;]"
        })
        return headers

    def _build_data(self):
        base_data = {
            "format": "json",
            "email": self.uid_phone_mail,
            "password": self.password,
            "credentials_type": "password",
            "generate_session_cookies": "1",
            "locale": "vi_VN",
            "client_country_code": "VN",
            "api_key": self.API_KEY,
            "access_token": self.ACCESS_TOKEN
        }

        base_data.update({
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
            "fb4a_shared_phone_cpl_experiment": "fb4a_shared_phone_nonce_cpl_at_risk_v3",
            "fb4a_shared_phone_cpl_group": "enable_v3_at_risk",
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
        })

        return base_data

    def _convert_token(self, access_token, target_app):
        try:
            app_id = FacebookAppTokens.get_app_id(target_app)
            if not app_id:
                return None

            response = requests.post(
                'https://api.facebook.com/method/auth.getSessionforApp',
                data={
                    'access_token': access_token,
                    'format': 'json',
                    'new_app_id': app_id,
                    'generate_session_cookies': '1'
                }
            )

            result = response.json()

            if 'access_token' in result:
                token = result['access_token']
                prefix = FacebookAppTokens.extract_token_prefix(token)

                cookies_dict = {}
                cookies_string = ""

                if 'session_cookies' in result:
                    for cookie in result['session_cookies']:
                        cookies_dict[cookie['name']] = cookie['value']
                        cookies_string += f"{cookie['name']}={cookie['value']}; "

                return {
                    'token_prefix': prefix,
                    'access_token': token,
                    'cookies': {
                        'dict': cookies_dict,
                        'string': cookies_string.rstrip('; ')
                    }
                }

            return None

        except:
            return None

    def _parse_success_response(self, response_json):
        original_token = response_json.get('access_token')
        original_prefix = FacebookAppTokens.extract_token_prefix(original_token)

        result = {
            'success': True,
            'original_token': {
                'token_prefix': original_prefix,
                'access_token': original_token
            },
            'cookies': {}
        }

        if 'session_cookies' in response_json:
            cookies_dict = {}
            cookies_string = ""
            for cookie in response_json['session_cookies']:
                cookies_dict[cookie['name']] = cookie['value']
                cookies_string += f"{cookie['name']}={cookie['value']}; "
            result['cookies'] = {
                'dict': cookies_dict,
                'string': cookies_string.rstrip('; ')
            }

        if self.convert_token_to:
            result['converted_tokens'] = {}
            for target_app in self.convert_token_to:
                converted = self._convert_token(original_token, target_app)
                if converted:
                    result['converted_tokens'][target_app] = converted

        return result

    def _handle_2fa(self, error_data):
        if not self.twwwoo2fa:
            return {'success': False, 'error': 'Can ma 2FA nhung chua duoc cung cap'}

        try:
            twofactor_code = pyotp.TOTP(self.twwwoo2fa).now()

            data_2fa = {
                'locale': 'vi_VN',
                'format': 'json',
                'email': self.uid_phone_mail,
                'device_id': self.device_id,
                'access_token': self.ACCESS_TOKEN,
                'generate_session_cookies': 'true',
                'generate_machine_id': '1',
                'twofactor_code': twofactor_code,
                'credentials_type': 'two_factor',
                'error_detail_type': 'button_with_disabled',
                'first_factor': error_data['login_first_factor'],
                'password': self.password,
                'userid': error_data['uid'],
                'machine_id': error_data['login_first_factor']
            }

            response = self.session.post(self.API_URL, data=data_2fa, headers=self.headers)
            response_json = response.json()

            if 'access_token' in response_json:
                return self._parse_success_response(response_json)
            elif 'error' in response_json:
                return {
                    'success': False,
                    'error': response_json['error'].get('message', 'Unknown error')
                }

        except Exception as e:
            return {'success': False, 'error': f'Loi 2FA: {str(e)}'}

    def login(self):
        try:
            response = self.session.post(self.API_URL, headers=self.headers, data=self.data)
            response_json = response.json()

            if 'access_token' in response_json:
                return self._parse_success_response(response_json)

            if 'error' in response_json:
                error_data = response_json.get('error', {}).get('error_data', {})

                if 'login_first_factor' in error_data and 'uid' in error_data:
                    return self._handle_2fa(error_data)

                return {
                    'success': False,
                    'error': response_json['error'].get('message', 'Unknown error'),
                    'error_user_msg': response_json['error'].get('error_user_msg')
                }

            return {'success': False, 'error': 'Unknown response format'}

        except json.JSONDecodeError:
            return {'success': False, 'error': 'Response khong phai JSON hop le'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ==========================================
# PHAN TELEGRAM BOT
# ==========================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
ALLOWED_USER_IDS = [int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()]


def authorized(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return update.effective_user.id in ALLOWED_USER_IDS


def parse_account_args(args_text: str):
    """Parse 'uid|pass' or 'uid|pass|2fa' or 'uid|pass|2fa|machine_id'."""
    parts = args_text.strip().split("|")
    if len(parts) < 2:
        return None
    uid = parts[0].strip()
    pwd = parts[1].strip()
    tfa = parts[2].strip().replace(" ", "") if len(parts) >= 3 else ""
    machine_id = parts[3].strip() if len(parts) >= 4 else ""
    if not uid or not pwd:
        return None
    return uid, pwd, tfa, machine_id


def do_login(uid, pwd, tfa, machine_id, convert_all, convert_list):
    """Run login synchronously (called via asyncio.to_thread)."""
    fb = FacebookLogin(
        uid_phone_mail=uid,
        password=pwd,
        twwwoo2fa=tfa,
        machine_id=machine_id if machine_id else None,
        convert_token_to=convert_list,
        convert_all_tokens=convert_all
    )
    return fb.login()


def format_result_text(result):
    """Format the result into a human-readable HTML message."""
    lines = []
    if result.get('success'):
        lines.append("✅ <b>LOGIN THANH CONG</b>")
        lines.append("")
        lines.append(f"🔹 <b>{result['original_token']['token_prefix']}</b>")
        lines.append(f"<code>{result['original_token']['access_token']}</code>")

        if result.get('converted_tokens'):
            lines.append("")
            lines.append("🔁 <b>CONVERTED TOKENS:</b>")
            for app_key, td in result['converted_tokens'].items():
                lines.append("")
                lines.append(f"🔸 <b>{td['token_prefix']}</b> ({app_key})")
                lines.append(f"<code>{td['access_token']}</code>")

        if result.get('cookies', {}).get('string'):
            lines.append("")
            lines.append("🍪 <b>COOKIES:</b>")
            lines.append(f"<code>{result['cookies']['string']}</code>")
    else:
        lines.append("❌ <b>LOGIN THAT BAI</b>")
        lines.append(f"Error: <code>{result.get('error', 'Unknown')}</code>")
        if result.get('error_user_msg'):
            lines.append(f"Msg: <code>{result.get('error_user_msg')}</code>")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await update.message.reply_text("⛔ Ban khong co quyen su dung bot nay.")
        return
    msg = (
        "🤖 <b>FACEBOOK LOGIN BOT</b>\n\n"
        "Bot lay Facebook access token &amp; cookies.\n\n"
        "<b>Lenh:</b>\n"
        "/login <code>uid|pass</code> — Dang nhap thu cong\n"
        "/login <code>uid|pass|2fa</code> — Co ma 2FA (TOTP secret)\n"
        "/login <code>uid|pass|2fa|machine_id</code> — Co ca machine_id\n"
        "/convert_all <code>uid|pass</code> — Convert token sang tat ca app\n"
        "/convert <code>APP_KEY uid|pass</code> — Convert sang 1 app\n"
        "/apps — Xem danh sach app ho tro\n"
        "/help — Huong dan day du\n\n"
        "<b>Batch mode:</b> Gui file <code>.txt</code> moi dong dang <code>uid|pass</code>, "
        "bot se tra ve file token."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    msg = (
        "📖 <b>HUONG DAN</b>\n\n"
        "<b>1) Dang nhap don:</b>\n"
        "/login <code>uid|pass</code>\n"
        "Vi du: /login <code>100000123|matkhau123</code>\n\n"
        "<b>2) Co 2FA (TOTP secret 32 ky tu):</b>\n"
        "/login <code>uid|pass|JBSWY3DPEHPK3PXP</code>\n\n"
        "<b>3) Co 2FA + Machine ID:</b>\n"
        "/login <code>uid|pass|2fa|machine_id</code>\n\n"
        "<b>4) Convert sang tat ca app:</b>\n"
        "/convert_all <code>uid|pass</code>\n\n"
        "<b>5) Convert sang 1 app cu the:</b>\n"
        "/convert <code>FB_LITE uid|pass</code>\n\n"
        "<b>6) Xem app ho tro:</b>\n"
        "/apps\n\n"
        "<b>7) Check hang loat (batch):</b>\n"
        "• Gui file <code>.txt</code> cho bot\n"
        "• Moi dong dang <code>uid|pass</code> (hoac <code>uid|pass|2fa</code>)\n"
        "• Bot tra ve file <code>tokens.txt</code> moi dong 1 token\n\n"
        "⚠️ <i>Neu muon batch kem 2FA, dung format: uid|pass|2fa</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    lines = ["📱 <b>DANH SACH APP</b>\n"]
    for key, info in FacebookAppTokens.APPS.items():
        lines.append(f"• <code>{key}</code> — {info['name']} (app_id: {info['app_id']})")
    lines.append("\nDung key trong lenh /convert <code>APP_KEY uid|pass</code>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    args_text = " ".join(context.args).strip() if context.args else ""
    parsed = parse_account_args(args_text)
    if not parsed:
        await update.message.reply_text(
            "❌ Sai cu phap.\n"
            "Dung: /login <code>uid|pass</code>\n"
            "Hoac: /login <code>uid|pass|2fa</code>\n"
            "Hoac: /login <code>uid|pass|2fa|machine_id</code>",
            parse_mode=ParseMode.HTML
        )
        return
    uid, pwd, tfa, machine_id = parsed

    wait_msg = await update.message.reply_text("⏳ Dang dang nhap...")
    try:
        result = await asyncio.to_thread(do_login, uid, pwd, tfa, machine_id, False, None)
        text = format_result_text(result)
        # Telegram message limit ~4096 chars
        if len(text) > 4000:
            await wait_msg.delete()
            await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)
            await update.message.reply_text(text[4000:], parse_mode=ParseMode.HTML)
        else:
            await wait_msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Loi he thong: <code>{e}</code>", parse_mode=ParseMode.HTML)


async def cmd_convert_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    args_text = " ".join(context.args).strip() if context.args else ""
    parsed = parse_account_args(args_text)
    if not parsed:
        await update.message.reply_text(
            "❌ Sai cu phap.\nDung: /convert_all <code>uid|pass</code>",
            parse_mode=ParseMode.HTML
        )
        return
    uid, pwd, tfa, machine_id = parsed

    wait_msg = await update.message.reply_text("⏳ Dang dang nhap &amp; convert tat ca app...")
    try:
        result = await asyncio.to_thread(do_login, uid, pwd, tfa, machine_id, True, None)
        text = format_result_text(result)
        if len(text) > 4000:
            await wait_msg.delete()
            await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)
            await update.message.reply_text(text[4000:], parse_mode=ParseMode.HTML)
        else:
            await wait_msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Loi he thong: <code>{e}</code>", parse_mode=ParseMode.HTML)


async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Sai cu phap.\nDung: /convert <code>APP_KEY uid|pass</code>\n"
            "Vi du: /convert <code>FB_LITE 100000123|matkhau</code>",
            parse_mode=ParseMode.HTML
        )
        return
    app_key = context.args[0].upper().strip()
    if app_key not in FacebookAppTokens.APPS:
        await update.message.reply_text(
            f"❌ App key '<code>{app_key}</code>' khong hop le. Dung /apps de xem danh sach.",
            parse_mode=ParseMode.HTML
        )
        return

    args_text = " ".join(context.args[1:]).strip()
    parsed = parse_account_args(args_text)
    if not parsed:
        await update.message.reply_text(
            "❌ Sai cu phap account.\nDung: /convert <code>APP_KEY uid|pass</code>",
            parse_mode=ParseMode.HTML
        )
        return
    uid, pwd, tfa, machine_id = parsed

    wait_msg = await update.message.reply_text(f"⏳ Dang dang nhap &amp; convert sang {app_key}...")
    try:
        result = await asyncio.to_thread(do_login, uid, pwd, tfa, machine_id, False, [app_key])
        text = format_result_text(result)
        if len(text) > 4000:
            await wait_msg.delete()
            await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)
            await update.message.reply_text(text[4000:], parse_mode=ParseMode.HTML)
        else:
            await wait_msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Loi he thong: <code>{e}</code>", parse_mode=ParseMode.HTML)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded .txt files - batch processing."""
    if not authorized(update):
        return
    doc = update.message.document
    if not doc:
        return
    if not (doc.file_name or "").lower().endswith('.txt'):
        await update.message.reply_text("⚠️ Chi xu ly file .txt")
        return

    tg_file = await doc.get_file()

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, doc.file_name or "accounts.txt")
        await tg_file.download_to_drive(in_path)

        wait_msg = await update.message.reply_text("⏳ Da nhan file. Dang doc...")

        accounts = []
        try:
            with open(in_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or '|' not in line:
                        continue
                    parts = line.split('|')
                    if len(parts) < 2:
                        continue
                    acc = {'uid': parts[0].strip(), 'pass': parts[1].strip()}
                    if len(parts) >= 3 and parts[2].strip():
                        acc['tfa'] = parts[2].strip().replace(' ', '')
                    if len(parts) >= 4 and parts[3].strip():
                        acc['machine_id'] = parts[3].strip()
                    accounts.append(acc)
        except Exception as e:
            await wait_msg.edit_text(f"❌ Loi doc file: <code>{e}</code>", parse_mode=ParseMode.HTML)
            return

        total = len(accounts)
        if total == 0:
            await wait_msg.edit_text("❌ File khong chua tai khoan hop le (thieu dau |).")
            return

        await wait_msg.edit_text(f"📊 Da nap {total} tai khoan. Bat dau check...")

        tokens = []
        live_count = 0
        die_count = 0
        last_progress = -1

        for i, acc in enumerate(accounts):
            try:
                result = await asyncio.to_thread(
                    do_login,
                    acc['uid'], acc['pass'],
                    acc.get('tfa', ''),
                    acc.get('machine_id', ''),
                    False, None
                )
                if result.get('success'):
                    tk = result['original_token']['access_token']
                    if tk:
                        tokens.append(tk)
                        live_count += 1
                else:
                    die_count += 1
            except Exception:
                die_count += 1

            # Progress update every 5 or at end
            if (i + 1) % 5 == 0 or (i + 1) == total:
                progress_pct = int(((i + 1) / total) * 100)
                if progress_pct != last_progress:
                    last_progress = progress_pct
                    try:
                        await wait_msg.edit_text(
                            f"📊 Tien do: {i+1}/{total} ({progress_pct}%)\n"
                            f"✅ Live: {live_count} | ❌ Die: {die_count}"
                        )
                    except Exception:
                        pass
                # Yield to event loop
                await asyncio.sleep(0)

        if tokens:
            out_name = f"tokens_original_{int(time.time())}.txt"
            out_path = os.path.join(tmpdir, out_name)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(tokens))

            summary = (
                f"✅ <b>HOAN TAT</b>\n"
                f"Tong: {total}\n"
                f"Live: {live_count}\n"
                f"Die: {die_count}\n\n"
                f"File token ({len(tokens)} dong) dinh kem ben duoi."
            )
            await wait_msg.edit_text(summary, parse_mode=ParseMode.HTML)

            with open(out_path, 'rb') as f:
                await update.message.reply_document(
                    document=InputFile(f, filename=out_name),
                    caption=f"Tokens ({live_count} live / {total} total)"
                )
        else:
            await wait_msg.edit_text(
                f"❌ Khong co token nao lay duoc.\nTong: {total} | Die: {die_count}"
            )


def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        print("=" * 60)
        print("❌ Chua cau hinh BOT_TOKEN!")
        print("Cach 1: Sua bien BOT_TOKEN trong file nay.")
        print("Cach 2: Chay voi env var:")
        print("  Linux/Mac:  BOT_TOKEN=xxx python laytoken_bot.py")
        print("  Windows:    set BOT_TOKEN=xxx && python laytoken_bot.py")
        print("=" * 60)
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("apps", cmd_apps))
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CommandHandler("convert_all", cmd_convert_all))
    app.add_handler(CommandHandler("convert", cmd_convert))
    app.add_handler(MessageHandler(filters.Document.TXT, on_document))

    print("🤖 Bot dang chay... Nhan Ctrl+C de dung.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
