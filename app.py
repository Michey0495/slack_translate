import os
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from googletrans import Translator, LANGUAGES

# 環境変数の読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

def translate_text(text, dest='en'):
    try:
        translation = translator.translate(text, dest=dest)
        return translation.text
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return None

@app.event("message")
def handle_message_events(body, say):
    logger.info(f"Received message event: {body}")
    event = body["event"]
    process_message(event, say)

@app.event("app_mention")
def handle_app_mention_events(body, say):
    logger.info(f"Received app mention event: {body}")
    event = body["event"]
    process_message(event, say)

def process_message(event, say):
    channel_id = event.get("channel")
    user = event.get("user")
    text = event.get("text")
    
    if not text:
        logger.warning("Received empty message text")
        return

    logger.info(f"Processing message: channel={channel_id}, user={user}, text={text}")

    # メッセージの言語を検出
    try:
        detected_lang = translator.detect(text).lang
        logger.info(f"Detected language: {detected_lang}")
    except Exception as e:
        logger.error(f"Language detection error: {str(e)}")
        say("Sorry, I couldn't detect the language of your message.")
        return

    # 翻訳
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

    say(response)

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