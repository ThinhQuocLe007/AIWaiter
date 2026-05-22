# AI Waiter - Capstone Project

## Introduction
This project is an AI-powered waiter designed to take restaurant orders in Vietnamese. It allows customers to order food and ask menu questions using natural voice commands.

The goal is to build a seamless system that understands context, retrieves menu information, and processes orders using Large Language Models.

## System Architecture
The system follows a specific pipeline to handle voice inputs and generate appropriate responses.

![System Pipeline](pipeline.jpg)

### How it works

The pipeline consists of three main stages:

1. **Input Processing:**
   - The microphone captures audio.
   - **Silero VAD** detects voice activity.
   - **PhoWhisper** converts Vietnamese speech into text.

2. **Llama 3 Decision Engine (The Core):**
   - The text is sent to the Llama 3 model to understand user intent.
   - The system splits into two logic branches:
     - **Branch 1 (Action/Info):** If the user wants to order or asks about food, the system uses **RAG** to search the menu or **Function Calling** to create an order/payment via API.
     - **Branch 2 (General Chat):** If the user is just chatting, the system generates a conversational response without using tools.

3. **Output Synthesis:**
   - The final text response is converted back to speech for the user.

## Tech Stack

- **LLM:** Llama 3 (running locally or on server)
- **Speech-to-Text:** PhoWhisper (Vietnamese specific)
- **Voice Detection:** Silero VAD
- **Knowledge Retrieval:** RAG (Retrieval-Augmented Generation) for Menu Search
- **Actions:** Function Calling (API for Orders/Payments)
- **Deployment:** Kaggle (Prototype) -> AWS (Final)

## Project Status

- [x] System Design & Architecture
- [ ] Text Processing Implementation (Llama 3 + RAG + Tools)
- [ ] Voice Integration
- [ ] Final Deployment

---
University Student - Ho Chi Minh City