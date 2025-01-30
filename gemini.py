import os
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
import io

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for detailed logs
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def validate_configuration():
    """Validate all required environment variables"""
    required_vars = [
        'TELEGRAM_TOKEN',
        'GEMINI_API_KEY',
        'MONGODB_USERNAME',
        'MONGODB_PASSWORD',
        'MONGODB_HOST',
        'MONGODB_DBNAME'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

async def initialize_mongodb():
    """Initialize and verify MongoDB connection"""
    logger.debug("Initializing MongoDB...")
    encoded_user = quote_plus(os.getenv('MONGODB_USERNAME'))
    encoded_pass = quote_plus(os.getenv('MONGODB_PASSWORD'))
    mongodb_uri = f"mongodb+srv://{encoded_user}:{encoded_pass}@{os.getenv('MONGODB_HOST')}/{os.getenv('MONGODB_DBNAME')}?retryWrites=true&w=majority"
    
    try:
        client = AsyncIOMotorClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        logger.info("MongoDB connection successful")
        return client
    except Exception as e:
        logger.error(f"MongoDB connection failed: {str(e)}")
        raise

async def initialize_gemini():
    """Initialize and verify Gemini API connection"""
    logger.debug("Initializing Gemini...")
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        await model.generate_content_async("Test connection")  # Verify API works
        logger.info("Gemini initialized successfully")
        return model
    except Exception as e:
        logger.error(f"Gemini initialization failed: {str(e)}")
        raise

# Keyboard for contact sharing
contact_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Share Contact", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Improved /start command with registration status check"""
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        users_collection = context.bot_data['users_collection']
        user_data = await users_collection.find_one({"chat_id": chat_id})
        
        if not user_data:
            # New user registration flow
            await users_collection.insert_one({
                "chat_id": chat_id,
                "registered": False,
                "first_name": user.first_name,
                "username": user.username,
                "created_at": datetime.now(timezone.utc),
                "last_interaction": datetime.now(timezone.utc)
            })
            await update.message.reply_text(
                "Welcome! Please share your phone number to register:",
                reply_markup=contact_keyboard
            )
            logger.info(f"New user started: {chat_id}")
        else:
            # Existing user status check
            if user_data.get('registered'):
                await update.message.reply_text(
                    "Welcome back! You're fully registered and ready to chat!",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "⚠️ Registration incomplete. Please share your contact:",
                    reply_markup=contact_keyboard
                )
            logger.debug(f"Returning user: {chat_id}")
            
    except Exception as e:
        logger.exception("Start command error")
        await update.message.reply_text("Service temporary unavailable. Please try again later.")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced contact handler with atomic update"""
    try:
        contact = update.message.contact
        chat_id = update.effective_chat.id
        
        result = await context.bot_data['users_collection'].update_one(
            {"chat_id": chat_id},
            {"$set": {
                "phone_number": contact.phone_number,
                "registered": True,
                "last_interaction": datetime.now(timezone.utc)
            }}
        )
        
        if result.modified_count == 1:
            await update.message.reply_text(
                "✅ Registration successful! Ask me anything:",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"User {chat_id} completed registration")
        else:
            await update.message.reply_text(
                "⚠️ Registration failed. Please try /start",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.warning(f"Failed registration update for {chat_id}")
            
    except Exception as e:
        logger.exception("Contact handling failed")
        await update.message.reply_text("❌ Registration error. Please try again.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message handler with consolidated registration check"""
    try:
        chat_id = update.effective_chat.id
        text = update.message.text
        
        # Unified check using MongoDB query
        user = await context.bot_data['users_collection'].find_one(
            {"chat_id": chat_id, "registered": True}
        )
        
        if not user:
            await update.message.reply_text(
                "⚠️ Complete registration first!\n"
                "Use /start and share your contact.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
            
        # Process message...
        response = await context.bot_data['gemini_model'].generate_content_async(text)
        await update.message.reply_text(response.text)
        
        # Update interaction time
        await context.bot_data['users_collection'].update_one(
            {"chat_id": chat_id},
            {"$set": {"last_interaction": datetime.now(timezone.utc)}}
        )
        
    except Exception as e:
        logger.exception("Message processing error")
        await update.message.reply_text("❌ Error processing your message")
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process images"""
    try:
        chat_id = update.effective_chat.id
        logger.debug(f"Image received from {chat_id}")
        
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        img = Image.open(io.BytesIO(photo_bytes)).convert('RGB')
        response = await context.bot_data['gemini_model'].generate_content_async(["Analyze this image:", img])
        
        await context.bot_data['files_collection'].insert_one({
            "user_id": chat_id,
            "file_id": photo_file.file_id,
            "analysis": response.text,
            "timestamp": datetime.now(timezone.utc)
        })
        
        await update.message.reply_text(response.text)
        logger.info(f"Image processed for {chat_id}")
        
    except Exception as e:
        logger.exception("Image processing failed")
        await update.message.reply_text("❌ Failed to analyze image")

def main():
    """Main entry point"""
    try:
        validate_configuration()
        application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
        
        # Initialize services
        async def setup_services():
            mongo_client = await initialize_mongodb()
            gemini_model = await initialize_gemini()
            
            # Share resources with handlers
            application.bot_data.update({
                'users_collection': mongo_client[os.getenv('MONGODB_DBNAME')].users,
                'messages_collection': mongo_client[os.getenv('MONGODB_DBNAME')].messages,
                'files_collection': mongo_client[os.getenv('MONGODB_DBNAME')].files,
                'gemini_model': gemini_model
            })
        
        # Run setup synchronously
        import asyncio
        asyncio.get_event_loop().run_until_complete(setup_services())
        
        # Register handlers
        application.add_handler(CommandHandler('start', start))
        application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_image))
        
        logger.info("Bot is starting...")
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        raise

if __name__ == '__main__':
    main()   
