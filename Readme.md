Telegram AI Chatbot 🤖 This is a Telegram chatbot powered by Google Gemini AI and MongoDB. It can process text and images, register users, and provide AI-generated responses.

Features 🌍 AI-powered text responses 📷 Image analysis with AI 📞 User registration with phone number verification 📊 MongoDB integration for data storage 🔐 Secure API handling with environment variables

Here’s a list of dependencies along with the versions you can use for your project. You can create a requirements.txt file and add the following content:

txt Copy Edit python-telegram-bot==20.0 google-generativeai==0.1.0 motor==2.6.0 Pillow==9.0.1 python-dotenv==0.21.0

1.Set Up the Tech Stack:

Use Python as the programming language.

Install required libraries pip install python-telegram-bot google-generativeai pymongo python-dotenv requests Set up MongoDB for data storage. Use MongoDB Atlas for a free cloud database.

Resource: MongoDB Atlas Setup Guide

2.Environment Setup:

Create a .env file to store sensitive data like API keys and MongoDB URI:

Copy TELEGRAM_BOT_TOKEN=your_telegram_bot_token GEMINI_API_KEY=your_gemini_api_key MONGODB_URI=your_mongodb_uri Resource: Python Dotenv Documentati
