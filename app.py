import os
import time
import logging
from threading import Lock
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from googletrans import Translator, LANGUAGES

# 環境変数のロード
load_dotenv()

# ロギングの設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境変数の確認
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    logger.error("Slack tokens are not set in the environment variables.")
    raise ValueError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in the .env file.")

# アプリの初期化
app = App(token=SLACK_BOT_TOKEN)

# 翻訳機能の初期化
translator = Translator()

# グローバル変数
processed_events = {}
message_lock = Lock()
last_message_time = 0
MIN_MESSAGE_INTERVAL = 1  # 1秒間隔

def translate_text(text, dest='en'):
    try:
        translation = translator.translate(text, dest=dest)
        return translation.text
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return None

def send_message_with_rate_limit(say, text, channel):
    global last_message_time
    with message_lock:
        current_time = time.time()
        if current_time - last_message_time < MIN_MESSAGE_INTERVAL:
            time.sleep(MIN_MESSAGE_INTERVAL - (current_time - last_message_time))
        say(text=text, channel=channel)
        last_message_time = time.time()

@app.event("message")
def handle_message_events(body, say):
    logger.debug(f"Received message event: {body}")
    event = body["event"]
    event_id = body.get("event_id")
    event_time = body.get("event_time")

    # イベントの重複チェック
    if event_id in processed_events:
        if time.time() - processed_events[event_id] < 60:  # 60秒以内の重複は無視
            logger.info(f"Duplicate event detected: {event_id}")
            return
    
    processed_events[event_id] = time.time()

    process_message(event, say)

def process_message(event, say):
    channel_id = event.get("channel")
    user = event.get("user")
    text = event.get("text")
    
    if not text or event.get("subtype") == "bot_message":
        logger.debug("Skipping empty or bot message")
        return

    logger.info(f"Processing message: channel={channel_id}, user={user}, text={text}")

    try:
        detected_lang = translator.detect(text).lang
        logger.info(f"Detected language: {detected_lang}")

        if detected_lang != 'ja':
            translated_text = translate_text(text, dest='ja')
            if translated_text:
                response = f"<@{user}>さんのメッセージの日本語訳:\n{translated_text}"
            else:
                response = "申し訳ありませんが、翻訳中にエラーが発生しました。"
        else:
            translated_text = translate_text(text, dest='en')
            if translated_text:
                response = f"English translation of <@{user}>'s message:\n{translated_text}"
            else:
                response = "I'm sorry, but an error occurred during translation."

        send_message_with_rate_limit(say, response, channel_id)
    except Exception as e:
        logger.exception(f"Error processing message: {str(e)}")
        say("申し訳ありませんが、メッセージの処理中にエラーが発生しました。")

@app.error
def custom_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.info(f"Request body: {body}")

def list_supported_languages():
    return ", ".join(LANGUAGES.keys())

@app.command("/translation_help")
def translation_help(ack, say):
    ack()
    help_text = (
        "I can translate messages between Japanese and other languages. "
        "Just type your message, and I'll automatically detect the language and translate it. "
        f"Supported languages: {list_supported_languages()}"
    )
    say(help_text)

# アプリの起動
if __name__ == "__main__":
    try:
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        logger.info("Starting the Slack Translator Bot...")
        handler.start()
    except Exception as e:
        logger.error(f"Error starting the app: {str(e)}")
