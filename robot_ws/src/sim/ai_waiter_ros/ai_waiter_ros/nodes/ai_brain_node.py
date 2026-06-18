vad = Silero_VAD() 
asr = PhoASR(model_name= 'vinai/PhoWhisper-large')

is_active = True
print("\n========================================")
print("🤖 AI Waiter is ready to take orders.")
print("========================================")

# --- The Conversation Loop ---
while is_active:
    try:
        # 1. Listen for customer speech using the VAD
        customer_audio_file = vad.listen()

        # 2. Transcribe the captured audio file using PhoWhisper
        customer_text = asr.transcribe(customer_audio_file)
        print(f"👤 CUSTOMER SAID: {customer_text}")

        # 3. (Future Step) Process text with NLU and get a response
        if "tạm biệt" in customer_text.lower():
            is_active = False
            response = "Cảm ơn quý khách. Hẹn gặp lại!"
        else:
            response = "Vâng ạ, tôi đã hiểu. Quý khách còn yêu cầu gì nữa không?"
        
        # 4. (Future Step) Speak the response using TTS
        print(f"🤖 AI WAITER SAYS: {response}")
        # speak(response)

        print("\n--------------------------------------")

    except KeyboardInterrupt:
        print("\nConversation ended by user. Shutting down.")
        is_active = False
    except Exception as e:
        print(f"An error occurred: {e}")
        is_active = False
